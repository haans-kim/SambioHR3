"""
간소화된 배치 프로세서 - 기존 시스템과 호환되는 최적화 버전
조직별 근무분석에서 바로 사용 가능
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from datetime import date, datetime, timedelta
import pickle
import logging
import time
from multiprocessing import Pool, Manager, cpu_count
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import sqlite3
from pathlib import Path
import sys
import os

# 프로젝트 경로 추가
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))


class SimpleBatchProcessor:
    """기존 시스템과 호환되는 간소화된 배치 프로세서"""
    
    def __init__(self, num_workers: int = 4, db_path: str = None):
        """
        Args:
            num_workers: 워커 프로세스 수 (기본값 4로 안전하게 설정)
            db_path: 데이터베이스 경로 (None이면 기본 경로 사용)
        """
        self.num_workers = num_workers
        
        # 로거 설정 (이미 설정되어 있으면 재사용)
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            logging.basicConfig(level=logging.INFO)
        
        # 기존 DB 연결 (SQLite)
        if db_path:
            self.db_path = db_path
        else:
            # 프로젝트 루트에서 상대 경로로 찾기
            db_file = Path(project_root) / 'data' / 'sambio_human.db'
            if db_file.exists():
                self.db_path = str(db_file)
            else:
                self.db_path = 'data/sambio_human.db'
        
        # 데이터 캐시
        self.data_cache = {}
        
        self.logger.info(f"SimpleBatchProcessor 초기화 (워커: {self.num_workers}, DB: {self.db_path})")
    
    def preload_data_for_date(self, target_date: date) -> Dict[str, pd.DataFrame]:
        """
        특정 날짜의 모든 데이터를 미리 로드
        메모리에 한 번만 로드하여 모든 직원이 공유
        """
        self.logger.info(f"📥 {target_date} 데이터 사전 로드 시작...")
        start_time = time.time()
        
        # DB 파일 존재 확인
        if not Path(self.db_path).exists():
            self.logger.error(f"DB 파일이 없습니다: {self.db_path}")
            raise FileNotFoundError(f"Database file not found: {self.db_path}")
        
        conn = sqlite3.connect(self.db_path)
        
        try:
            # 1. 태그 데이터 로드 (실제 컬럼명 사용)
            # ENTE_DT가 날짜, 출입시각이 시간
            prev_date = target_date - timedelta(days=1)
            
            # ENTE_DT를 날짜로 변환 (YYYYMMDD 형식일 가능성)
            target_date_str = target_date.strftime('%Y%m%d')
            prev_date_str = prev_date.strftime('%Y%m%d')
            
            tag_query = f"""
                SELECT 사번 as employee_id, ENTE_DT, 출입시각, DR_NM, INOUT_GB,
                       CENTER, BU, TEAM, GROUP_A, PART
                FROM tag_data 
                WHERE ENTE_DT BETWEEN {prev_date_str} AND {target_date_str}
                ORDER BY 사번, 출입시각
            """
            tag_data = pd.read_sql_query(tag_query, conn)
            self.logger.info(f"  태그 데이터: {len(tag_data):,}건")
            
            # 2. 식사 데이터 로드 (실제 컬럼명 사용)
            meal_query = f"""
                SELECT 사번 as employee_id, 취식일시, 정산일, 식당명, 
                       식사구분명, 성명, 부서
                FROM meal_data
                WHERE DATE(정산일) BETWEEN '{prev_date}' AND '{target_date}'
            """
            meal_data = pd.read_sql_query(meal_query, conn)
            self.logger.info(f"  식사 데이터: {len(meal_data):,}건")
            
            # 3. Claim 데이터 로드 (실제 컬럼명 사용)
            claim_query = f"""
                SELECT 사번 as employee_id, 근무일, WORKSCHDTYPNM, 
                       근무시간, 시작, 종료, 성명, 부서, 직급
                FROM claim_data
                WHERE DATE(근무일) = '{target_date}'
            """
            claim_data = pd.read_sql_query(claim_query, conn)
            self.logger.info(f"  Claim 데이터: {len(claim_data):,}건")
            
            # 4. 장비 데이터 로드 (테이블이 있을 경우만)
            try:
                equipment_query = f"""
                    SELECT * FROM equipment_data
                    WHERE DATE(datetime) BETWEEN '{prev_date}' AND '{target_date}'
                """
                equipment_data = pd.read_sql_query(equipment_query, conn)
                self.logger.info(f"  장비 데이터: {len(equipment_data):,}건")
            except:
                equipment_data = pd.DataFrame()
                self.logger.info(f"  장비 데이터: 없음")
            
            # 5. 근태 데이터 로드 (테이블이 있을 경우만)
            try:
                attendance_query = f"""
                    SELECT * FROM attendance_data
                    WHERE DATE(work_date) = '{target_date}'
                """
                attendance_data = pd.read_sql_query(attendance_query, conn)
                self.logger.info(f"  근태 데이터: {len(attendance_data):,}건")
            except:
                attendance_data = pd.DataFrame()
                self.logger.info(f"  근태 데이터: 없음")
            
        finally:
            conn.close()
        
        # 캐시에 저장
        self.data_cache = {
            'tag_data': tag_data,
            'meal_data': meal_data,
            'claim_data': claim_data,
            'equipment_data': equipment_data,
            'attendance_data': attendance_data,
            'target_date': target_date
        }
        
        elapsed = time.time() - start_time
        self.logger.info(f"✅ 데이터 로드 완료: {elapsed:.2f}초")
        
        return self.data_cache
    
    def analyze_employee_batch(self, employee_id: str, target_date: date) -> Dict[str, Any]:
        """
        개별 직원 분석 (배치용 최적화)
        기존 execute_analysis와 호환되는 결과 반환
        """
        try:
            # 캐시된 데이터에서 직원 데이터 필터링
            if 'tag_data' not in self.data_cache:
                self.logger.error("데이터가 사전 로드되지 않았습니다.")
                return None
            
            # 1. 태그 데이터 필터링
            tag_data = self.data_cache['tag_data']
            # employee_id를 문자열로 변환하여 비교
            emp_tag_data = tag_data[tag_data['employee_id'].astype(str) == str(employee_id)].copy()
            
            if emp_tag_data.empty:
                return {
                    'employee_id': employee_id,
                    'analysis_date': target_date.isoformat(),
                    'status': 'no_data'
                }
            
            # 2. 식사 데이터 필터링
            meal_data = self.data_cache['meal_data']
            emp_meal_data = meal_data[meal_data['employee_id'].astype(str) == str(employee_id)].copy()
            
            # 3. Claim 데이터 필터링
            claim_data = self.data_cache['claim_data']
            emp_claim_data = claim_data[claim_data['employee_id'].astype(str) == str(employee_id)].copy()
            
            # 4. 장비 데이터 필터링
            equipment_data = self.data_cache.get('equipment_data', pd.DataFrame())
            if not equipment_data.empty:
                emp_equipment_data = equipment_data[equipment_data['employee_id'] == employee_id].copy()
            else:
                emp_equipment_data = pd.DataFrame()
            
            # 5. 근태 데이터 필터링
            attendance_data = self.data_cache.get('attendance_data', pd.DataFrame())
            if not attendance_data.empty:
                emp_attendance_data = attendance_data[attendance_data['employee_id'] == employee_id].copy()
            else:
                emp_attendance_data = pd.DataFrame()
            
            # 6. 간단한 분석 수행 (execute_analysis의 핵심 로직만)
            
            # 근무 시간 계산 (2교대 근무 고려)
            if not emp_tag_data.empty:
                try:
                    # ENTE_DT(날짜)와 출입시각(시간) 결합
                    emp_tag_data['datetime'] = emp_tag_data.apply(
                        lambda row: pd.to_datetime(f"{row['ENTE_DT']} {str(row['출입시각']).zfill(6)}", 
                                                  format='%Y%m%d %H%M%S', errors='coerce'),
                        axis=1
                    )
                    
                    # NaT 제거
                    emp_tag_data = emp_tag_data.dropna(subset=['datetime'])
                    
                    if not emp_tag_data.empty:
                        # 2교대 근무 시스템: target_date 기준으로 근무 시간 계산
                        target_start = pd.to_datetime(f"{target_date} 00:00:00")
                        target_end = pd.to_datetime(f"{target_date} 23:59:59")
                        
                        # 먼저 target_date의 태그만 필터링
                        day_tags = emp_tag_data[
                            (emp_tag_data['datetime'] >= target_start) & 
                            (emp_tag_data['datetime'] <= target_end)
                        ]
                        
                        if not day_tags.empty:
                            first_tag = day_tags['datetime'].min()
                            last_tag = day_tags['datetime'].max()
                            
                            # 야간 근무인 경우 다음날 오전 태그도 확인
                            if last_tag.hour >= 20:  # 야간 근무 가능성
                                next_day_start = target_end + pd.Timedelta(seconds=1)
                                next_day_end = next_day_start + pd.Timedelta(hours=12)
                                
                                next_day_tags = emp_tag_data[
                                    (emp_tag_data['datetime'] >= next_day_start) & 
                                    (emp_tag_data['datetime'] <= next_day_end)
                                ]
                                
                                if not next_day_tags.empty:
                                    last_tag = next_day_tags['datetime'].max()
                            
                            total_hours = (last_tag - first_tag).total_seconds() / 3600
                            # 최대 12시간으로 제한
                            total_hours = min(total_hours, 12)
                        else:
                            total_hours = 0
                            first_tag = None
                            last_tag = None
                    else:
                        total_hours = 0
                        first_tag = None
                        last_tag = None
                except Exception as e:
                    self.logger.warning(f"시간 계산 오류: {e}")
                    total_hours = 0
                    first_tag = None
                    last_tag = None
            else:
                total_hours = 0
                first_tag = None
                last_tag = None
            
            # Claim 데이터에서 예정 근무시간
            if not emp_claim_data.empty:
                # 근무시간 파싱 (예: "08:00~17:00" 형식)
                work_time_str = emp_claim_data.iloc[0].get('근무시간', '')
                try:
                    if '~' in work_time_str:
                        start_str, end_str = work_time_str.split('~')
                        # 시간 계산 로직 (간단히 8시간으로 가정)
                        scheduled_hours = 8
                    else:
                        scheduled_hours = 8
                except:
                    scheduled_hours = 8
                    
                work_type = emp_claim_data.iloc[0].get('WORKSCHDTYPNM', '일반근무')
            else:
                scheduled_hours = 8
                work_type = '일반근무'
            
            # 식사 횟수
            meal_count = len(emp_meal_data)
            
            # 실제 근무시간 추정 (간단한 로직)
            # 총 시간에서 식사시간(30분 * 횟수) 빼기
            actual_work_hours = max(0, total_hours - (meal_count * 0.5))
            
            # 효율성 계산
            if scheduled_hours > 0:
                efficiency_ratio = (actual_work_hours / scheduled_hours) * 100
            else:
                efficiency_ratio = 0
            
            # 활동 요약 (간단 버전)
            activity_summary = {
                'WORK': actual_work_hours * 60,  # 분 단위
                'MEAL': meal_count * 30,  # 식사당 30분 가정
                'REST': max(0, (total_hours - actual_work_hours - meal_count * 0.5) * 60)
            }
            
            # 결과 반환 (기존 execute_analysis와 호환되는 형식)
            return {
                'employee_id': employee_id,
                'analysis_date': target_date.isoformat(),
                'status': 'success',
                'work_start': first_tag.isoformat() if first_tag else None,
                'work_end': last_tag.isoformat() if last_tag else None,
                'work_time_analysis': {
                    'total_hours': total_hours,
                    'actual_work_hours': actual_work_hours,
                    'scheduled_hours': scheduled_hours,
                    'efficiency_ratio': efficiency_ratio
                },
                'meal_time_analysis': {
                    'total_meal_time': meal_count * 30,
                    'meal_count': meal_count
                },
                'activity_summary': activity_summary,
                'work_type': work_type,
                'tag_count': len(emp_tag_data),
                'attendance_hours': total_hours,  # 조직 분석에서 사용
                'meeting_time': 0,  # 간단 버전에서는 0
                'movement_time': 0,  # 간단 버전에서는 0
                'rest_time': activity_summary['REST'] / 60,  # 시간 단위
                'work_estimation_rate': efficiency_ratio,
                'data_reliability': 80 if len(emp_tag_data) > 10 else 50
            }
            
        except Exception as e:
            self.logger.error(f"직원 {employee_id} 분석 실패: {e}")
            return {
                'employee_id': employee_id,
                'analysis_date': target_date.isoformat(),
                'status': 'error',
                'error': str(e)
            }
    
    @staticmethod
    def _analyze_worker(args):
        """워커 프로세스에서 실행될 분석 함수"""
        processor, employee_id, target_date = args
        return processor.analyze_employee_batch(employee_id, target_date)
    
    def batch_analyze_employees(self, employee_ids: List[str], target_date: date) -> List[Dict[str, Any]]:
        """
        여러 직원을 병렬로 분석
        """
        self.logger.info(f"🚀 배치 분석 시작: {len(employee_ids)}명, {self.num_workers}개 워커")
        start_time = time.time()
        
        # 1. 데이터 사전 로드 (한 번만!)
        self.preload_data_for_date(target_date)
        
        # 2. 순차 처리 (테스트용) 또는 병렬 처리
        if self.num_workers == 1:
            # 순차 처리 (디버깅용)
            results = []
            for i, emp_id in enumerate(employee_ids):
                result = self.analyze_employee_batch(emp_id, target_date)
                results.append(result)
                if (i + 1) % 100 == 0:
                    elapsed = time.time() - start_time
                    rate = (i + 1) / elapsed
                    remaining = (len(employee_ids) - i - 1) / rate if rate > 0 else 0
                    self.logger.info(f"  진행: {i+1}/{len(employee_ids)} "
                                   f"({rate:.1f}명/초, 남은시간: {remaining/60:.1f}분)")
        else:
            # 실제 병렬 처리 구현
            # ThreadPool 사용 (데이터가 이미 메모리에 있으므로 I/O bound 작업)
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            results = []
            
            # ThreadPoolExecutor로 병렬 처리
            with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
                # 작업 제출
                future_to_emp = {
                    executor.submit(self.analyze_employee_batch, emp_id, target_date): emp_id 
                    for emp_id in employee_ids
                }
                
                # 결과 수집
                completed = 0
                for future in as_completed(future_to_emp):
                    emp_id = future_to_emp[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        self.logger.error(f"직원 {emp_id} 분석 실패: {e}")
                        results.append({
                            'employee_id': emp_id,
                            'analysis_date': target_date.isoformat(),
                            'status': 'error',
                            'error': str(e)
                        })
                    
                    completed += 1
                    # 진행 상황 표시
                    if completed % 100 == 0 or completed == len(employee_ids):
                        elapsed = time.time() - start_time
                        rate = completed / elapsed if elapsed > 0 else 0
                        remaining = (len(employee_ids) - completed) / rate if rate > 0 else 0
                        self.logger.info(f"  진행: {completed}/{len(employee_ids)} "
                                       f"({rate:.1f}명/초, 남은시간: {remaining/60:.1f}분)")
        
        elapsed = time.time() - start_time
        success_count = sum(1 for r in results if r.get('status') == 'success')
        
        self.logger.info(f"✅ 배치 분석 완료")
        self.logger.info(f"  - 총 직원: {len(employee_ids)}명")
        self.logger.info(f"  - 성공: {success_count}명")
        self.logger.info(f"  - 소요 시간: {elapsed:.2f}초")
        self.logger.info(f"  - 처리 속도: {len(employee_ids)/elapsed:.1f}명/초")
        
        return results
    
    def save_results_to_db(self, results: List[Dict[str, Any]]) -> int:
        """
        분석 결과를 DB에 저장
        기존 daily_analysis_results 테이블 사용
        """
        self.logger.info(f"💾 {len(results)}건 DB 저장 시작...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        saved_count = 0
        
        try:
            for result in results:
                if result.get('status') != 'success':
                    continue
                
                # 데이터 준비
                data = {
                    'employee_id': result['employee_id'],
                    'analysis_date': result['analysis_date'],
                    'work_start': result.get('work_start'),
                    'work_end': result.get('work_end'),
                    'total_hours': result['work_time_analysis']['total_hours'],
                    'actual_work_hours': result['work_time_analysis']['actual_work_hours'],
                    'claimed_work_hours': result['work_time_analysis']['scheduled_hours'],
                    'efficiency_ratio': result['work_time_analysis']['efficiency_ratio'],
                    'meal_count': result['meal_time_analysis']['meal_count'],
                    'tag_count': result.get('tag_count', 0),
                    'updated_at': datetime.now().isoformat()
                }
                
                # UPSERT 쿼리
                cursor.execute("""
                    INSERT OR REPLACE INTO daily_analysis_results 
                    (employee_id, analysis_date, work_start, work_end,
                     total_hours, actual_work_hours, claimed_work_hours,
                     efficiency_ratio, meal_count, tag_count, updated_at)
                    VALUES 
                    (:employee_id, :analysis_date, :work_start, :work_end,
                     :total_hours, :actual_work_hours, :claimed_work_hours,
                     :efficiency_ratio, :meal_count, :tag_count, :updated_at)
                """, data)
                
                saved_count += 1
                
                if saved_count % 100 == 0:
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


# 테스트 함수
def test_simple_batch_processor():
    """간단한 테스트"""
    logging.basicConfig(level=logging.INFO)
    
    processor = SimpleBatchProcessor(num_workers=1)
    
    # 테스트할 직원 ID (예시)
    test_employees = ['20170124', '20170125', '20170126']
    test_date = date(2025, 6, 15)
    
    # 분석 실행
    results = processor.batch_analyze_employees(test_employees, test_date)
    
    # 결과 출력
    for result in results:
        if result.get('status') == 'success':
            print(f"\n직원 {result['employee_id']}:")
            print(f"  근무시간: {result['work_time_analysis']['actual_work_hours']:.1f}시간")
            print(f"  효율성: {result['work_time_analysis']['efficiency_ratio']:.1f}%")
            print(f"  태그 수: {result.get('tag_count', 0)}개")
    
    # DB 저장 테스트
    saved = processor.save_results_to_db(results)
    print(f"\nDB 저장: {saved}건")


if __name__ == "__main__":
    test_simple_batch_processor()