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
    청크 단위로 직원들을 분석
    """
    # 임시 파일에서 데이터 로드
    with open(temp_file_path, 'rb') as f:
        data_cache = pickle.load(f)
    
    results = []
    
    for employee_id in employee_ids:
        try:
            # 직원 데이터 필터링
            tag_data = data_cache['tag_data']
            emp_tag_data = tag_data[tag_data['employee_id'].astype(str) == str(employee_id)].copy()
            
            if emp_tag_data.empty:
                results.append({
                    'employee_id': employee_id,
                    'analysis_date': target_date.isoformat(),
                    'status': 'no_data'
                })
                continue
            
            meal_data = data_cache['meal_data']
            emp_meal_data = meal_data[meal_data['employee_id'].astype(str) == str(employee_id)].copy()
            
            claim_data = data_cache['claim_data']
            emp_claim_data = claim_data[claim_data['employee_id'].astype(str) == str(employee_id)].copy()
            
            # 근무 시간 계산 (2교대 근무 고려)
            if not emp_tag_data.empty:
                try:
                    emp_tag_data['datetime'] = emp_tag_data.apply(
                        lambda row: pd.to_datetime(f"{row['ENTE_DT']} {str(row['출입시각']).zfill(6)}", 
                                                  format='%Y%m%d %H%M%S', errors='coerce'),
                        axis=1
                    )
                    
                    emp_tag_data = emp_tag_data.dropna(subset=['datetime'])
                    
                    if not emp_tag_data.empty:
                        # 2교대 근무 시스템: target_date 기준으로 근무 시간 계산
                        # 주간근무: target_date 08:00 ~ 20:00
                        # 야간근무: target_date 20:00 ~ target_date+1 08:00
                        
                        target_date_str = target_date.strftime('%Y%m%d')
                        
                        # 해당 날짜에 속하는 태그만 필터링
                        # 주간: target_date의 태그
                        # 야간: target_date 20시 이후 + target_date+1 08시 이전
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
                                next_day_end = next_day_start + pd.Timedelta(hours=12)  # 다음날 정오까지
                                
                                next_day_tags = emp_tag_data[
                                    (emp_tag_data['datetime'] >= next_day_start) & 
                                    (emp_tag_data['datetime'] <= next_day_end)
                                ]
                                
                                if not next_day_tags.empty:
                                    last_tag = next_day_tags['datetime'].max()
                            
                            total_hours = (last_tag - first_tag).total_seconds() / 3600
                            
                            # 최대 12시간으로 제한 (2교대 근무)
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
                    total_hours = 0
                    first_tag = None
                    last_tag = None
            else:
                total_hours = 0
                first_tag = None
                last_tag = None
            
            # Claim 데이터에서 예정 근무시간
            if not emp_claim_data.empty:
                scheduled_hours = 8  # 간단히 8시간으로 가정
                work_type = emp_claim_data.iloc[0].get('WORKSCHDTYPNM', '일반근무')
            else:
                scheduled_hours = 8
                work_type = '일반근무'
            
            # 식사 횟수
            meal_count = len(emp_meal_data)
            
            # 실제 근무시간 추정
            actual_work_hours = max(0, total_hours - (meal_count * 0.5))
            
            # 효율성 계산
            efficiency_ratio = (actual_work_hours / scheduled_hours * 100) if scheduled_hours > 0 else 0
            
            # 결과 반환
            results.append({
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
                'work_type': work_type,
                'tag_count': len(emp_tag_data),
                'attendance_hours': total_hours,
                'meeting_time': 0,
                'movement_time': 0,
                'rest_time': max(0, (total_hours - actual_work_hours - meal_count * 0.5) * 60) / 60,
                'work_estimation_rate': efficiency_ratio,
                'data_reliability': 80 if len(emp_tag_data) > 10 else 50
            })
            
        except Exception as e:
            results.append({
                'employee_id': employee_id,
                'analysis_date': target_date.isoformat(),
                'status': 'error',
                'error': str(e)
            })
    
    return results