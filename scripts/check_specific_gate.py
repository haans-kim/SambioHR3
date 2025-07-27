#!/usr/bin/env python3
"""특정 게이트 정보 확인"""

import pandas as pd
import os
import sys
from sqlalchemy import create_engine, text

# 프로젝트 루트 경로 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from src.database.db_manager import DatabaseManager

def check_specific_gate():
    """701-10 게이트 정보 확인"""
    
    # 데이터베이스 연결
    db_manager = DatabaseManager()
    engine = db_manager.engine
    
    print("=== 701-10 게이트 정보 확인 ===\n")
    
    with engine.connect() as conn:
        # 701-10 관련 모든 게이트 확인
        result = conn.execute(text("""
            SELECT * 
            FROM tag_location_master 
            WHERE DR_NO LIKE '701-10%'
            ORDER BY DR_NO
        """))
        
        rows = list(result)
        print(f"701-10 관련 게이트: {len(rows)}개\n")
        
        if rows:
            columns = result.keys()
            for row in rows:
                print("-" * 80)
                for i, col in enumerate(columns):
                    print(f"{col}: {row[i]}")
                print()
        
        # Tag_Code 집계
        print("\n=== Tag_Code 분포 ===")
        result = conn.execute(text("""
            SELECT Tag_Code, COUNT(*) as cnt 
            FROM tag_location_master 
            WHERE DR_NO LIKE '701-10%'
            GROUP BY Tag_Code
        """))
        
        for row in result:
            print(f"{row[0]}: {row[1]}개")

if __name__ == "__main__":
    check_specific_gate()