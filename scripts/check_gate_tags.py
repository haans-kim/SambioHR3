#!/usr/bin/env python3
"""정문 관련 태그 확인 스크립트"""

import pandas as pd
import os
import sys
from sqlalchemy import create_engine, text

# 프로젝트 루트 경로 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from src.database.db_manager import DatabaseManager

def check_gate_tags():
    """정문 관련 태그 확인"""
    
    # 데이터베이스 연결
    db_manager = DatabaseManager()
    engine = db_manager.engine
    
    print("=== 정문 관련 태그 확인 ===\n")
    
    with engine.connect() as conn:
        # 1. 정문 관련 모든 데이터 확인
        result = conn.execute(text("""
            SELECT 표기명, 게이트명, Tag_Code, 입출구분, DR_NO 
            FROM tag_location_master 
            WHERE 표기명 LIKE '%정문%' OR 게이트명 LIKE '%정문%' OR 표기명 LIKE '%GATE%' OR 게이트명 LIKE '%GATE%'
            ORDER BY Tag_Code, 입출구분
            LIMIT 50
        """))
        
        print("정문/GATE 관련 태그:")
        print("-" * 100)
        print(f"{'표기명':<40} {'게이트명':<30} {'Tag_Code':<10} {'입출구분':<10} {'DR_NO':<10}")
        print("-" * 100)
        
        gate_data = []
        for row in result:
            gate_data.append(row)
            print(f"{row[0]:<40} {row[1]:<30} {row[2]:<10} {row[3]:<10} {row[4]:<10}")
        
        # 2. Tag_Code별 집계
        print("\n\n=== Tag_Code별 정문 태그 집계 ===")
        result = conn.execute(text("""
            SELECT Tag_Code, COUNT(*) as cnt,
                   SUM(CASE WHEN 입출구분 = 'IN' THEN 1 ELSE 0 END) as in_count,
                   SUM(CASE WHEN 입출구분 = 'OUT' THEN 1 ELSE 0 END) as out_count
            FROM tag_location_master 
            WHERE 표기명 LIKE '%정문%' OR 게이트명 LIKE '%정문%' OR 표기명 LIKE '%GATE%' OR 게이트명 LIKE '%GATE%'
            GROUP BY Tag_Code
            ORDER BY Tag_Code
        """))
        
        print(f"{'Tag_Code':<10} {'총개수':<10} {'입문(IN)':<10} {'출문(OUT)':<10}")
        print("-" * 40)
        for row in result:
            print(f"{row[0]:<10} {row[1]:<10} {row[2]:<10} {row[3]:<10}")
        
        # 3. 특정 DR_NO 확인 (예: 701-8-1-1)
        print("\n\n=== 특정 DR_NO 확인 (701-8-1-1) ===")
        result = conn.execute(text("""
            SELECT * 
            FROM tag_location_master 
            WHERE DR_NO = '701-8-1-1'
        """))
        
        rows = list(result)
        if rows:
            columns = result.keys()
            for row in rows:
                print("\n상세 정보:")
                for i, col in enumerate(columns):
                    print(f"  {col}: {row[i]}")
        else:
            print("해당 DR_NO를 찾을 수 없습니다.")
        
        # 4. 잘못된 Tag_Code 찾기 (정문인데 G1인 경우)
        print("\n\n=== 잘못된 Tag_Code 확인 (정문/GATE인데 G1) ===")
        result = conn.execute(text("""
            SELECT 표기명, 게이트명, Tag_Code, 입출구분, DR_NO
            FROM tag_location_master 
            WHERE (표기명 LIKE '%정문%' OR 게이트명 LIKE '%정문%' OR 
                   표기명 LIKE '%SPEED%GATE%' OR 게이트명 LIKE '%SPEED%GATE%')
                  AND Tag_Code = 'G1'
            LIMIT 20
        """))
        
        wrong_tags = list(result)
        if wrong_tags:
            print(f"\n발견된 문제: {len(wrong_tags)}건")
            print("-" * 100)
            print(f"{'표기명':<40} {'게이트명':<30} {'Tag_Code':<10} {'입출구분':<10} {'DR_NO':<10}")
            print("-" * 100)
            for row in wrong_tags:
                print(f"{row[0]:<40} {row[1]:<30} {row[2]:<10} {row[3]:<10} {row[4]:<10}")
        else:
            print("정문/GATE 태그가 모두 올바르게 설정되어 있습니다.")

if __name__ == "__main__":
    check_gate_tags()