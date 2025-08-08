#!/usr/bin/env python3
"""
Claim 데이터 기반 Mock 분석 DB 생성 스크립트
실제 분석 전에 UI 개발을 위한 테스트 데이터 생성
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import json
import random
from pathlib import Path
import sys
import logging

# 프로젝트 경로 설정
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.database import get_database_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockAnalyticsGenerator:
    """Mock 분석 데이터 생성기"""
    
    def __init__(self, source_db_path: str = None, target_db_path: str = None):
        self.source_db = source_db_path or str(project_root / 'data' / 'sambio.db')
        self.target_db = target_db_path or str(project_root / 'data' / 'sambio_analytics_mock.db')
        
        # 효율성 분포 설정 (현실적인 분포)
        self.efficiency_dist = {
            'Lv.1': {'mean': 85, 'std': 8},   # 사원
            'Lv.2': {'mean': 88, 'std': 7},   # 대리
            'Lv.3': {'mean': 90, 'std': 6},   # 과장
            'Lv.4': {'mean': 92, 'std': 5},   # 부장
            '경영진': {'mean': 95, 'std': 3}   # 경영진
        }
        
        logger.info(f"MockAnalyticsGenerator 초기화")
        logger.info(f"Source DB: {self.source_db}")
        logger.info(f"Target DB: {self.target_db}")
    
    def init_mock_db(self):
        """Mock DB 초기화 (실제 분석 DB와 동일한 스키마)"""
        conn = sqlite3.connect(self.target_db)
        cursor = conn.cursor()
        
        # 기존 테이블 삭제
        cursor.execute("DROP TABLE IF EXISTS daily_analysis")
        cursor.execute("DROP TABLE IF EXISTS team_daily_summary")
        cursor.execute("DROP TABLE IF EXISTS center_daily_summary")
        
        # daily_analysis 테이블
        cursor.execute("""
        CREATE TABLE daily_analysis (
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
            analysis_version TEXT DEFAULT '1.0.0-mock',
            processing_time_ms INTEGER,
            
            UNIQUE(employee_id, analysis_date)
        )""")
        
        # team_daily_summary 테이블
        cursor.execute("""
        CREATE TABLE team_daily_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT NOT NULL,
            team_name TEXT,
            center_id TEXT,
            center_name TEXT,
            analysis_date DATE NOT NULL,
            
            total_employees INTEGER,
            analyzed_employees INTEGER,
            avg_efficiency_ratio REAL,
            avg_work_hours REAL,
            avg_focus_ratio REAL,
            avg_productivity_score REAL,
            
            grade_distribution TEXT,
            efficiency_by_grade TEXT,
            hourly_patterns TEXT,
            
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            UNIQUE(team_id, analysis_date)
        )""")
        
        # center_daily_summary 테이블
        cursor.execute("""
        CREATE TABLE center_daily_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            center_id TEXT NOT NULL,
            center_name TEXT,
            analysis_date DATE NOT NULL,
            
            total_employees INTEGER,
            analyzed_employees INTEGER,
            total_teams INTEGER,
            avg_efficiency_ratio REAL,
            avg_work_hours REAL,
            avg_focus_ratio REAL,
            
            team_performance TEXT,
            grade_distribution TEXT,
            
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            UNIQUE(center_id, analysis_date)
        )""")
        
        # 인덱스 생성
        cursor.execute("CREATE INDEX idx_mock_daily_employee_date ON daily_analysis(employee_id, analysis_date)")
        cursor.execute("CREATE INDEX idx_mock_daily_date ON daily_analysis(analysis_date)")
        cursor.execute("CREATE INDEX idx_mock_daily_center ON daily_analysis(center_id, analysis_date)")
        cursor.execute("CREATE INDEX idx_mock_daily_team ON daily_analysis(team_id, analysis_date)")
        
        conn.commit()
        conn.close()
        
        logger.info("Mock DB 초기화 완료")
    
    def get_claim_based_targets(self) -> pd.DataFrame:
        """Claim 데이터 기반 대상 추출"""
        conn = sqlite3.connect(self.source_db)
        
        # Claim 데이터와 직원 정보 조인
        query = """
        SELECT DISTINCT
            ec.employee_id,
            e.employee_name,
            ec.work_date,
            ec.total_hours as claim_hours,
            e.center_id,
            e.center_name,
            e.team_id,
            e.team_name,
            e.group_id,
            e.group_name,
            e.job_grade
        FROM employee_claims ec
        INNER JOIN employees e ON ec.employee_id = e.employee_id
        WHERE ec.total_hours > 0
        ORDER BY ec.work_date, ec.employee_id
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        logger.info(f"Claim 기반 대상 추출: {len(df)}건")
        return df
    
    def generate_mock_metrics(self, row: pd.Series) -> dict:
        """Mock 메트릭 생성 (현실적인 패턴)"""
        
        # 직급별 효율성 기본값
        grade = row.get('job_grade', 'Lv.2')
        if grade not in self.efficiency_dist:
            grade = 'Lv.2'
        
        # 효율성 생성 (정규분포)
        base_efficiency = np.random.normal(
            self.efficiency_dist[grade]['mean'],
            self.efficiency_dist[grade]['std']
        )
        
        # 요일별 변동 (월요일 낮음, 수요일 높음)
        work_date = pd.to_datetime(row['work_date'])
        weekday = work_date.weekday()
        weekday_adjustment = [0.95, 1.0, 1.05, 1.02, 0.98, 0.9, 0.85][weekday]
        
        efficiency_ratio = np.clip(base_efficiency * weekday_adjustment, 60, 100)
        
        # Claim 시간 기반 실제 시간 계산
        claim_hours = float(row.get('claim_hours', 8))
        
        # 실제 시간은 Claim과 약간의 차이 (±2시간)
        actual_variation = np.random.normal(0, 0.5)
        total_hours = np.clip(claim_hours + actual_variation, 4, 14)
        
        # 근무 시간 비율
        work_ratio = efficiency_ratio / 100
        work_hours = total_hours * work_ratio
        
        # 세부 시간 분배
        focused_work_hours = work_hours * np.random.uniform(0.5, 0.7)
        meeting_hours = work_hours * np.random.uniform(0.1, 0.3)
        
        # 식사 및 휴식
        meal_hours = np.random.uniform(1.5, 2.5)
        break_hours = np.random.uniform(0.5, 1.5)
        movement_hours = np.random.uniform(0.3, 0.8)
        idle_hours = max(0, total_hours - work_hours - meal_hours - break_hours - movement_hours)
        
        # 집중도 및 생산성
        focus_ratio = (focused_work_hours / work_hours * 100) if work_hours > 0 else 0
        productivity_score = efficiency_ratio * (focus_ratio / 100) * np.random.uniform(0.9, 1.1)
        
        # 식사 패턴 (현실적)
        breakfast_taken = 1 if np.random.random() < 0.3 else 0  # 30% 확률
        lunch_taken = 1 if np.random.random() < 0.95 else 0     # 95% 확률
        dinner_taken = 1 if total_hours > 10 and np.random.random() < 0.7 else 0
        midnight_meal_taken = 1 if row.get('team_name', '').startswith('P2') and np.random.random() < 0.2 else 0
        
        # 피크 시간대 (Mock)
        peak_hours = ["09:00-11:00", "14:00-16:00"] if weekday < 5 else ["10:00-12:00"]
        
        # 활동 분포 (Mock)
        activity_distribution = {
            "WORK": round(work_hours, 1),
            "FOCUSED_WORK": round(focused_work_hours, 1),
            "MEETING": round(meeting_hours, 1),
            "BREAK": round(break_hours, 1),
            "MEAL": round(meal_hours, 1),
            "MOVEMENT": round(movement_hours, 1),
            "IDLE": round(idle_hours, 1)
        }
        
        # 위치 패턴 (Mock)
        location_patterns = {
            "OFFICE": round(work_hours * 0.7, 1),
            "MEETING_ROOM": round(meeting_hours, 1),
            "CAFETERIA": round(meal_hours, 1),
            "OTHER": round(movement_hours, 1)
        }
        
        # 시간대별 효율성 (Mock)
        hourly_efficiency = {}
        for hour in range(8, 20):
            if hour < 12:
                hourly_efficiency[f"{hour:02d}:00"] = round(efficiency_ratio * np.random.uniform(0.8, 1.1), 1)
            else:
                hourly_efficiency[f"{hour:02d}:00"] = round(efficiency_ratio * np.random.uniform(0.7, 1.0), 1)
        
        return {
            'total_hours': round(total_hours, 2),
            'work_hours': round(work_hours, 2),
            'focused_work_hours': round(focused_work_hours, 2),
            'meeting_hours': round(meeting_hours, 2),
            'break_hours': round(break_hours, 2),
            'meal_hours': round(meal_hours, 2),
            'movement_hours': round(movement_hours, 2),
            'idle_hours': round(idle_hours, 2),
            'efficiency_ratio': round(efficiency_ratio, 1),
            'focus_ratio': round(focus_ratio, 1),
            'productivity_score': round(productivity_score, 1),
            'breakfast_taken': breakfast_taken,
            'lunch_taken': lunch_taken,
            'dinner_taken': dinner_taken,
            'midnight_meal_taken': midnight_meal_taken,
            'peak_hours': json.dumps(peak_hours),
            'activity_distribution': json.dumps(activity_distribution),
            'location_patterns': json.dumps(location_patterns),
            'hourly_efficiency': json.dumps(hourly_efficiency),
            'claim_vs_actual_diff': round(total_hours - claim_hours, 2),
            'processing_time_ms': np.random.randint(800, 1200)
        }
    
    def generate_mock_data(self, limit: int = None, sample_rate: float = 1.0):
        """Mock 데이터 생성 및 저장"""
        
        # Claim 기반 대상 추출
        targets = self.get_claim_based_targets()
        
        # 샘플링 (빠른 테스트용)
        if sample_rate < 1.0:
            targets = targets.sample(frac=sample_rate)
        
        if limit:
            targets = targets.head(limit)
        
        logger.info(f"Mock 데이터 생성 시작: {len(targets)}건")
        
        # DB 연결
        conn = sqlite3.connect(self.target_db)
        cursor = conn.cursor()
        
        # 진행률 추적
        total = len(targets)
        batch_size = 1000
        
        for i in range(0, total, batch_size):
            batch = targets.iloc[i:i+batch_size]
            records = []
            
            for _, row in batch.iterrows():
                # Mock 메트릭 생성
                metrics = self.generate_mock_metrics(row)
                
                # 레코드 생성
                record = {
                    'employee_id': row['employee_id'],
                    'employee_name': row['employee_name'],
                    'analysis_date': row['work_date'],
                    'center_id': row.get('center_id'),
                    'center_name': row.get('center_name'),
                    'team_id': row.get('team_id'),
                    'team_name': row.get('team_name'),
                    'group_id': row.get('group_id'),
                    'group_name': row.get('group_name'),
                    'job_grade': row.get('job_grade'),
                    'claim_hours': float(row.get('claim_hours', 8)),
                    **metrics
                }
                records.append(record)
            
            # 배치 저장
            for record in records:
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
                    claim_hours, claim_vs_actual_diff, processing_time_ms
                ) VALUES (
                    :employee_id, :employee_name, :analysis_date,
                    :center_id, :center_name, :team_id, :team_name,
                    :group_id, :group_name, :job_grade,
                    :total_hours, :work_hours, :focused_work_hours,
                    :meeting_hours, :break_hours, :meal_hours,
                    :movement_hours, :idle_hours,
                    :efficiency_ratio, :focus_ratio, :productivity_score,
                    :breakfast_taken, :lunch_taken, :dinner_taken, :midnight_meal_taken,
                    :peak_hours, :activity_distribution, :location_patterns, :hourly_efficiency,
                    :claim_hours, :claim_vs_actual_diff, :processing_time_ms
                )
                """, record)
            
            conn.commit()
            
            # 진행률 표시
            progress = min(i + batch_size, total)
            pct = progress * 100 / total
            logger.info(f"진행: {progress}/{total} ({pct:.1f}%)")
        
        conn.close()
        logger.info("Mock 데이터 생성 완료")
    
    def generate_aggregations(self):
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
        WHERE team_id IS NOT NULL
        GROUP BY team_id, analysis_date
        """)
        
        # 직급별 분포 추가
        teams = cursor.execute("""
            SELECT DISTINCT team_id, analysis_date 
            FROM team_daily_summary
        """).fetchall()
        
        for team_id, analysis_date in teams:
            grade_dist = cursor.execute("""
                SELECT job_grade, COUNT(*) as count
                FROM daily_analysis
                WHERE team_id = ? AND analysis_date = ?
                GROUP BY job_grade
            """, (team_id, analysis_date)).fetchall()
            
            grade_dict = {grade: count for grade, count in grade_dist}
            
            cursor.execute("""
                UPDATE team_daily_summary
                SET grade_distribution = ?
                WHERE team_id = ? AND analysis_date = ?
            """, (json.dumps(grade_dict), team_id, analysis_date))
        
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
        WHERE center_id IS NOT NULL
        GROUP BY center_id, analysis_date
        """)
        
        conn.commit()
        conn.close()
        
        logger.info("집계 데이터 생성 완료")
    
    def print_summary(self):
        """생성된 데이터 요약 출력"""
        conn = sqlite3.connect(self.target_db)
        
        # 전체 통계
        stats = pd.read_sql_query("""
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT employee_id) as unique_employees,
                COUNT(DISTINCT analysis_date) as unique_dates,
                MIN(analysis_date) as first_date,
                MAX(analysis_date) as last_date,
                AVG(efficiency_ratio) as avg_efficiency,
                AVG(claim_vs_actual_diff) as avg_diff
            FROM daily_analysis
        """, conn)
        
        print("\n" + "="*60)
        print("📊 Mock 데이터 생성 완료")
        print("="*60)
        
        if not stats.empty:
            row = stats.iloc[0]
            print(f"📌 총 레코드: {row['total_records']:,}개")
            print(f"👥 직원 수: {row['unique_employees']:,}명")
            print(f"📅 날짜 범위: {row['first_date']} ~ {row['last_date']} ({row['unique_dates']}일)")
            print(f"📈 평균 효율성: {row['avg_efficiency']:.1f}%")
            print(f"⏱️  Claim vs 실제 차이: {row['avg_diff']:.2f}시간")
        
        # 조직별 요약
        org_stats = pd.read_sql_query("""
            SELECT 
                center_name,
                COUNT(DISTINCT team_id) as teams,
                COUNT(DISTINCT employee_id) as employees,
                AVG(efficiency_ratio) as avg_efficiency
            FROM daily_analysis
            WHERE center_name IS NOT NULL
            GROUP BY center_name
            ORDER BY employees DESC
            LIMIT 5
        """, conn)
        
        if not org_stats.empty:
            print("\n📊 상위 5개 센터:")
            for _, row in org_stats.iterrows():
                print(f"  • {row['center_name']}: {row['employees']}명, "
                      f"{row['teams']}팀, 효율성 {row['avg_efficiency']:.1f}%")
        
        conn.close()
        
        print("\n✅ Mock DB 경로:")
        print(f"   {self.target_db}")
        print("\n🚀 UI 개발 시작 가능!")
        print("   FastAPI 백엔드를 Mock DB와 연결하여 사용하세요.")


def main():
    """메인 실행"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Mock 분석 데이터 생성')
    parser.add_argument('--limit', type=int, help='생성할 레코드 수 제한')
    parser.add_argument('--sample-rate', type=float, default=1.0,
                       help='샘플링 비율 (0.1 = 10%)')
    parser.add_argument('--quick', action='store_true',
                       help='빠른 테스트 (최근 7일, 10% 샘플)')
    
    args = parser.parse_args()
    
    # 생성기 초기화
    generator = MockAnalyticsGenerator()
    
    # Mock DB 초기화
    generator.init_mock_db()
    
    # 옵션 설정
    if args.quick:
        # 빠른 테스트 모드
        generator.generate_mock_data(limit=5000, sample_rate=0.1)
    else:
        # 전체 생성
        generator.generate_mock_data(limit=args.limit, sample_rate=args.sample_rate)
    
    # 집계 생성
    generator.generate_aggregations()
    
    # 요약 출력
    generator.print_summary()


if __name__ == "__main__":
    main()