"""
싱글톤 배치 프로세서 - 단일 프로세스로 순차적 처리
데이터 정확성을 위해 멀티프로세싱 없이 작동
"""

import os
import sys
import logging
import pickle
import json
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
from tqdm import tqdm
import time

# 프로젝트 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database import get_database_manager, get_pickle_manager
from src.analysis import IndividualAnalyzer
from src.analysis.analysis_result_saver import AnalysisResultSaver
from src.ui.components.individual_dashboard import IndividualDashboard


class SingletonBatchProcessor:
    """싱글톤 배치 프로세서 - 데이터 정확성을 위한 순차 처리"""
    
    def __init__(self):
        """초기화"""
        # 로깅 설정
        self.setup_logging()
        
        # 싱글톤 매니저 사용
        self.db_manager = get_database_manager()
        self.pickle_manager = get_pickle_manager()
        
        # 분석 컴포넌트 초기화
        self.individual_analyzer = IndividualAnalyzer(self.db_manager)
        self.result_saver = AnalysisResultSaver()
        
        # 데이터 로드
        self.logger.info("싱글톤 배치 프로세서 초기화...")
        self.load_data()
        
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
    
    def load_data(self):
        """데이터 로드"""
        self.logger.info("📥 데이터 로드 시작...")
        
        # 조직 데이터 로드
        self.org_data = self.pickle_manager.load_dataframe('organization_data')
        if self.org_data is None:
            raise ValueError("조직 데이터를 로드할 수 없습니다.")
        
        self.logger.info(f"✅ {len(self.org_data):,}명 직원 데이터 로드 완료")
        
    def process_all_employees(self, start_date: date, end_date: date, 
                            save_to_db: bool = True, 
                            skip_existing: bool = True) -> Dict[str, Any]:
        """모든 직원 분석 처리 (순차적)
        
        Args:
            start_date: 분석 시작일
            end_date: 분석 종료일  
            save_to_db: DB 저장 여부
            skip_existing: 기존 분석 결과 스킵 여부
            
        Returns:
            처리 결과 통계
        """
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"싱글톤 배치 분석 시작")
        self.logger.info(f"분석 기간: {start_date} ~ {end_date}")
        self.logger.info(f"직원 수: {len(self.org_data):,}명")
        self.logger.info(f"{'='*60}\n")
        
        # 분석 대상 날짜 목록
        dates = pd.date_range(start_date, end_date).to_list()
        total_analyses = len(self.org_data) * len(dates)
        
        # 결과 저장
        results = {
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'errors': [],
            'processing_time': 0
        }
        
        start_time = time.time()
        
        # 직원별 순차 처리
        with tqdm(total=total_analyses, desc="전체 진행률") as pbar:
            for _, employee in self.org_data.iterrows():
                employee_id = str(employee['사번'])
                employee_name = employee['성명']
                
                # 직원별 처리
                for analysis_date in dates:
                    try:
                        # 기존 결과 확인
                        if skip_existing and self._check_existing_result(employee_id, analysis_date):
                            results['skipped'] += 1
                            pbar.update(1)
                            continue
                        
                        # 개별 분석 수행
                        result = self._analyze_single_employee_date(
                            employee_id, 
                            employee_name,
                            analysis_date,
                            save_to_db
                        )
                        
                        if result:
                            results['success'] += 1
                        else:
                            results['failed'] += 1
                            
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append({
                            'employee_id': employee_id,
                            'date': analysis_date.strftime('%Y-%m-%d'),
                            'error': str(e)
                        })
                        self.logger.error(f"분석 실패: {employee_id} ({analysis_date}): {e}")
                    
                    pbar.update(1)
        
        # 처리 시간 계산
        results['processing_time'] = time.time() - start_time
        
        # 결과 요약
        self._print_summary(results, total_analyses)
        
        return results
    
    def _analyze_single_employee_date(self, employee_id: str, employee_name: str,
                                    analysis_date: date, save_to_db: bool) -> Optional[Dict]:
        """단일 직원-날짜 분석
        
        Args:
            employee_id: 직원 ID
            employee_name: 직원 이름
            analysis_date: 분석 날짜
            save_to_db: DB 저장 여부
            
        Returns:
            분석 결과 또는 None
        """
        try:
            # IndividualDashboard 초기화
            dashboard = IndividualDashboard(
                individual_analyzer=self.individual_analyzer
            )
            
            # 데이터 로드
            daily_data = dashboard.get_daily_tag_data(employee_id, analysis_date)
            
            if daily_data is None or daily_data.empty:
                return None
            
            # 활동 분류
            classified_data = dashboard.classify_activities(daily_data)
            
            if classified_data is None or classified_data.empty:
                return None
            
            # 일일 분석
            analysis_result = dashboard.analyze_daily_data(
                employee_id, 
                analysis_date, 
                classified_data
            )
            
            if analysis_result:
                # activity_summary를 activity_analysis 형식으로 변환 (FastBatchProcessor와 동일)
                activity_summary = analysis_result.get('activity_summary', {})
                
                # 영문 activity_code를 한글로 매핑
                activity_mapping = {
                    'WORK': '업무',
                    'FOCUSED_WORK': '업무(확실)',
                    'EQUIPMENT_OPERATION': '업무',
                    'WORK_PREPARATION': '준비',
                    'WORKING': '업무',
                    'MEETING': '회의',
                    'TRAINING': '교육',
                    'EDUCATION': '교육',
                    'BREAKFAST': '식사',
                    'LUNCH': '식사',
                    'DINNER': '식사',
                    'MIDNIGHT_MEAL': '식사',
                    'REST': '휴게',
                    'FITNESS': '휴게',
                    'LEAVE': '휴게',
                    'IDLE': '휴게',
                    'MOVEMENT': '이동',
                    'TRANSIT': '경유',
                    'COMMUTE_IN': '출입(IN)',
                    'COMMUTE_OUT': '출입(OUT)',
                    'NON_WORK': '비업무',
                    'UNKNOWN': '비업무'
                }
                
                # 한글 키로 변환된 activity_distribution 생성
                activity_distribution = {}
                for code, minutes in activity_summary.items():
                    korean_key = activity_mapping.get(code, code)
                    if korean_key in activity_distribution:
                        activity_distribution[korean_key] += minutes
                    else:
                        activity_distribution[korean_key] = minutes
                
                # 디버깅: 변환 결과 확인
                if employee_id in ['20120203', '20150276']:  # 처음 두 직원만
                    self.logger.info(f"[DEBUG] {employee_id} - activity_summary: {activity_summary}")
                    self.logger.info(f"[DEBUG] {employee_id} - activity_distribution (한글): {activity_distribution}")
                
                # activity_analysis 구조 생성
                activity_analysis = {
                    'activity_distribution': activity_distribution,
                    'primary_activity': max(activity_distribution.items(), key=lambda x: x[1])[0] if activity_distribution else 'UNKNOWN',
                    'activity_diversity': len(activity_distribution)
                }
                
                # 결과에 activity_analysis 추가
                analysis_result['activity_analysis'] = activity_analysis
                
                # timeline_analysis 형식 맞추기
                if 'activity_segments' in analysis_result:
                    analysis_result['timeline_analysis'] = {
                        'timeline': analysis_result.get('activity_segments', []),
                        'daily_timelines': []
                    }
                
                if save_to_db:
                    # DB 저장
                    self.result_saver.save_individual_analysis(analysis_result)
                
            return analysis_result
            
        except Exception as e:
            self.logger.error(f"직원 분석 오류 {employee_id}: {e}")
            return None
    
    def _check_existing_result(self, employee_id: str, analysis_date: date) -> bool:
        """기존 분석 결과 존재 여부 확인
        
        Args:
            employee_id: 직원 ID
            analysis_date: 분석 날짜
            
        Returns:
            존재 여부
        """
        try:
            query = """
            SELECT 1 FROM individual_analysis_results 
            WHERE employee_id = :employee_id 
            AND analysis_date = :analysis_date
            LIMIT 1
            """
            
            result = self.db_manager.execute_query(query, {
                'employee_id': employee_id,
                'analysis_date': analysis_date.strftime('%Y-%m-%d')
            })
            
            return len(result) > 0
            
        except:
            return False
    
    def _print_summary(self, results: Dict[str, Any], total_analyses: int):
        """처리 결과 요약 출력
        
        Args:
            results: 처리 결과
            total_analyses: 전체 분석 수
        """
        processing_time = results['processing_time']
        success_count = results['success']
        failed_count = results['failed']
        skipped_count = results['skipped']
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"싱글톤 배치 처리 완료")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"전체 분석 수: {total_analyses:,}")
        self.logger.info(f"성공: {success_count:,} ({success_count/total_analyses*100:.1f}%)")
        self.logger.info(f"실패: {failed_count:,} ({failed_count/total_analyses*100:.1f}%)")
        self.logger.info(f"스킵: {skipped_count:,} ({skipped_count/total_analyses*100:.1f}%)")
        self.logger.info(f"처리 시간: {processing_time/60:.1f}분")
        self.logger.info(f"평균 처리 속도: {total_analyses/processing_time:.1f} 분석/초")
        
        if results['errors']:
            self.logger.warning(f"\n오류 발생 목록 (상위 10개):")
            for error in results['errors'][:10]:
                self.logger.warning(f"  - {error['employee_id']} ({error['date']}): {error['error']}")


def main():
    """메인 실행 함수"""
    # 날짜 설정
    start_date = date(2024, 10, 1)
    end_date = date(2024, 10, 31)
    
    # 싱글톤 프로세서 생성
    processor = SingletonBatchProcessor()
    
    # 전체 직원 처리
    results = processor.process_all_employees(
        start_date=start_date,
        end_date=end_date,
        save_to_db=True,
        skip_existing=True
    )
    
    return results


if __name__ == "__main__":
    main()