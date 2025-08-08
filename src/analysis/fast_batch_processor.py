"""
고속 배치 프로세서 - 실제 병렬 처리로 대규모 데이터 처리
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import date, datetime, timedelta
import logging
import time
import sqlite3
from pathlib import Path
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
import pickle
import tempfile
import os

# 프로젝트 경로 추가
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src.analysis.individual_analyzer import IndividualAnalyzer


class FastBatchProcessor:
    """고속 병렬 처리를 위한 배치 프로세서"""
    
    def __init__(self, num_workers: int = 4, db_path: str = None):
        """
        Args:
            num_workers: 워커 프로세스 수
            db_path: 데이터베이스 경로
        """
        self.num_workers = min(num_workers, os.cpu_count() or 4)
        self.logger = logging.getLogger(__name__)
        
        # DB 경로 설정
        if db_path:
            self.db_path = db_path
        else:
            db_file = Path(project_root) / 'data' / 'sambio_human.db'
            self.db_path = str(db_file) if db_file.exists() else 'data/sambio_human.db'
        
        self.logger.info(f"FastBatchProcessor 초기화 (워커: {self.num_workers}, DB: {self.db_path})")
    
    def preload_data_for_date(self, target_date: date) -> str:
        """
        특정 날짜의 모든 데이터를 미리 로드하고 임시 파일에 저장
        Returns:
            임시 파일 경로
        """
        self.logger.info(f"📥 {target_date} 데이터 사전 로드 시작...")
        start_time = time.time()
        
        conn = sqlite3.connect(self.db_path)
        
        try:
            # 날짜 형식 준비
            prev_date = target_date - timedelta(days=1)
            target_date_str = target_date.strftime('%Y%m%d')
            prev_date_str = prev_date.strftime('%Y%m%d')
            
            # 1. 태그 데이터 로드
            tag_query = f"""
                SELECT 사번 as employee_id, ENTE_DT, 출입시각, DR_NM, INOUT_GB,
                       CENTER, BU, TEAM, GROUP_A, PART
                FROM tag_data 
                WHERE ENTE_DT BETWEEN {prev_date_str} AND {target_date_str}
                ORDER BY 사번, 출입시각
            """
            tag_data = pd.read_sql_query(tag_query, conn)
            self.logger.info(f"  태그 데이터: {len(tag_data):,}건")
            
            # 2. 식사 데이터 로드
            meal_query = f"""
                SELECT 사번 as employee_id, 취식일시, 정산일, 식당명, 
                       식사구분명, 성명, 부서
                FROM meal_data
                WHERE DATE(정산일) BETWEEN '{prev_date}' AND '{target_date}'
            """
            meal_data = pd.read_sql_query(meal_query, conn)
            self.logger.info(f"  식사 데이터: {len(meal_data):,}건")
            
            # 3. Claim 데이터 로드
            claim_query = f"""
                SELECT 사번 as employee_id, 근무일, WORKSCHDTYPNM, 
                       근무시간, 시작, 종료, 성명, 부서, 직급
                FROM claim_data
                WHERE DATE(근무일) = '{target_date}'
            """
            claim_data = pd.read_sql_query(claim_query, conn)
            self.logger.info(f"  Claim 데이터: {len(claim_data):,}건")
            
        finally:
            conn.close()
        
        # 데이터를 임시 파일에 저장
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
        data_cache = {
            'tag_data': tag_data,
            'meal_data': meal_data,
            'claim_data': claim_data,
            'target_date': target_date
        }
        
        with open(temp_file.name, 'wb') as f:
            pickle.dump(data_cache, f)
        
        elapsed = time.time() - start_time
        self.logger.info(f"✅ 데이터 로드 완료: {elapsed:.2f}초")
        
        return temp_file.name
    
    def batch_analyze_employees(self, employee_ids: List[str], target_date: date) -> List[Dict[str, Any]]:
        """
        여러 직원을 실제 병렬로 분석
        """
        self.logger.info(f"🚀 고속 배치 분석 시작: {len(employee_ids)}명, {self.num_workers}개 워커")
        start_time = time.time()
        
        # 1. 데이터 사전 로드 및 임시 파일 저장
        temp_file_path = self.preload_data_for_date(target_date)
        
        try:
            # 2. 작업을 청크로 분할
            chunk_size = max(1, len(employee_ids) // (self.num_workers * 4))  # 각 워커가 여러 청크 처리
            chunks = [employee_ids[i:i+chunk_size] for i in range(0, len(employee_ids), chunk_size)]
            
            self.logger.info(f"  청크 수: {len(chunks)}, 청크 크기: ~{chunk_size}명")
            
            # 3. 병렬 처리
            results = []
            completed_count = 0
            
            with ProcessPoolExecutor(max_workers=self.num_workers) as executor:
                # 작업 제출
                future_to_chunk = {
                    executor.submit(process_employee_chunk, temp_file_path, chunk, target_date): chunk
                    for chunk in chunks
                }
                
                # 결과 수집
                for future in as_completed(future_to_chunk):
                    chunk = future_to_chunk[future]
                    try:
                        chunk_results = future.result()
                        results.extend(chunk_results)
                        completed_count += len(chunk_results)
                        
                        # 진행 상황 표시
                        if completed_count % 100 == 0 or completed_count == len(employee_ids):
                            elapsed = time.time() - start_time
                            rate = completed_count / elapsed if elapsed > 0 else 0
                            remaining = (len(employee_ids) - completed_count) / rate if rate > 0 else 0
                            self.logger.info(f"  진행: {completed_count}/{len(employee_ids)} "
                                           f"({rate:.1f}명/초, 남은시간: {remaining/60:.1f}분)")
                    except Exception as e:
                        self.logger.error(f"청크 처리 실패: {e}")
                        # 실패한 청크의 직원들에 대해 에러 결과 추가
                        for emp_id in chunk:
                            results.append({
                                'employee_id': emp_id,
                                'analysis_date': target_date.isoformat(),
                                'status': 'error',
                                'error': str(e)
                            })
        
        finally:
            # 임시 파일 삭제
            try:
                os.unlink(temp_file_path)
            except:
                pass
        
        elapsed = time.time() - start_time
        success_count = sum(1 for r in results if r.get('status') == 'success')
        
        self.logger.info(f"✅ 고속 배치 분석 완료")
        self.logger.info(f"  - 총 직원: {len(employee_ids)}명")
        self.logger.info(f"  - 성공: {success_count}명")
        self.logger.info(f"  - 소요 시간: {elapsed:.2f}초")
        self.logger.info(f"  - 처리 속도: {len(employee_ids)/elapsed:.1f}명/초")
        
        return results
    
    def save_results_to_db(self, results: List[Dict[str, Any]]) -> int:
        """분석 결과를 DB에 저장"""
        self.logger.info(f"💾 {len(results)}건 DB 저장 시작...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        saved_count = 0
        
        try:
            for result in results:
                if result.get('status') != 'success':
                    continue
                
                # 데이터 준비
                work_time = result.get('work_time_analysis', {})
                meal_time = result.get('meal_time_analysis', {})
                
                # timeline에서 첫 태그와 마지막 태그 시간 추출
                timeline = result.get('timeline_analysis', {}).get('daily_timelines', [])
                work_start = None
                work_end = None
                total_hours = 0
                
                if timeline:
                    for daily in timeline:
                        events = daily.get('timeline', [])
                        if events:
                            first_event = events[0]
                            last_event = events[-1]
                            if work_start is None or first_event.get('timestamp') < work_start:
                                work_start = first_event.get('timestamp')
                            if work_end is None or last_event.get('timestamp') > work_end:
                                work_end = last_event.get('timestamp')
                            
                            # 총 체류시간 계산
                            if work_start and work_end:
                                start_dt = pd.to_datetime(work_start)
                                end_dt = pd.to_datetime(work_end)
                                total_hours = (end_dt - start_dt).total_seconds() / 3600
                
                # work_efficiency 값 추출 (안전하게)
                efficiency_ratio = 0
                if work_time and 'work_efficiency' in work_time:
                    efficiency_ratio = work_time.get('work_efficiency', 0)
                elif work_time and 'efficiency_ratio' in work_time:
                    efficiency_ratio = work_time.get('efficiency_ratio', 0)
                
                data = {
                    'employee_id': result['employee_id'],
                    'analysis_date': result['analysis_date'],
                    'work_start': work_start,
                    'work_end': work_end,
                    'total_hours': total_hours,
                    'actual_work_hours': work_time.get('actual_work_hours', 0) if work_time else 0,
                    'claimed_work_hours': work_time.get('claimed_work_hours', 0) if work_time else 0,
                    'efficiency_ratio': efficiency_ratio,
                    'meal_count': (meal_time.get('lunch_count', 0) + meal_time.get('dinner_count', 0) + 
                                  meal_time.get('breakfast_count', 0) + meal_time.get('midnight_meal_count', 0)) if meal_time else 0,
                    'tag_count': result.get('data_quality', {}).get('total_tags', 0),
                    'updated_at': datetime.now().isoformat()
                }
                
                # 활동별 시간 데이터 추가 (activity_analysis에서 가져옴)
                activity = result.get('activity_analysis', {})
                activity_summary = activity.get('activity_summary', {}) if activity else {}
                
                data.update({
                    'work_minutes': activity_summary.get('WORK', 0) + activity_summary.get('WORK_CONFIRMED', 0),
                    'meeting_minutes': activity_summary.get('MEETING', 0),
                    'meal_minutes': (activity_summary.get('BREAKFAST', 0) + activity_summary.get('LUNCH', 0) + 
                                   activity_summary.get('DINNER', 0) + activity_summary.get('MIDNIGHT_MEAL', 0)),
                    'movement_minutes': activity_summary.get('TRANSIT', 0),
                    'rest_minutes': activity_summary.get('REST', 0),
                    'breakfast_minutes': activity_summary.get('BREAKFAST', 0),
                    'lunch_minutes': activity_summary.get('LUNCH', 0),
                    'dinner_minutes': activity_summary.get('DINNER', 0),
                    'midnight_meal_minutes': activity_summary.get('MIDNIGHT_MEAL', 0)
                })
                
                # 신뢰도 추가
                data['confidence_score'] = result.get('data_quality', {}).get('data_completeness', 50)
                
                # UPSERT 쿼리 (활동별 시간 컬럼 추가)
                cursor.execute("""
                    INSERT OR REPLACE INTO daily_analysis_results 
                    (employee_id, analysis_date, work_start, work_end,
                     total_hours, actual_work_hours, claimed_work_hours,
                     efficiency_ratio, meal_count, tag_count,
                     work_minutes, meeting_minutes, meal_minutes,
                     movement_minutes, rest_minutes,
                     breakfast_minutes, lunch_minutes, dinner_minutes, midnight_meal_minutes,
                     confidence_score, updated_at)
                    VALUES 
                    (:employee_id, :analysis_date, :work_start, :work_end,
                     :total_hours, :actual_work_hours, :claimed_work_hours,
                     :efficiency_ratio, :meal_count, :tag_count,
                     :work_minutes, :meeting_minutes, :meal_minutes,
                     :movement_minutes, :rest_minutes,
                     :breakfast_minutes, :lunch_minutes, :dinner_minutes, :midnight_meal_minutes,
                     :confidence_score, :updated_at)
                """, data)
                
                saved_count += 1
                
                if saved_count % 1000 == 0:
                    conn.commit()  # 주기적으로 커밋
                    self.logger.info(f"  {saved_count}건 저장...")
            
            conn.commit()  # 최종 커밋
            
        except Exception as e:
            self.logger.error(f"DB 저장 실패: {e}")
            conn.rollback()
            
        finally:
            conn.close()
        
        self.logger.info(f"✅ DB 저장 완료: {saved_count}건")
        return saved_count


def process_employee_chunk(temp_file_path: str, employee_ids: List[str], target_date: date) -> List[Dict[str, Any]]:
    """
    워커 프로세스에서 실행될 함수
    IndividualAnalyzer를 사용하여 개인별 분석 수행
    """
    # IndividualAnalyzer 인스턴스 생성
    from src.analysis.individual_analyzer import IndividualAnalyzer
    from src.database import DatabaseManager
    
    # DatabaseManager 인스턴스 생성
    db_manager = DatabaseManager()
    analyzer = IndividualAnalyzer(db_manager)
    
    results = []
    
    for employee_id in employee_ids:
        try:
            # 개인별 분석 실행 (target_date 하루만)
            analysis_result = analyzer.analyze_individual(
                employee_id=employee_id,
                start_date=datetime.combine(target_date, datetime.min.time()),
                end_date=datetime.combine(target_date, datetime.max.time())
            )
            
            # 분석 결과를 배치 프로세서 형식으로 변환
            if analysis_result:
                work_time = analysis_result.get('work_time_analysis', {})
                meal_time = analysis_result.get('meal_time_analysis', {})
                activity = analysis_result.get('activity_analysis', {})
                timeline = analysis_result.get('timeline_analysis', {})
                
                results.append({
                    'employee_id': employee_id,
                    'analysis_date': target_date.isoformat(),
                    'status': 'success',
                    'work_time_analysis': work_time,
                    'meal_time_analysis': meal_time,
                    'activity_analysis': activity,
                    'timeline_analysis': timeline,
                    'data_quality': analysis_result.get('data_quality', {})
                })
            else:
                results.append({
                    'employee_id': employee_id,
                    'analysis_date': target_date.isoformat(),
                    'status': 'no_data'
                })
            
        except Exception as e:
            results.append({
                'employee_id': employee_id,
                'analysis_date': target_date.isoformat(),
                'status': 'error',
                'error': str(e)
            })
    
    return results