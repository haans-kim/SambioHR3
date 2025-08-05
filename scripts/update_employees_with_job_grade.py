"""
직원 테이블에 직급 정보를 추가하는 스크립트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gzip
import pickle
import pandas as pd
from src.database import get_database_manager

def update_employees_with_job_grade():
    """직원 테이블에 직급 정보 추가"""
    
    # 조직 데이터 로드
    with gzip.open('data/pickles/organization_data_v20250722_110253.pkl.gz', 'rb') as f:
        org_data = pickle.load(f)
    
    print(f"조직 데이터 로드 완료: {len(org_data)}명")
    
    # 데이터베이스 매니저
    db_manager = get_database_manager()
    
    # 직급 정보 업데이트
    update_count = 0
    
    for _, row in org_data.iterrows():
        employee_id = str(row['사번'])
        job_grade = row.get('직급2*')
        
        if job_grade and job_grade not in ['비정규직', '임원']:
            # 직급 정보 업데이트
            query = """
            UPDATE employees 
            SET job_grade = :job_grade 
            WHERE employee_id = :employee_id
            """
            
            db_manager.execute_query(query, {
                'job_grade': job_grade,
                'employee_id': employee_id
            })
            
            update_count += 1
    
    print(f"직급 정보 업데이트 완료: {update_count}명")
    
    # employees 테이블이 없으면 생성
    create_table_query = """
    CREATE TABLE IF NOT EXISTS employees (
        employee_id TEXT PRIMARY KEY,
        employee_name TEXT,
        center_id TEXT,
        center_name TEXT,
        group_id TEXT,
        group_name TEXT,
        team_id TEXT,
        team_name TEXT,
        position TEXT,
        job_grade TEXT
    )
    """
    db_manager.execute_query(create_table_query)
    
    # 직원 정보 삽입
    insert_count = 0
    
    for _, row in org_data.iterrows():
        employee_id = str(row['사번'])
        employee_name = row['성명']
        center_name = row['센터']
        group_name = row.get('그룹', row.get('GROUP_A'))
        team_name = row['팀']
        job_grade = row.get('직급2*')
        
        # 직급이 1,2,3,4만 저장
        if job_grade and job_grade in ['1', '2', '3', '4']:
            query = """
            INSERT OR REPLACE INTO employees (
                employee_id, employee_name, 
                center_id, center_name,
                group_id, group_name,
                team_id, team_name,
                job_grade
            ) VALUES (
                :employee_id, :employee_name,
                :center_id, :center_name,
                :group_id, :group_name,
                :team_id, :team_name,
                :job_grade
            )
            """
            
            db_manager.execute_query(query, {
                'employee_id': employee_id,
                'employee_name': employee_name,
                'center_id': center_name,
                'center_name': center_name,
                'group_id': group_name,
                'group_name': group_name,
                'team_id': team_name,
                'team_name': team_name,
                'job_grade': job_grade
            })
            
            insert_count += 1
    
    print(f"직원 정보 삽입 완료: {insert_count}명")
    
    # 확인
    result = db_manager.execute_query("""
    SELECT job_grade, COUNT(*) as count 
    FROM employees 
    WHERE job_grade IS NOT NULL 
    GROUP BY job_grade 
    ORDER BY job_grade
    """)
    
    print("\n직급별 인원 현황:")
    for row in result:
        print(f"Lv.{row['job_grade']}: {row['count']}명")


if __name__ == "__main__":
    update_employees_with_job_grade()