#!/usr/bin/env python3
"""
태그 매핑 문제 수정 스크립트
tag_location_master의 '기기번호' 컬럼을 'DR_NO'로 변경
"""

import pandas as pd
import os
import sys
from sqlalchemy import create_engine, text

# 프로젝트 루트 경로 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from src.database.db_manager import DatabaseManager

def fix_tag_mapping():
    """태그 매핑 문제 수정"""
    
    # 데이터베이스 연결
    db_manager = DatabaseManager()
    engine = db_manager.engine
    
    print("=== 태그 매핑 수정 시작 ===")
    
    try:
        # 현재 데이터 백업
        print("\n1. 현재 데이터 백업 중...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM tag_location_master"))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
            df.to_csv('data/tag_location_master_backup.csv', index=False, encoding='utf-8-sig')
            print(f"   백업 완료: {len(df)}개 행")
        
        # DR_NO 컬럼 추가 (기기번호 복사)
        print("\n2. DR_NO 컬럼 추가...")
        with engine.connect() as conn:
            # DR_NO 컬럼이 없으면 추가
            try:
                conn.execute(text("ALTER TABLE tag_location_master ADD COLUMN DR_NO TEXT"))
                conn.commit()
                print("   DR_NO 컬럼 추가 완료")
            except Exception as e:
                print(f"   DR_NO 컬럼이 이미 존재하거나 오류: {e}")
            
            # 기기번호 데이터를 DR_NO로 복사
            conn.execute(text("UPDATE tag_location_master SET DR_NO = 기기번호"))
            conn.commit()
            print("   기기번호 데이터를 DR_NO로 복사 완료")
        
        # 데이터 검증
        print("\n3. 데이터 검증...")
        with engine.connect() as conn:
            # Tag_Code별 집계
            result = conn.execute(text("""
                SELECT Tag_Code, COUNT(*) as cnt 
                FROM tag_location_master 
                WHERE Tag_Code IS NOT NULL
                GROUP BY Tag_Code 
                ORDER BY Tag_Code
            """))
            print("   Tag_Code 분포:")
            for row in result:
                print(f"     {row[0]}: {row[1]}개")
            
            # T2/T3 데이터 확인
            result = conn.execute(text("""
                SELECT COUNT(*) as cnt, Tag_Code 
                FROM tag_location_master 
                WHERE Tag_Code IN ('T2', 'T3')
                GROUP BY Tag_Code
            """))
            print("\n   출입문 태그:")
            for row in result:
                print(f"     {row[1]}: {row[0]}개")
            
            # DR_NO 데이터 확인
            result = conn.execute(text("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN DR_NO IS NOT NULL THEN 1 ELSE 0 END) as dr_no_count,
                       SUM(CASE WHEN 기기번호 IS NOT NULL THEN 1 ELSE 0 END) as device_no_count
                FROM tag_location_master
            """))
            row = result.fetchone()
            print(f"\n   전체 행: {row[0]}, DR_NO 있음: {row[1]}, 기기번호 있음: {row[2]}")
            
            # 샘플 데이터
            result = conn.execute(text("""
                SELECT 표기명, DR_NO, Tag_Code, 입출구분 
                FROM tag_location_master 
                WHERE Tag_Code IN ('T2', 'T3') 
                LIMIT 5
            """))
            print("\n   출입문 샘플 데이터:")
            for row in result:
                print(f"     {row[0]} / DR_NO:{row[1]} / {row[2]} / {row[3]}")
        
        print("\n✅ 태그 매핑 수정 완료!")
        print("   이제 개인별 조회에서 Tag_Code가 제대로 매핑될 것입니다.")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_tag_mapping()