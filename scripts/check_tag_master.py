#!/usr/bin/env python3
"""태그 마스터 테이블 구조 및 데이터 확인 스크립트"""

import pandas as pd
import os
import sys
from sqlalchemy import create_engine, inspect, text

# 프로젝트 루트 경로 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from src.database.db_manager import DatabaseManager

def check_tag_master():
    """태그 마스터 테이블 확인"""
    
    # 데이터베이스 연결
    db_manager = DatabaseManager()
    engine = db_manager.engine
    
    # Inspector 생성
    inspector = inspect(engine)
    
    # 모든 테이블 목록
    print("=== 데이터베이스 테이블 목록 ===")
    tables = inspector.get_table_names()
    for table in sorted(tables):
        print(f"  - {table}")
    
    # tag_location_master 테이블 확인
    if 'tag_location_master' in tables:
        print("\n=== tag_location_master 테이블 구조 ===")
        columns = inspector.get_columns('tag_location_master')
        for col in columns:
            print(f"  - {col['name']}: {col['type']}")
        
        # 데이터 샘플 확인
        with engine.connect() as conn:
            # 전체 행 수
            result = conn.execute(text("SELECT COUNT(*) FROM tag_location_master"))
            count = result.scalar()
            print(f"\n총 데이터 수: {count}개")
            
            # Tag_Code 컬럼 존재 여부 확인
            try:
                result = conn.execute(text("""
                    SELECT Tag_Code, COUNT(*) as cnt 
                    FROM tag_location_master 
                    WHERE Tag_Code IS NOT NULL AND Tag_Code != ''
                    GROUP BY Tag_Code 
                    ORDER BY Tag_Code
                """))
                print("\n=== Tag_Code 분포 ===")
                has_tag_code = False
                for row in result:
                    has_tag_code = True
                    print(f"  {row[0]}: {row[1]}개")
                
                if not has_tag_code:
                    print("  Tag_Code 데이터가 없습니다!")
                    
            except Exception as e:
                print(f"\nTag_Code 컬럼이 없거나 오류 발생: {e}")
            
            # 근무구역여부 컬럼 확인 (기존 공간구분_code)
            try:
                result = conn.execute(text("""
                    SELECT 근무구역여부, COUNT(*) as cnt 
                    FROM tag_location_master 
                    WHERE 근무구역여부 IS NOT NULL AND 근무구역여부 != ''
                    GROUP BY 근무구역여부 
                    ORDER BY 근무구역여부
                """))
                print("\n=== 근무구역여부(공간구분_code) 분포 ===")
                for row in result:
                    print(f"  {row[0]}: {row[1]}개")
            except Exception as e:
                print(f"\n근무구역여부 컬럼 오류: {e}")
            
            # 출입문 관련 데이터 확인
            print("\n=== 출입문 관련 데이터 샘플 ===")
            try:
                # Tag_Code로 확인
                result = conn.execute(text("""
                    SELECT 표기명, Tag_Code, 입출구분, 게이트명 
                    FROM tag_location_master 
                    WHERE Tag_Code IN ('T2', 'T3') 
                    LIMIT 10
                """))
                rows = list(result)
                if rows:
                    print("Tag_Code가 T2/T3인 데이터:")
                    for row in rows:
                        print(f"  {row[0]} / {row[1]} / {row[2]} / {row[3]}")
                else:
                    # 근무구역여부로 확인
                    result = conn.execute(text("""
                        SELECT 표기명, 근무구역여부, 입출구분, 게이트명 
                        FROM tag_location_master 
                        WHERE 근무구역여부 IN ('T2', 'T3') 
                        LIMIT 10
                    """))
                    rows = list(result)
                    if rows:
                        print("근무구역여부가 T2/T3인 데이터:")
                        for row in rows:
                            print(f"  {row[0]} / {row[1]} / {row[2]} / {row[3]}")
                    else:
                        # 게이트명으로 출입문 찾기
                        result = conn.execute(text("""
                            SELECT 표기명, 근무구역여부, 입출구분, 게이트명 
                            FROM tag_location_master 
                            WHERE 게이트명 LIKE '%GATE%' OR 게이트명 LIKE '%정문%'
                            LIMIT 10
                        """))
                        print("게이트명에 'GATE' 또는 '정문'이 포함된 데이터:")
                        for row in result:
                            print(f"  {row[0]} / {row[1]} / {row[2]} / {row[3]}")
            except Exception as e:
                print(f"출입문 데이터 확인 오류: {e}")
                
    else:
        print("\n태그 마스터 테이블이 존재하지 않습니다!")
        
    # pickle 파일 확인
    print("\n=== Pickle 파일 확인 ===")
    pickle_dir = os.path.join(project_root, "data", "pickles")
    if os.path.exists(pickle_dir):
        tag_pickles = [f for f in os.listdir(pickle_dir) if 'tag' in f.lower()]
        for pickle_file in tag_pickles[:5]:  # 최대 5개만
            print(f"  - {pickle_file}")

if __name__ == "__main__":
    check_tag_master()