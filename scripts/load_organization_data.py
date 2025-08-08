#!/usr/bin/env python3
"""
조직 및 인원 데이터를 Excel에서 읽어 DB에 로드하는 스크립트
employees 테이블 생성 및 데이터 적재
"""

import pandas as pd
import sqlite3
from pathlib import Path
import logging
import sys

# 프로젝트 경로 설정
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_organization_data():
    """조직 데이터 로드 및 DB 저장"""
    
    # 파일 경로
    excel_path = project_root / 'data' / '25년 6월말 인원현황.xlsx'
    db_path = project_root / 'data' / 'sambio.db'
    
    if not excel_path.exists():
        logger.error(f"Excel 파일을 찾을 수 없습니다: {excel_path}")
        return False
    
    logger.info(f"조직 데이터 로드 시작: {excel_path}")
    
    try:
        # Excel 파일 읽기
        df = pd.read_excel(excel_path)
        logger.info(f"데이터 로드 완료: {len(df)}행")
        logger.info(f"컬럼: {df.columns.tolist()}")
        
        # 첫 몇 행 확인
        print("\n샘플 데이터:")
        print(df.head(3))
        
        # 컬럼명 매핑
        column_mapping = {
            '사번': 'employee_id',
            '성명': 'employee_name',
            '이름': 'employee_name',
            '센터': 'center_name',
            '센터명': 'center_name',
            '팀': 'team_name',
            '팀명': 'team_name',
            '그룹': 'group_name',
            '그룹명': 'group_name',
            '파트': 'group_name',  # 파트를 그룹으로 매핑
            '부서명': 'department',
            '직급명': 'job_grade',  # 직급명으로 수정
            '직책명': 'position',
            '그룹입사일': 'hire_date',
            '재직상태': 'employment_status'
        }
        
        # 사용 가능한 컬럼만 매핑
        available_mappings = {}
        for orig, new in column_mapping.items():
            if orig in df.columns:
                available_mappings[orig] = new
        
        if available_mappings:
            df = df.rename(columns=available_mappings)
            logger.info(f"컬럼 매핑 완료: {available_mappings}")
        
        # 센터/팀/그룹 정보 생성
        # 부서 컬럼이 있으면 파싱 시도
        if 'department' in df.columns and 'center_name' not in df.columns:
            # 부서명에서 센터/팀 추출 시도
            df['center_name'] = df['department'].apply(lambda x: str(x).split()[0] if pd.notna(x) else None)
        
        # DB 연결
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 테이블 생성
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            employee_id TEXT PRIMARY KEY,
            employee_name TEXT,
            center_id TEXT,
            center_name TEXT,
            team_id TEXT,
            team_name TEXT,
            group_id TEXT,
            group_name TEXT,
            department TEXT,
            position TEXT,
            job_grade TEXT,
            hire_date DATE,
            employment_status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # 인덱스 생성
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_emp_center 
        ON employees(center_name)
        """)
        
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_emp_team 
        ON employees(team_name)
        """)
        
        # 데이터 삽입
        inserted = 0
        skipped = 0
        
        for _, row in df.iterrows():
            try:
                # employee_id가 없으면 스킵
                if pd.isna(row.get('employee_id')):
                    continue
                
                # center_id, team_id, group_id 생성 (이름 기반)
                center_name_val = row.get('center_name')
                team_name_val = row.get('team_name')
                group_name_val = row.get('group_name')
                
                # Series 대신 직접 값 추출
                if isinstance(center_name_val, pd.Series):
                    center_name_val = center_name_val.iloc[0] if not center_name_val.empty else ''
                if isinstance(team_name_val, pd.Series):
                    team_name_val = team_name_val.iloc[0] if not team_name_val.empty else ''
                if isinstance(group_name_val, pd.Series):
                    group_name_val = group_name_val.iloc[0] if not group_name_val.empty else ''
                
                center_id = str(center_name_val) if pd.notna(center_name_val) else ''
                team_id = f"{center_id}_{team_name_val}" if pd.notna(team_name_val) else center_id
                group_id = f"{team_id}_{group_name_val}" if pd.notna(group_name_val) else team_id
                
                # 모든 값을 문자열로 변환하고 None 처리
                def safe_str(val):
                    if pd.isna(val):
                        return None
                    if isinstance(val, pd.Series):
                        val = val.iloc[0] if not val.empty else None
                    return str(val) if val is not None else None
                
                cursor.execute("""
                INSERT OR REPLACE INTO employees (
                    employee_id, employee_name,
                    center_id, center_name,
                    team_id, team_name,
                    group_id, group_name,
                    department, position, job_grade,
                    hire_date, employment_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    safe_str(row.get('employee_id')),
                    safe_str(row.get('employee_name')),
                    center_id,
                    safe_str(center_name_val),
                    team_id,
                    safe_str(team_name_val),
                    group_id,
                    safe_str(group_name_val),
                    safe_str(row.get('department')),
                    safe_str(row.get('position')),
                    safe_str(row.get('job_grade')),
                    safe_str(row.get('hire_date')),
                    safe_str(row.get('employment_status'))
                ))
                inserted += 1
            except Exception as e:
                logger.warning(f"행 삽입 실패: {e}")
                skipped += 1
        
        conn.commit()
        
        # 통계 확인
        cursor.execute("SELECT COUNT(*) FROM employees")
        total_count = cursor.fetchone()[0]
        
        cursor.execute("""
        SELECT 
            COUNT(DISTINCT center_name) as centers,
            COUNT(DISTINCT team_name) as teams,
            COUNT(DISTINCT job_grade) as grades
        FROM employees
        WHERE center_name IS NOT NULL
        """)
        stats = cursor.fetchone()
        
        conn.close()
        
        logger.info(f"""
        ========================================
        조직 데이터 로드 완료!
        ========================================
        총 직원: {total_count}명
        삽입: {inserted}, 스킵: {skipped}
        센터: {stats[0]}개
        팀: {stats[1]}개
        직급: {stats[2]}종
        ========================================
        """)
        
        return True
        
    except Exception as e:
        logger.error(f"조직 데이터 로드 실패: {e}", exc_info=True)
        return False


def update_claim_with_organization():
    """Claim 데이터에 조직 정보 업데이트"""
    db_path = project_root / 'data' / 'sambio.db'
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # employee_claims 테이블에 조직 정보 업데이트
        cursor.execute("""
        UPDATE employee_claims
        SET 
            center_name = (SELECT center_name FROM employees WHERE employees.employee_id = employee_claims.employee_id),
            team_name = (SELECT team_name FROM employees WHERE employees.employee_id = employee_claims.employee_id),
            group_name = (SELECT group_name FROM employees WHERE employees.employee_id = employee_claims.employee_id),
            job_grade = (SELECT job_grade FROM employees WHERE employees.employee_id = employee_claims.employee_id)
        WHERE EXISTS (SELECT 1 FROM employees WHERE employees.employee_id = employee_claims.employee_id)
        """)
        
        updated = cursor.rowcount
        conn.commit()
        
        logger.info(f"Claim 데이터에 조직 정보 업데이트 완료: {updated}건")
        
    except Exception as e:
        logger.error(f"업데이트 실패: {e}")
    finally:
        conn.close()


def verify_organization_data():
    """조직 데이터 검증"""
    db_path = project_root / 'data' / 'sambio.db'
    
    if not db_path.exists():
        logger.error("DB 파일이 없습니다.")
        return
    
    conn = sqlite3.connect(db_path)
    
    # 샘플 데이터 확인
    sample = pd.read_sql_query("""
        SELECT * FROM employees 
        LIMIT 5
    """, conn)
    
    print("\n직원 샘플 데이터:")
    print(sample[['employee_id', 'employee_name', 'center_name', 'team_name', 'job_grade']])
    
    # 조직별 통계
    org_stats = pd.read_sql_query("""
        SELECT 
            center_name,
            COUNT(DISTINCT team_name) as teams,
            COUNT(*) as employees
        FROM employees
        WHERE center_name IS NOT NULL
        GROUP BY center_name
        ORDER BY employees DESC
        LIMIT 10
    """, conn)
    
    print("\n상위 10개 센터:")
    print(org_stats)
    
    # 직급 분포
    grade_dist = pd.read_sql_query("""
        SELECT 
            job_grade,
            COUNT(*) as count
        FROM employees
        WHERE job_grade IS NOT NULL
        GROUP BY job_grade
        ORDER BY count DESC
    """, conn)
    
    print("\n직급 분포:")
    print(grade_dist)
    
    conn.close()


if __name__ == "__main__":
    # 1. 조직 데이터 로드
    success = load_organization_data()
    
    if success:
        # 2. 검증
        verify_organization_data()
        
        # 3. Claim 데이터 업데이트
        update_claim_with_organization()