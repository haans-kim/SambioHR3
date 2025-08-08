"""
병렬 배치 분석 모듈 - 기존 분석 로직을 멀티프로세싱으로 가속화
"""

import os
import sys
import logging
import pickle
import json
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple
from multiprocessing import Pool, Manager, Queue, cpu_count
from concurrent.futures import ProcessPoolExecutor, as_completed
import pandas as pd
from tqdm import tqdm
import psutil
import time

# 프로젝트 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database import get_database_manager, get_pickle_manager
from src.analysis import IndividualAnalyzer
from src.analysis.analysis_result_saver import AnalysisResultSaver
from src.ui.components.individual_dashboard import IndividualDashboard


class ParallelBatchAnalyzer:
    """초고속 병렬 배치 분석 엔진"""
    
    def __init__(self, num_workers: int = None):
        """
        Args:
            num_workers: 워커 프로세스 수 (None이면 CPU 코어 수 - 1)
        """
        # 워커 수 결정 (M4 Max는 12개 P-코어)
        self.num_workers = num_workers or min(cpu_count() - 1, 12)
        
        # 로깅 설정
        self.setup_logging()
        
        # 데이터 사전 로드 및 인덱싱
        self.logger.info(f"병렬 분석 엔진 초기화 (워커: {self.num_workers})")
        self.prepare_indexed_data()
        
        # 진행 상황 큐
        self.manager = Manager()
        self.progress_queue = self.manager.Queue()
        self.result_queue = self.manager.Queue()
        
    def setup_logging(self):
        """로깅 설정"""
        self.logger = logging.getLogger(__name__)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - [%(levelname)s] - %(message)s',
            datefmt='%H:%M:%S'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def prepare_indexed_data(self):
        """데이터를 메모리에 로드하고 인덱싱"""
        self.logger.info("📥 데이터 인덱싱 시작...")
        
        # Pickle Manager로 데이터 로드
        pickle_manager = get_pickle_manager()
        
        # 조직 데이터 로드
        org_data = pickle_manager.load_dataframe('organization_data')
        
        # 직원별 인덱스 생성
        self.employee_index = {}
        for _, row in org_data.iterrows():
            emp_id = row['사번']
            self.employee_index[emp_id] = {
                'employee_id': emp_id,
                'employee_name': row['성명'],
                'center_id': row['센터'],
                'group_id': row['그룹'],
                'team_id': row['팀'],
                'job_grade': row.get('직급2*', '')
            }
        
        self.logger.info(f"✅ {len(self.employee_index):,}명 직원 인덱싱 완료")
        
        # 태그 데이터 사전 로드 (가능한 경우)
        try:
            daily_tags = pickle_manager.load_dataframe('daily_tags')
            if daily_tags is not None:
                # 직원-날짜별 인덱스 생성
                self.tag_index = {}
                for emp_id, group in daily_tags.groupby('employee_id'):
                    self.tag_index[emp_id] = group.to_dict('records')
                self.logger.info(f"✅ 태그 데이터 인덱싱 완료")
        except:
            self.tag_index = None
            self.logger.info("태그 데이터 사전 로드 스킵")
    
    @staticmethod
    def analyze_single_employee(args: Tuple) -> Dict[str, Any]:
        """
        단일 직원 분석 (워커 프로세스에서 실행)
        정적 메서드로 피클링 가능
        """
        employee_id, analysis_date, employee_info = args
        
        try:
            # 각 프로세스에서 독립적으로 객체 생성
            from src.database import get_database_manager
            from src.analysis import IndividualAnalyzer
            from src.ui.components.individual_dashboard import IndividualDashboard
            
            db_manager = get_database_manager()
            analyzer = IndividualAnalyzer(db_manager)
            dashboard = IndividualDashboard(analyzer)
            
            # 분석 수행
            daily_data = dashboard.get_daily_tag_data(employee_id, analysis_date)
            
            if daily_data is None or daily_data.empty:
                return {
                    'employee_id': employee_id,
                    'status': 'no_data',
                    'analysis_date': analysis_date.isoformat()
                }
            
            # 활동 분류
            classified_data = dashboard.classify_activities(daily_data, employee_id, analysis_date)
            
            # 일일 분석
            result = dashboard.analyze_daily_data(
                employee_id,
                analysis_date,
                classified_data
            )
            
            # 메모리 절약을 위한 데이터 정리
            if 'raw_data' in result:
                del result['raw_data']
            if 'timeline_data' in result:
                del result['timeline_data']
            
            result['status'] = 'success'
            result['employee_info'] = employee_info
            
            return result
            
        except Exception as e:
            return {
                'employee_id': employee_id,
                'status': 'error',
                'error': str(e),
                'analysis_date': analysis_date.isoformat()
            }
    
    def batch_analyze_parallel(self, 
                             analysis_date: date,
                             employee_ids: List[str] = None,
                             center_id: str = None,
                             group_id: str = None,
                             team_id: str = None,
                             save_to_db: bool = True) -> Dict[str, Any]:
        """
        병렬 배치 분석 실행
        
        Args:
            analysis_date: 분석 날짜
            employee_ids: 특정 직원 ID 리스트 (None이면 조직 기준)
            center_id: 센터 ID
            group_id: 그룹 ID  
            team_id: 팀 ID
            save_to_db: DB 저장 여부
            
        Returns:
            분석 결과 요약
        """
        start_time = time.time()
        
        # 분석할 직원 목록 준비
        if employee_ids:
            employees = [self.employee_index[emp_id] for emp_id in employee_ids 
                        if emp_id in self.employee_index]
        else:
            employees = self._filter_employees(center_id, group_id, team_id)
        
        if not employees:
            return {'status': 'no_employees', 'total': 0}
        
        total_count = len(employees)
        self.logger.info(f"🚀 병렬 분석 시작: {total_count:,}명, 워커: {self.num_workers}개")
        
        # 분석 태스크 준비
        tasks = [
            (emp['employee_id'], analysis_date, emp)
            for emp in employees
        ]
        
        # 병렬 처리 실행
        results = []
        success_count = 0
        error_count = 0
        
        # ProcessPoolExecutor 사용 (더 안정적)
        with ProcessPoolExecutor(max_workers=self.num_workers) as executor:
            # 모든 태스크 제출
            futures = {
                executor.submit(self.analyze_single_employee, task): task[0]
                for task in tasks
            }
            
            # 진행률 표시
            with tqdm(total=total_count, desc="분석 진행") as pbar:
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=10)  # 10초 타임아웃
                        
                        if result['status'] == 'success':
                            success_count += 1
                            
                            # DB 저장
                            if save_to_db:
                                self._save_result(result)
                            
                            results.append(result)
                        else:
                            error_count += 1
                            
                    except Exception as e:
                        error_count += 1
                        self.logger.error(f"분석 실패: {e}")
                    
                    pbar.update(1)
                    
                    # 실시간 통계 업데이트
                    if pbar.n % 100 == 0:
                        elapsed = time.time() - start_time
                        rate = pbar.n / elapsed
                        eta = (total_count - pbar.n) / rate if rate > 0 else 0
                        
                        pbar.set_postfix({
                            '성공': success_count,
                            '실패': error_count,
                            '속도': f'{rate:.1f}/s',
                            '남은시간': f'{eta/60:.1f}분'
                        })
        
        # 최종 통계
        elapsed_time = time.time() - start_time
        
        summary = {
            'status': 'completed',
            'analysis_date': analysis_date.isoformat(),
            'total_employees': total_count,
            'analyzed_count': success_count,
            'error_count': error_count,
            'success_rate': round(success_count / total_count * 100, 1),
            'elapsed_seconds': round(elapsed_time, 1),
            'processing_rate': round(total_count / elapsed_time, 1),
            'workers_used': self.num_workers,
            'saved_to_db': save_to_db
        }
        
        # 평균 지표 계산
        if results:
            valid_results = [r for r in results if 'work_time_analysis' in r]
            if valid_results:
                avg_efficiency = sum(r['work_time_analysis']['efficiency_ratio'] 
                                   for r in valid_results) / len(valid_results)
                avg_work_hours = sum(r['work_time_analysis']['actual_work_hours'] 
                                   for r in valid_results) / len(valid_results)
                
                summary['averages'] = {
                    'efficiency_ratio': round(avg_efficiency, 1),
                    'actual_work_hours': round(avg_work_hours, 1)
                }
        
        self.logger.info(f"✅ 분석 완료: {total_count:,}건 in {elapsed_time:.1f}초")
        self.logger.info(f"⚡ 처리 속도: {summary['processing_rate']:.1f} 건/초")
        
        return summary
    
    def _filter_employees(self, center_id=None, group_id=None, team_id=None):
        """조직 기준으로 직원 필터링"""
        employees = []
        
        for emp_id, emp_info in self.employee_index.items():
            if center_id and emp_info['center_id'] != center_id:
                continue
            if group_id and emp_info['group_id'] != group_id:
                continue
            if team_id and emp_info['team_id'] != team_id:
                continue
            
            employees.append(emp_info)
        
        return employees
    
    def _save_result(self, result):
        """분석 결과 DB 저장"""
        try:
            saver = AnalysisResultSaver()
            saver.save_individual_analysis(
                result,
                result.get('employee_info', {})
            )
        except Exception as e:
            self.logger.error(f"DB 저장 실패: {e}")
    
    def get_system_info(self) -> Dict[str, Any]:
        """시스템 정보 조회"""
        return {
            'cpu_count': cpu_count(),
            'workers': self.num_workers,
            'memory_usage_mb': psutil.Process().memory_info().rss / 1024 / 1024,
            'cpu_percent': psutil.cpu_percent(interval=1),
            'available_memory_gb': psutil.virtual_memory().available / 1024 / 1024 / 1024
        }


# CLI 실행용
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='병렬 배치 분석')
    parser.add_argument('--date', type=str, required=True, help='분석 날짜 (YYYY-MM-DD)')
    parser.add_argument('--workers', type=int, help='워커 프로세스 수')
    parser.add_argument('--center', type=str, help='센터 ID')
    parser.add_argument('--group', type=str, help='그룹 ID')
    parser.add_argument('--team', type=str, help='팀 ID')
    
    args = parser.parse_args()
    
    # 분석 실행
    analyzer = ParallelBatchAnalyzer(num_workers=args.workers)
    
    # 시스템 정보 출력
    sys_info = analyzer.get_system_info()
    print(f"\n🖥️ 시스템 정보:")
    print(f"  - CPU 코어: {sys_info['cpu_count']}개")
    print(f"  - 워커: {sys_info['workers']}개")
    print(f"  - 메모리: {sys_info['available_memory_gb']:.1f}GB 사용 가능")
    
    # 분석 실행
    analysis_date = datetime.strptime(args.date, '%Y-%m-%d').date()
    
    summary = analyzer.batch_analyze_parallel(
        analysis_date,
        center_id=args.center,
        group_id=args.group,
        team_id=args.team
    )
    
    print(f"\n📊 분석 결과:")
    print(f"  - 총 직원: {summary['total_employees']:,}명")
    print(f"  - 성공: {summary['analyzed_count']:,}명")
    print(f"  - 실패: {summary['error_count']:,}명")
    print(f"  - 소요 시간: {summary['elapsed_seconds']:.1f}초")
    print(f"  - 처리 속도: {summary['processing_rate']:.1f}건/초")