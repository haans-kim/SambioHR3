#!/usr/bin/env python3
"""
Claim 데이터를 Excel에서 읽어 DB에 로드하는 스크립트
employee_claims 테이블 생성 및 데이터 적재
"""

import pandas as pd
import sqlite3
from pathlib import Path
import logging
from datetime import datetime
import sys

# 프로젝트 경로 설정
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_claim_data():
    """Claim 데이터 로드 및 DB 저장"""
    
    # 파일 경로
    excel_path = project_root / 'data' / 'data_근무시간(claim)_전사_2506.xlsx'
    db_path = project_root / 'data' / 'sambio.db'
    
    if not excel_path.exists():
        logger.error(f"Excel 파일을 찾을 수 없습니다: {excel_path}")
        return False
    
    logger.info(f"Claim 데이터 로드 시작: {excel_path}")
    
    try:
        # Excel 파일 읽기
        df = pd.read_excel(excel_path)
        logger.info(f"데이터 로드 완료: {len(df)}행")
        
        # 컬럼명 확인 및 정리
        logger.info(f"원본 컬럼: {df.columns.tolist()}")
        
        # 컬럼명 매핑 (실제 컬럼명에 맞게 조정)
        column_mapping = {
            '사번': 'employee_id',
            '성명': 'employee_name',
            '근무일': 'work_date',
            '근무일자': 'work_date',
            '날짜': 'work_date',
            'Date': 'work_date',
            '총 근무시간': 'total_hours',
            '근무시간': 'total_hours',
            'Total Hours': 'total_hours',
            '정규근무': 'regular_hours',
            '초과근무': 'overtime_hours',
            '야간근무': 'night_hours',
            '휴일근무': 'holiday_hours',
            '센터': 'center_name',
            '팀': 'team_name',
            '그룹': 'group_name',
            '직급': 'job_grade'
        }
        
        # 사용 가능한 컬럼만 매핑
        available_mappings = {}
        for orig, new in column_mapping.items():
            if orig in df.columns:
                available_mappings[orig] = new
        
        if available_mappings:
            df = df.rename(columns=available_mappings)
            logger.info(f"컬럼 매핑 완료: {available_mappings}")
        
        # 필수 컬럼 확인
        required_columns = ['employee_id', 'work_date', 'total_hours']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            # 컬럼 추정 시도
            if 'employee_id' not in df.columns and len(df.columns) > 0:
                # 첫 번째 컬럼을 사번으로 가정
                df.rename(columns={df.columns[0]: 'employee_id'}, inplace=True)
            
            if 'work_date' not in df.columns and len(df.columns) > 1:
                # 날짜 형식 컬럼 찾기
                for col in df.columns:
                    if 'date' in col.lower() or '날짜' in col or '일' in col:
                        df.rename(columns={col: 'work_date'}, inplace=True)
                        break
            
            if 'total_hours' not in df.columns:
                # 시간 관련 컬럼 찾기
                for col in df.columns:
                    if '시간' in col or 'hour' in col.lower():
                        df.rename(columns={col: 'total_hours'}, inplace=True)
                        break
        
        # 날짜 형식 변환
        if 'work_date' in df.columns:
            # 근무일이 YYYYMMDD 형식인 경우 처리
            if df['work_date'].dtype in ['int64', 'int32']:
                df['work_date'] = pd.to_datetime(df['work_date'].astype(str), format='%Y%m%d', errors='coerce')
            else:
                df['work_date'] = pd.to_datetime(df['work_date'], errors='coerce')
            df = df.dropna(subset=['work_date'])
            df['work_date'] = df['work_date'].dt.strftime('%Y-%m-%d')
        
        # 근무시간 변환 (HH:MM 형식을 시간 단위로)
        if 'total_hours' in df.columns:
            def convert_time_to_hours(time_str):
                """HH:MM 형식을 시간 단위로 변환"""
                if pd.isna(time_str) or time_str == '00:00':
                    return 0
                try:
                    if isinstance(time_str, str) and ':' in time_str:
                        parts = time_str.split(':')
                        hours = int(parts[0])
                        minutes = int(parts[1]) if len(parts) > 1 else 0
                        return hours + minutes / 60
                    else:
                        return float(time_str)
                except:
                    return 0
            
            df['total_hours'] = df['total_hours'].apply(convert_time_to_hours)
            # 0시간 제외 (실제 근무한 경우만)
            df = df[df['total_hours'] > 0]
        
        # DB 연결
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 테이블 생성
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS employee_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            employee_name TEXT,
            work_date DATE NOT NULL,
            total_hours REAL,
            regular_hours REAL,
            overtime_hours REAL,
            night_hours REAL,
            holiday_hours REAL,
            center_name TEXT,
            team_name TEXT,
            group_name TEXT,
            job_grade TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(employee_id, work_date)
        )
        """)
        
        # 인덱스 생성
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_claims_employee_date 
        ON employee_claims(employee_id, work_date)
        """)
        
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_claims_date 
        ON employee_claims(work_date)
        """)
        
        # 데이터 삽입
        inserted = 0
        skipped = 0
        
        for _, row in df.iterrows():
            try:
                cursor.execute("""
                INSERT OR REPLACE INTO employee_claims (
                    employee_id, employee_name, work_date, total_hours,
                    regular_hours, overtime_hours, night_hours, holiday_hours,
                    center_name, team_name, group_name, job_grade
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(row.get('employee_id', '')),
                    row.get('employee_name'),
                    row.get('work_date'),
                    float(row.get('total_hours', 0)) if pd.notna(row.get('total_hours')) else 0,
                    float(row.get('regular_hours', 0)) if pd.notna(row.get('regular_hours')) else None,
                    float(row.get('overtime_hours', 0)) if pd.notna(row.get('overtime_hours')) else None,
                    float(row.get('night_hours', 0)) if pd.notna(row.get('night_hours')) else None,
                    float(row.get('holiday_hours', 0)) if pd.notna(row.get('holiday_hours')) else None,
                    row.get('center_name'),
                    row.get('team_name'),
                    row.get('group_name'),
                    row.get('job_grade')
                ))
                inserted += 1
            except Exception as e:
                logger.warning(f"행 삽입 실패: {e}")
                skipped += 1
        
        conn.commit()
        
        # 통계 확인
        cursor.execute("SELECT COUNT(*) FROM employee_claims")
        total_count = cursor.fetchone()[0]
        
        cursor.execute("""
        SELECT 
            COUNT(DISTINCT employee_id) as employees,
            COUNT(DISTINCT work_date) as dates,
            MIN(work_date) as min_date,
            MAX(work_date) as max_date
        FROM employee_claims
        """)
        stats = cursor.fetchone()
        
        conn.close()
        
        logger.info(f"""
        ========================================
        Claim 데이터 로드 완료!
        ========================================
        총 레코드: {total_count}
        삽입: {inserted}, 스킵: {skipped}
        직원 수: {stats[0]}
        날짜 범위: {stats[2]} ~ {stats[3]} ({stats[1]}일)
        ========================================
        """)
        
        return True
        
    except Exception as e:
        logger.error(f"Claim 데이터 로드 실패: {e}", exc_info=True)
        return False


def verify_claim_data():
    """Claim 데이터 검증"""
    db_path = project_root / 'data' / 'sambio.db'
    
    if not db_path.exists():
        logger.error("DB 파일이 없습니다.")
        return
    
    conn = sqlite3.connect(db_path)
    
    # 샘플 데이터 확인
    sample = pd.read_sql_query("""
        SELECT * FROM employee_claims 
        LIMIT 5
    """, conn)
    
    print("\n샘플 데이터:")
    print(sample)
    
    # 날짜별 통계
    daily_stats = pd.read_sql_query("""
        SELECT 
            work_date,
            COUNT(DISTINCT employee_id) as employees,
            AVG(total_hours) as avg_hours
        FROM employee_claims
        GROUP BY work_date
        ORDER BY work_date DESC
        LIMIT 10
    """, conn)
    
    print("\n최근 10일 통계:")
    print(daily_stats)
    
    conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Claim 데이터 로드')
    parser.add_argument('--verify', action='store_true', help='데이터 검증만 실행')
    
    args = parser.parse_args()
    
    if args.verify:
        verify_claim_data()
    else:
        success = load_claim_data()
        if success:
            verify_claim_data()