#!/usr/bin/env python3
"""
대규모 배치 분석 실행 스크립트
5000명 × 30일 데이터를 병렬로 처리하여 별도 DB에 저장
"""

import os
import sys
from pathlib import Path
import sqlite3
from datetime import datetime, timedelta, date
import pandas as pd
import numpy as np
from multiprocessing import Pool, cpu_count, Manager
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import logging
import time
from typing import List, Tuple, Dict, Optional
import argparse

# 프로젝트 경로 설정
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.database import get_database_manager
from src.analysis.individual_analyzer import IndividualAnalyzer
from src.data_processing import PickleManager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('batch_analysis.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BatchAnalysisProcessor:
    """대규모 배치 분석 처리기"""
    
    def __init__(self, 
                 source_db_path: str = None,
                 target_db_path: str = None,
                 num_workers: int = None):
        """
        Args:
            source_db_path: 원본 데이터 DB 경로
            target_db_path: 분석 결과 저장 DB 경로
            num_workers: 병렬 처리 워커 수
        """
        self.source_db = source_db_path or str(project_root / 'data' / 'sambio.db')
        self.target_db = target_db_path or str(project_root / 'data' / 'sambio_analytics.db')
        self.num_workers = num_workers or min(cpu_count() - 1, 8)
        self.batch_size = 50  # 한 배치당 처리할 작업 수
        
        # 분석 결과 DB 초기화
        self._init_analytics_db()
        
        logger.info(f"BatchAnalysisProcessor 초기화 완료")
        logger.info(f"Source DB: {self.source_db}")
        logger.info(f"Target DB: {self.target_db}")
        logger.info(f"Workers: {self.num_workers}")
    
    def _init_analytics_db(self):
        """분석 결과 저장용 DB 초기화"""
        conn = sqlite3.connect(self.target_db)
        cursor = conn.cursor()
        
        # 일별 개인 분석 결과 테이블
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            employee_name TEXT,
            analysis_date DATE NOT NULL,
            
            -- 조직 정보
            center_id TEXT,
            center_name TEXT,
            team_id TEXT,
            team_name TEXT,
            group_id TEXT,
            group_name TEXT,
            job_grade TEXT,
            
            -- 근무 시간 분석
            total_hours REAL,
            work_hours REAL,
            focused_work_hours REAL,
            meeting_hours REAL,
            break_hours REAL,
            meal_hours REAL,
            movement_hours REAL,
            idle_hours REAL,
            
            -- 효율성 지표
            efficiency_ratio REAL,
            focus_ratio REAL,
            productivity_score REAL,
            
            -- 식사 분석
            breakfast_taken INTEGER DEFAULT 0,
            lunch_taken INTEGER DEFAULT 0,
            dinner_taken INTEGER DEFAULT 0,
            midnight_meal_taken INTEGER DEFAULT 0,
            
            -- 패턴 분석 (JSON)
            peak_hours TEXT,
            activity_distribution TEXT,
            location_patterns TEXT,
            hourly_efficiency TEXT,
            
            -- Claim 비교
            claim_hours REAL,
            claim_vs_actual_diff REAL,
            
            -- 메타 정보
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            analysis_version TEXT DEFAULT '1.0.0',
            processing_time_ms INTEGER,
            
            UNIQUE(employee_id, analysis_date)
        )""")
        
        # 팀별 일일 집계
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_daily_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT NOT NULL,
            team_name TEXT,
            center_id TEXT,
            center_name TEXT,
            analysis_date DATE NOT NULL,
            
            -- 통계
            total_employees INTEGER,
            analyzed_employees INTEGER,
            avg_efficiency_ratio REAL,
            avg_work_hours REAL,
            avg_focus_ratio REAL,
            avg_productivity_score REAL,
            
            -- 직급별 분포 (JSON)
            grade_distribution TEXT,
            efficiency_by_grade TEXT,
            
            -- 시간대별 패턴 (JSON)
            hourly_patterns TEXT,
            
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            UNIQUE(team_id, analysis_date)
        )""")
        
        # 센터별 일일 집계
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS center_daily_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            center_id TEXT NOT NULL,
            center_name TEXT,
            analysis_date DATE NOT NULL,
            
            -- 통계
            total_employees INTEGER,
            analyzed_employees INTEGER,
            total_teams INTEGER,
            avg_efficiency_ratio REAL,
            avg_work_hours REAL,
            avg_focus_ratio REAL,
            
            -- 팀별 분포 (JSON)
            team_performance TEXT,
            grade_distribution TEXT,
            
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            UNIQUE(center_id, analysis_date)
        )""")
        
        # 처리 로그
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS processing_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            total_items INTEGER,
            processed_items INTEGER,
            failed_items INTEGER,
            status TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        
        # 인덱스 생성
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_daily_employee_date 
        ON daily_analysis(employee_id, analysis_date)
        """)
        
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_daily_date 
        ON daily_analysis(analysis_date)
        """)
        
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_daily_center 
        ON daily_analysis(center_id, analysis_date)
        """)
        
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_daily_team 
        ON daily_analysis(team_id, analysis_date)
        """)
        
        conn.commit()
        conn.close()
        
        logger.info(f"Analytics DB 초기화 완료: {self.target_db}")
    
    def get_analysis_targets(self, 
                           start_date: date,
                           end_date: date,
                           use_claim_filter: bool = True) -> List[Tuple[str, date]]:
        """
        분석 대상 추출 (Claim 데이터 기반 필터링)
        
        Returns:
            [(employee_id, work_date), ...]
        """
        conn = sqlite3.connect(self.source_db)
        
        if use_claim_filter:
            # Claim 데이터가 있는 날짜만
            query = """
            SELECT DISTINCT 
                ec.employee_id,
                ec.work_date
            FROM employee_claims ec
            INNER JOIN employees e ON ec.employee_id = e.employee_id
            WHERE ec.work_date BETWEEN ? AND ?
                AND ec.total_hours > 0
            ORDER BY ec.employee_id, ec.work_date
            """
        else:
            # 모든 직원의 모든 날짜
            query = """
            SELECT 
                e.employee_id,
                d.date as work_date
            FROM employees e
            CROSS JOIN (
                SELECT DATE(?, '+' || n || ' days') as date
                FROM (
                    SELECT ROW_NUMBER() OVER () - 1 as n
                    FROM employees
                    LIMIT (julianday(?) - julianday(?) + 1)
                )
            ) d
            ORDER BY e.employee_id, d.date
            """
        
        df = pd.read_sql_query(
            query,
            conn,
            params=(start_date.isoformat(), end_date.isoformat()) if use_claim_filter 
                   else (start_date.isoformat(), end_date.isoformat(), start_date.isoformat())
        )
        
        conn.close()
        
        targets = [(row['employee_id'], pd.to_datetime(row['work_date']).date()) 
                  for _, row in df.iterrows()]
        
        logger.info(f"분석 대상 추출 완료: {len(targets)}건")
        return targets
    
    def analyze_single_task(self, task: Tuple[str, date]) -> Optional[Dict]:
        """
        단일 작업 분석 (employee_id, date)
        
        Returns:
            분석 결과 딕셔너리 또는 None
        """
        employee_id, work_date = task
        start_time = time.time()
        
        try:
            # DB 매니저와 분석기 초기화 (프로세스별)
            from src.database import DatabaseManager
            db_manager = DatabaseManager(self.source_db)
            analyzer = IndividualAnalyzer(db_manager, None)
            
            # 분석 실행
            result = analyzer.analyze_employee_optimized(
                employee_id=employee_id,
                start_date=work_date,
                end_date=work_date
            )
            
            if not result or result.empty:
                return None
            
            # 결과 변환
            row = result.iloc[0]
            
            # 직원 정보 조회
            emp_info = db_manager.execute_query("""
                SELECT employee_name, center_id, center_name, 
                       team_id, team_name, group_id, group_name, job_grade
                FROM employees
                WHERE employee_id = ?
            """, (employee_id,), fetch_one=True)
            
            # Claim 데이터 조회
            claim_data = db_manager.execute_query("""
                SELECT total_hours as claim_hours
                FROM employee_claims
                WHERE employee_id = ? AND work_date = ?
            """, (employee_id, work_date.isoformat()), fetch_one=True)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            return {
                'employee_id': employee_id,
                'employee_name': emp_info['employee_name'] if emp_info else None,
                'analysis_date': work_date.isoformat(),
                
                # 조직 정보
                'center_id': emp_info['center_id'] if emp_info else None,
                'center_name': emp_info['center_name'] if emp_info else None,
                'team_id': emp_info['team_id'] if emp_info else None,
                'team_name': emp_info['team_name'] if emp_info else None,
                'group_id': emp_info['group_id'] if emp_info else None,
                'group_name': emp_info['group_name'] if emp_info else None,
                'job_grade': emp_info['job_grade'] if emp_info else None,
                
                # 시간 분석
                'total_hours': float(row.get('total_hours', 0)),
                'work_hours': float(row.get('work_hours', 0)),
                'focused_work_hours': float(row.get('focused_work_hours', 0)),
                'meeting_hours': float(row.get('meeting_hours', 0)),
                'break_hours': float(row.get('break_hours', 0)),
                'meal_hours': float(row.get('meal_hours', 0)),
                'movement_hours': float(row.get('movement_hours', 0)),
                'idle_hours': float(row.get('idle_hours', 0)),
                
                # 효율성
                'efficiency_ratio': float(row.get('efficiency_ratio', 0)),
                'focus_ratio': float(row.get('focus_ratio', 0)),
                'productivity_score': float(row.get('productivity_score', 0)),
                
                # 식사
                'breakfast_taken': 1 if row.get('breakfast_taken') else 0,
                'lunch_taken': 1 if row.get('lunch_taken') else 0,
                'dinner_taken': 1 if row.get('dinner_taken') else 0,
                'midnight_meal_taken': 1 if row.get('midnight_meal_taken') else 0,
                
                # 패턴 (JSON)
                'peak_hours': json.dumps(row.get('peak_hours', [])),
                'activity_distribution': json.dumps(row.get('activity_distribution', {})),
                'location_patterns': json.dumps(row.get('location_patterns', {})),
                'hourly_efficiency': json.dumps(row.get('hourly_efficiency', {})),
                
                # Claim 비교
                'claim_hours': float(claim_data['claim_hours']) if claim_data else 0,
                'claim_vs_actual_diff': float(row.get('total_hours', 0)) - float(claim_data['claim_hours']) if claim_data else 0,
                
                # 메타
                'processing_time_ms': processing_time
            }
            
        except Exception as e:
            logger.error(f"분석 실패 - {employee_id}, {work_date}: {e}")
            return None
    
    def process_batch(self, batch: List[Tuple[str, date]]) -> List[Dict]:
        """배치 처리"""
        results = []
        for task in batch:
            result = self.analyze_single_task(task)
            if result:
                results.append(result)
        return results
    
    def save_results(self, results: List[Dict]):
        """결과 저장"""
        if not results:
            return
        
        conn = sqlite3.connect(self.target_db)
        cursor = conn.cursor()
        
        for result in results:
            try:
                cursor.execute("""
                INSERT OR REPLACE INTO daily_analysis (
                    employee_id, employee_name, analysis_date,
                    center_id, center_name, team_id, team_name, 
                    group_id, group_name, job_grade,
                    total_hours, work_hours, focused_work_hours,
                    meeting_hours, break_hours, meal_hours,
                    movement_hours, idle_hours,
                    efficiency_ratio, focus_ratio, productivity_score,
                    breakfast_taken, lunch_taken, dinner_taken, midnight_meal_taken,
                    peak_hours, activity_distribution, location_patterns, hourly_efficiency,
                    claim_hours, claim_vs_actual_diff,
                    processing_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, tuple(result.values()))
            except Exception as e:
                logger.error(f"저장 실패: {e}")
        
        conn.commit()
        conn.close()
    
    def run_parallel_analysis(self, 
                            start_date: date,
                            end_date: date,
                            use_claim_filter: bool = True,
                            resume_from: int = 0):
        """
        병렬 분석 실행
        
        Args:
            start_date: 시작 날짜
            end_date: 종료 날짜  
            use_claim_filter: Claim 데이터 필터링 사용 여부
            resume_from: 재시작 위치 (실패 시 복구용)
        """
        batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        logger.info(f"배치 분석 시작 - ID: {batch_id}")
        
        # 분석 대상 추출
        targets = self.get_analysis_targets(start_date, end_date, use_claim_filter)
        
        if resume_from > 0:
            targets = targets[resume_from:]
            logger.info(f"재시작 위치: {resume_from}")
        
        total_targets = len(targets)
        logger.info(f"총 분석 대상: {total_targets}건")
        
        # 배치 분할
        batches = [targets[i:i + self.batch_size] 
                  for i in range(0, len(targets), self.batch_size)]
        total_batches = len(batches)
        
        # 진행률 추적
        start_time = datetime.now()
        completed = 0
        failed = 0
        
        # 처리 로그 시작
        self._log_processing_start(batch_id, total_targets)
        
        try:
            with ProcessPoolExecutor(max_workers=self.num_workers) as executor:
                futures = {executor.submit(self.process_batch, batch): i 
                          for i, batch in enumerate(batches)}
                
                for future in as_completed(futures):
                    batch_idx = futures[future]
                    
                    try:
                        results = future.result(timeout=300)  # 5분 타임아웃
                        self.save_results(results)
                        completed += len(results)
                        
                        # 진행률 표시
                        elapsed = (datetime.now() - start_time).total_seconds()
                        rate = completed / elapsed if elapsed > 0 else 0
                        remaining = total_targets - completed
                        eta_seconds = remaining / rate if rate > 0 else 0
                        
                        progress_pct = (batch_idx + 1) * 100 / total_batches
                        
                        logger.info(f"""
                        배치 {batch_idx + 1}/{total_batches} 완료 ({progress_pct:.1f}%)
                        처리: {completed}/{total_targets} ({completed*100/total_targets:.1f}%)
                        속도: {rate:.1f} items/sec
                        경과: {timedelta(seconds=int(elapsed))}
                        예상 완료: {timedelta(seconds=int(eta_seconds))}
                        """)
                        
                    except Exception as e:
                        logger.error(f"배치 {batch_idx} 처리 실패: {e}")
                        failed += self.batch_size
            
            # 집계 생성
            self.generate_aggregations(start_date, end_date)
            
            # 처리 로그 완료
            self._log_processing_end(batch_id, completed, failed, "completed")
            
            logger.info(f"""
            ========================================
            배치 분석 완료!
            총 처리: {completed}/{total_targets}
            실패: {failed}
            소요 시간: {datetime.now() - start_time}
            ========================================
            """)
            
        except Exception as e:
            logger.error(f"배치 처리 중 오류: {e}")
            self._log_processing_end(batch_id, completed, failed, "failed", str(e))
            raise
    
    def generate_aggregations(self, start_date: date, end_date: date):
        """집계 테이블 생성"""
        logger.info("집계 데이터 생성 시작...")
        
        conn = sqlite3.connect(self.target_db)
        cursor = conn.cursor()
        
        # 팀별 집계
        cursor.execute("""
        INSERT OR REPLACE INTO team_daily_summary (
            team_id, team_name, center_id, center_name, analysis_date,
            total_employees, analyzed_employees,
            avg_efficiency_ratio, avg_work_hours, avg_focus_ratio, avg_productivity_score
        )
        SELECT 
            team_id, 
            MAX(team_name) as team_name,
            MAX(center_id) as center_id,
            MAX(center_name) as center_name,
            analysis_date,
            COUNT(DISTINCT employee_id) as total_employees,
            COUNT(DISTINCT CASE WHEN total_hours > 0 THEN employee_id END) as analyzed_employees,
            AVG(efficiency_ratio) as avg_efficiency_ratio,
            AVG(work_hours) as avg_work_hours,
            AVG(focus_ratio) as avg_focus_ratio,
            AVG(productivity_score) as avg_productivity_score
        FROM daily_analysis
        WHERE analysis_date BETWEEN ? AND ?
            AND team_id IS NOT NULL
        GROUP BY team_id, analysis_date
        """, (start_date.isoformat(), end_date.isoformat()))
        
        # 센터별 집계
        cursor.execute("""
        INSERT OR REPLACE INTO center_daily_summary (
            center_id, center_name, analysis_date,
            total_employees, analyzed_employees, total_teams,
            avg_efficiency_ratio, avg_work_hours, avg_focus_ratio
        )
        SELECT 
            center_id,
            MAX(center_name) as center_name,
            analysis_date,
            COUNT(DISTINCT employee_id) as total_employees,
            COUNT(DISTINCT CASE WHEN total_hours > 0 THEN employee_id END) as analyzed_employees,
            COUNT(DISTINCT team_id) as total_teams,
            AVG(efficiency_ratio) as avg_efficiency_ratio,
            AVG(work_hours) as avg_work_hours,
            AVG(focus_ratio) as avg_focus_ratio
        FROM daily_analysis  
        WHERE analysis_date BETWEEN ? AND ?
            AND center_id IS NOT NULL
        GROUP BY center_id, analysis_date
        """, (start_date.isoformat(), end_date.isoformat()))
        
        conn.commit()
        conn.close()
        
        logger.info("집계 데이터 생성 완료")
    
    def _log_processing_start(self, batch_id: str, total_items: int):
        """처리 시작 로그"""
        conn = sqlite3.connect(self.target_db)
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO processing_log (batch_id, start_time, total_items, status)
        VALUES (?, ?, ?, 'running')
        """, (batch_id, datetime.now(), total_items))
        conn.commit()
        conn.close()
    
    def _log_processing_end(self, batch_id: str, processed: int, failed: int, 
                          status: str, error: str = None):
        """처리 종료 로그"""
        conn = sqlite3.connect(self.target_db)
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE processing_log 
        SET end_time = ?, processed_items = ?, failed_items = ?, 
            status = ?, error_message = ?
        WHERE batch_id = ?
        """, (datetime.now(), processed, failed, status, error, batch_id))
        conn.commit()
        conn.close()


def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description='대규모 배치 분석 실행')
    parser.add_argument('--start-date', type=str, required=True,
                       help='시작 날짜 (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, required=True,
                       help='종료 날짜 (YYYY-MM-DD)')
    parser.add_argument('--workers', type=int, default=8,
                       help='병렬 처리 워커 수 (기본: 8)')
    parser.add_argument('--no-claim-filter', action='store_true',
                       help='Claim 필터링 비활성화 (모든 날짜 분석)')
    parser.add_argument('--resume-from', type=int, default=0,
                       help='재시작 위치 (실패 시 복구용)')
    
    args = parser.parse_args()
    
    # 날짜 파싱
    start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
    end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
    
    # 프로세서 초기화 및 실행
    processor = BatchAnalysisProcessor(num_workers=args.workers)
    
    try:
        processor.run_parallel_analysis(
            start_date=start_date,
            end_date=end_date,
            use_claim_filter=not args.no_claim_filter,
            resume_from=args.resume_from
        )
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
    except Exception as e:
        logger.error(f"실행 중 오류 발생: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()