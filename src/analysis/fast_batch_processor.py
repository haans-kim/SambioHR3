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
    
    def batch_analyze_employees(self, employee_ids: List[str], target_date: date, 
                              progress_callback=None) -> List[Dict[str, Any]]:
        """
        여러 직원을 실제 병렬로 분석
        
        Args:
            employee_ids: 분석할 직원 ID 목록
            target_date: 분석 대상 날짜
            progress_callback: 진행 상황 콜백 함수 (completed_count, total_count, message)
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
                            progress_msg = f"진행: {completed_count}/{len(employee_ids)} ({rate:.1f}명/초)"
                            self.logger.info(f"  {progress_msg}, 남은시간: {remaining/60:.1f}분")
                            
                            # 콜백 호출
                            if progress_callback:
                                progress_callback(completed_count, len(employee_ids), progress_msg)
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
                # activity_distribution을 사용하고 한글 키로 접근
                activity_dist = activity.get('activity_distribution', {}) if activity else {}
                
                # 디버깅
                if saved_count == 0:  # 첫 번째 결과만 로그
                    self.logger.info(f"[DEBUG] result keys: {list(result.keys())}")
                    self.logger.info(f"[DEBUG] activity_analysis: {activity}")
                    self.logger.info(f"[DEBUG] activity_distribution: {activity_dist}")
                
                data.update({
                    'work_minutes': activity_dist.get('업무', 0) + activity_dist.get('업무(확실)', 0),
                    'meeting_minutes': activity_dist.get('회의', 0) + activity_dist.get('교육', 0),
                    'meal_minutes': activity_dist.get('식사', 0),
                    'movement_minutes': activity_dist.get('경유', 0) + activity_dist.get('이동', 0),
                    'rest_minutes': activity_dist.get('휴게', 0),
                    'breakfast_minutes': 0,  # 세부 식사 시간은 현재 구분되지 않음
                    'lunch_minutes': 0,
                    'dinner_minutes': 0,
                    'midnight_meal_minutes': 0
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
    IndividualAnalyzer.analyze_individual()을 사용하여 완전한 분석 수행
    """
    # IndividualAnalyzer 인스턴스 생성
    from src.analysis.individual_analyzer import IndividualAnalyzer
    from src.database import DatabaseManager
    from src.ui.components.individual_dashboard import IndividualDashboard
    from datetime import datetime, time
    
    # DatabaseManager 인스턴스 생성
    db_manager = DatabaseManager()
    analyzer = IndividualAnalyzer(db_manager)
    
    # IndividualDashboard 인스턴스 생성 (싱글톤과 동일하게)
    dashboard = IndividualDashboard(individual_analyzer=analyzer)
    
    results = []
    
    for employee_id in employee_ids:
        try:
            # 싱글톤과 동일한 방식으로 분석
            # 1. 데이터 로드
            daily_data = dashboard.get_daily_tag_data(employee_id, target_date)
            
            if daily_data is None or daily_data.empty:
                results.append({
                    'employee_id': employee_id,
                    'analysis_date': target_date.isoformat(),
                    'status': 'no_data'
                })
                continue
            
            # 1-2. 식사 데이터도 별도로 로드
            meal_data = dashboard.get_meal_data(employee_id, target_date)
            
            # 2. 활동 분류
            classified_data = dashboard.classify_activities(daily_data)
            
            if classified_data is None or classified_data.empty:
                results.append({
                    'employee_id': employee_id,
                    'analysis_date': target_date.isoformat(),
                    'status': 'no_classified_data'
                })
                continue
            
            # 3. 일일 분석
            analysis_result = dashboard.analyze_daily_data(
                employee_id, 
                target_date, 
                classified_data
            )
            
            # 분석 결과를 배치 프로세서 형식으로 변환
            if analysis_result:
                # 디버깅: analysis_result 내용 확인
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"[DEBUG] analysis_result keys: {list(analysis_result.keys())}")
                logger.info(f"[DEBUG] activity_summary: {analysis_result.get('activity_summary', {})}")
                
                # activity_summary를 activity_analysis 형식으로 변환
                activity_summary = analysis_result.get('activity_summary', {})
                
                # 식사 데이터가 있으면 activity_summary에 추가
                if meal_data is not None and not meal_data.empty:
                    # 식사 종류별로 집계
                    for _, meal in meal_data.iterrows():
                        meal_category = meal.get('식사대분류', meal.get('meal_category', ''))
                        meal_code_map = {
                            '조식': 'BREAKFAST',
                            '중식': 'LUNCH',
                            '석식': 'DINNER',
                            '야식': 'MIDNIGHT_MEAL'
                        }
                        activity_code = meal_code_map.get(meal_category, 'LUNCH')
                        
                        # 테이크아웃 여부에 따라 duration 설정
                        restaurant_info = meal.get('배식구', meal.get('service_point', ''))
                        is_takeout = '테이크아웃' in str(restaurant_info)
                        duration = 10 if is_takeout else 30
                        
                        # activity_summary에 추가
                        if activity_code in activity_summary:
                            activity_summary[activity_code] += duration
                        else:
                            activity_summary[activity_code] = duration
                    
                    logger.info(f"[DEBUG] {employee_id} - 식사 데이터 추가 후 activity_summary: {activity_summary}")
                
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
                    logger.info(f"[DEBUG] {employee_id} - activity_summary: {activity_summary}")
                    logger.info(f"[DEBUG] {employee_id} - activity_distribution (한글): {activity_distribution}")
                
                # activity_analysis 구조 생성
                activity_analysis = {
                    'activity_distribution': activity_distribution,
                    'primary_activity': max(activity_distribution.items(), key=lambda x: x[1])[0] if activity_distribution else 'UNKNOWN',
                    'activity_diversity': len(activity_distribution)
                }
                
                # work_time_analysis와 기타 데이터 추가
                result_dict = {
                    'employee_id': employee_id,
                    'analysis_date': target_date.isoformat(),
                    'status': 'success',
                    'activity_analysis': activity_analysis,
                    'work_time_analysis': analysis_result.get('work_time_analysis', {}),
                    'data_quality': analysis_result.get('data_quality', {}),
                    'timeline_analysis': {
                        'timeline': analysis_result.get('activity_segments', []),
                        'daily_timelines': []  # 호환성을 위해
                    },
                    'meal_time_analysis': analysis_result.get('meal_time_analysis', {})
                }
                
                results.append(result_dict)
            else:
                results.append({
                    'employee_id': employee_id,
                    'analysis_date': target_date.isoformat(),
                    'status': 'no_analysis_result'
                })
            
        except Exception as e:
            results.append({
                'employee_id': employee_id,
                'analysis_date': target_date.isoformat(),
                'status': 'error',
                'error': str(e)
            })
    
    return results