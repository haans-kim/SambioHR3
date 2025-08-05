"""
조직 분석 관련 데이터베이스 테이블 및 뷰 설정 스크립트
"""

import os
import sys
import sqlite3
import logging
from pathlib import Path

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database import get_database_manager


def setup_organization_tables():
    """조직 분석 테이블 생성"""
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # DB 매니저 가져오기
    db_manager = get_database_manager()
    
    # SQL 파일 경로
    sql_dir = Path(__file__).parent
    table_sql_file = sql_dir / 'create_organization_tables.sql'
    view_sql_file = sql_dir / 'create_organization_views.sql'
    
    try:
        # 1. 테이블 생성
        logger.info("조직 분석 테이블 생성 중...")
        
        with open(table_sql_file, 'r', encoding='utf-8') as f:
            table_sql = f.read()
        
        # SQL 문장들을 세미콜론으로 분리하여 실행
        statements = [stmt.strip() for stmt in table_sql.split(';') if stmt.strip()]
        
        for i, stmt in enumerate(statements):
            try:
                db_manager.execute_query(stmt)
                logger.info(f"  - 실행 완료 ({i+1}/{len(statements)})")
            except Exception as e:
                logger.error(f"  - 실행 실패 ({i+1}/{len(statements)}): {e}")
        
        logger.info("테이블 생성 완료!")
        
        # 2. 뷰 생성
        logger.info("\n조직 분석 뷰 생성 중...")
        
        with open(view_sql_file, 'r', encoding='utf-8') as f:
            view_sql = f.read()
        
        # SQL 문장들을 세미콜론으로 분리하여 실행
        view_statements = [stmt.strip() for stmt in view_sql.split(';') if stmt.strip()]
        
        for i, stmt in enumerate(view_statements):
            try:
                db_manager.execute_query(stmt)
                logger.info(f"  - 뷰 생성 완료 ({i+1}/{len(view_statements)})")
            except Exception as e:
                logger.error(f"  - 뷰 생성 실패 ({i+1}/{len(view_statements)}): {e}")
        
        logger.info("뷰 생성 완료!")
        
        # 3. 테이블 및 뷰 확인
        logger.info("\n생성된 테이블 확인:")
        
        # 테이블 목록 조회
        tables = db_manager.execute_query("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND name LIKE '%daily_analysis%' OR name LIKE '%organization%'
            ORDER BY name
        """)
        
        if tables:
            for table in tables:
                if isinstance(table, dict):
                    logger.info(f"  - {table.get('name', 'Unknown')}")
                elif isinstance(table, (list, tuple)) and len(table) > 0:
                    logger.info(f"  - {table[0]}")
        else:
            logger.info("  - 조직 분석 관련 테이블이 없습니다.")
        
        # 뷰 목록 조회
        logger.info("\n생성된 뷰 확인:")
        views = db_manager.execute_query("""
            SELECT name FROM sqlite_master 
            WHERE type='view' 
            AND (name LIKE 'v_%' OR name LIKE '%organization%')
            ORDER BY name
        """)
        
        if views:
            for view in views:
                if isinstance(view, dict):
                    logger.info(f"  - {view.get('name', 'Unknown')}")
                elif isinstance(view, (list, tuple)) and len(view) > 0:
                    logger.info(f"  - {view[0]}")
        else:
            logger.info("  - 조직 분석 관련 뷰가 없습니다.")
        
        logger.info("\n데이터베이스 설정 완료!")
        
    except Exception as e:
        logger.error(f"데이터베이스 설정 중 오류 발생: {e}")
        raise


def check_employees_table():
    """employees 테이블 존재 확인 및 생성"""
    
    logger = logging.getLogger(__name__)
    db_manager = get_database_manager()
    
    # employees 테이블 존재 확인
    result = db_manager.execute_query("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='employees'
    """)
    
    if not result:
        logger.info("employees 테이블이 없습니다. 생성합니다...")
        
        # 임시 employees 테이블 생성
        db_manager.execute_query("""
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
        """)
        
        logger.info("employees 테이블 생성 완료")
        
        # organization_data에서 데이터 가져와서 채우기
        try:
            from src.database import get_pickle_manager
            pickle_manager = get_pickle_manager()
            org_data = pickle_manager.load_dataframe(name='organization_data')
            
            if org_data is not None:
                logger.info(f"조직 데이터에서 {len(org_data)}명의 직원 정보를 가져옵니다...")
                
                for _, row in org_data.iterrows():
                    db_manager.execute_query("""
                        INSERT OR REPLACE INTO employees (
                            employee_id, employee_name, 
                            center_id, center_name,
                            group_id, group_name,
                            team_id, team_name
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row.get('사번'),
                        row.get('성명'),
                        row.get('센터'),
                        row.get('센터'),
                        row.get('그룹'),
                        row.get('그룹'),
                        row.get('팀'),
                        row.get('팀')
                    ))
                
                logger.info("직원 정보 입력 완료")
        except Exception as e:
            logger.warning(f"직원 정보 가져오기 실패: {e}")
    else:
        logger.info("employees 테이블이 이미 존재합니다.")


def check_organization_master():
    """organization_master 테이블 존재 확인 및 생성"""
    
    logger = logging.getLogger(__name__)
    db_manager = get_database_manager()
    
    # organization_master 테이블 존재 확인
    result = db_manager.execute_query("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='organization_master'
    """)
    
    if not result:
        logger.info("organization_master 테이블이 없습니다. 생성합니다...")
        
        # 임시 organization_master 테이블 생성
        db_manager.execute_query("""
            CREATE TABLE IF NOT EXISTS organization_master (
                team_id TEXT PRIMARY KEY,
                team_name TEXT,
                group_id TEXT,
                group_name TEXT,
                center_id TEXT,
                center_name TEXT
            )
        """)
        
        logger.info("organization_master 테이블 생성 완료")


if __name__ == "__main__":
    print("조직 분석 데이터베이스 설정을 시작합니다...")
    
    # 필수 테이블 확인
    check_employees_table()
    check_organization_master()
    
    # 조직 분석 테이블 설정
    setup_organization_tables()
    
    print("\n설정이 완료되었습니다!")
    print("\n배치 분석 실행 예시:")
    print("python scripts/batch_organization_analysis.py --date 2025-07-31")
    print("python scripts/batch_organization_analysis.py --start-date 2025-07-01 --end-date 2025-07-31 --center 'Plant 1팀'")