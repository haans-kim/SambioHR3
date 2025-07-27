#!/usr/bin/env python3
"""
정문/GATE 태그 수정 스크립트
G1으로 잘못 분류된 게이트들을 T2(입문) 또는 T3(출문)으로 수정
"""

import pandas as pd
import os
import sys
from sqlalchemy import create_engine, text

# 프로젝트 루트 경로 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from src.database.db_manager import DatabaseManager

def fix_gate_tags():
    """정문/GATE 태그 수정"""
    
    # 데이터베이스 연결
    db_manager = DatabaseManager()
    engine = db_manager.engine
    
    print("=== 정문/GATE 태그 수정 시작 ===\n")
    
    try:
        # 백업
        print("1. 데이터 백업 중...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM tag_location_master"))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
            df.to_csv('data/tag_location_master_gate_backup.csv', index=False, encoding='utf-8-sig')
            print(f"   백업 완료: {len(df)}개 행")
        
        # 수정할 게이트 조건
        # 1. 화물 Gate (cargo gates)
        # 2. SPEED GATE
        # 3. 정문 관련 게이트
        # 4. 사무실정문
        # 5. Office Room-정문
        
        with engine.connect() as conn:
            # 입문(IN) 게이트를 T2로 수정
            print("\n2. 입문(IN) 게이트를 T2로 수정...")
            update_in = conn.execute(text("""
                UPDATE tag_location_master 
                SET Tag_Code = 'T2'
                WHERE Tag_Code = 'G1'
                AND 입출구분 = 'IN'
                AND (
                    표기명 LIKE '%화물%Gate%' OR 
                    표기명 LIKE '%SPEED%GATE%' OR
                    표기명 LIKE '%정문%' OR
                    게이트명 LIKE '%화물%Gate%' OR
                    게이트명 LIKE '%SPEED%GATE%' OR
                    게이트명 LIKE '%정문%' OR
                    표기명 LIKE '%사무실정문%' OR
                    표기명 LIKE '%Office Room-정문%'
                )
            """))
            conn.commit()
            print(f"   수정된 입문 게이트: {update_in.rowcount}개")
            
            # 출문(OUT) 게이트를 T3으로 수정
            print("\n3. 출문(OUT) 게이트를 T3으로 수정...")
            update_out = conn.execute(text("""
                UPDATE tag_location_master 
                SET Tag_Code = 'T3'
                WHERE Tag_Code = 'G1'
                AND 입출구분 = 'OUT'
                AND (
                    표기명 LIKE '%화물%Gate%' OR 
                    표기명 LIKE '%SPEED%GATE%' OR
                    표기명 LIKE '%정문%' OR
                    게이트명 LIKE '%화물%Gate%' OR
                    게이트명 LIKE '%SPEED%GATE%' OR
                    게이트명 LIKE '%정문%' OR
                    표기명 LIKE '%사무실정문%' OR
                    표기명 LIKE '%Office Room-정문%'
                )
            """))
            conn.commit()
            print(f"   수정된 출문 게이트: {update_out.rowcount}개")
            
            # T1으로 분류된 SPEED GATE도 수정
            print("\n4. T1으로 분류된 SPEED GATE 수정...")
            
            # T1 입문을 T2로
            update_t1_in = conn.execute(text("""
                UPDATE tag_location_master 
                SET Tag_Code = 'T2'
                WHERE Tag_Code = 'T1'
                AND 입출구분 = 'IN'
                AND (표기명 LIKE '%SPEED%GATE%' OR 게이트명 LIKE '%SPEED%GATE%')
            """))
            conn.commit()
            print(f"   T1→T2 수정된 입문 게이트: {update_t1_in.rowcount}개")
            
            # T1 출문을 T3으로
            update_t1_out = conn.execute(text("""
                UPDATE tag_location_master 
                SET Tag_Code = 'T3'
                WHERE Tag_Code = 'T1'
                AND 입출구분 = 'OUT'
                AND (표기명 LIKE '%SPEED%GATE%' OR 게이트명 LIKE '%SPEED%GATE%')
            """))
            conn.commit()
            print(f"   T1→T3 수정된 출문 게이트: {update_t1_out.rowcount}개")
            
            # 검증
            print("\n5. 수정 결과 검증...")
            
            # Tag_Code별 집계
            result = conn.execute(text("""
                SELECT Tag_Code, 
                       COUNT(*) as total,
                       SUM(CASE WHEN 입출구분 = 'IN' THEN 1 ELSE 0 END) as in_count,
                       SUM(CASE WHEN 입출구분 = 'OUT' THEN 1 ELSE 0 END) as out_count
                FROM tag_location_master 
                WHERE 표기명 LIKE '%정문%' OR 게이트명 LIKE '%정문%' OR 
                      표기명 LIKE '%GATE%' OR 게이트명 LIKE '%GATE%'
                GROUP BY Tag_Code
                ORDER BY Tag_Code
            """))
            
            print("\n   수정 후 게이트 Tag_Code 분포:")
            print(f"   {'Tag_Code':<10} {'총개수':<10} {'입문':<10} {'출문':<10}")
            print("   " + "-" * 40)
            for row in result:
                print(f"   {row[0]:<10} {row[1]:<10} {row[2]:<10} {row[3]:<10}")
            
            # 여전히 G1인 게이트 확인
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM tag_location_master 
                WHERE Tag_Code = 'G1'
                AND (표기명 LIKE '%정문%' OR 게이트명 LIKE '%정문%' OR 
                     표기명 LIKE '%GATE%' OR 게이트명 LIKE '%GATE%')
            """))
            remaining_g1 = result.scalar()
            
            if remaining_g1 > 0:
                print(f"\n   ⚠️  아직 G1으로 남아있는 게이트: {remaining_g1}개")
                
                # 상세 확인
                result = conn.execute(text("""
                    SELECT 표기명, 게이트명, 입출구분, DR_NO
                    FROM tag_location_master 
                    WHERE Tag_Code = 'G1'
                    AND (표기명 LIKE '%정문%' OR 게이트명 LIKE '%정문%' OR 
                         표기명 LIKE '%GATE%' OR 게이트명 LIKE '%GATE%')
                    LIMIT 10
                """))
                print("\n   남은 G1 게이트 예시:")
                for row in result:
                    print(f"     - {row[0]} / {row[1]} / {row[2]}")
            else:
                print("\n   ✅ 모든 게이트가 올바르게 수정되었습니다!")
            
            # 전체 Tag_Code 분포
            print("\n6. 전체 Tag_Code 분포:")
            result = conn.execute(text("""
                SELECT Tag_Code, COUNT(*) as cnt 
                FROM tag_location_master 
                GROUP BY Tag_Code 
                ORDER BY Tag_Code
            """))
            for row in result:
                print(f"   {row[0]}: {row[1]}개")
        
        print("\n✅ 게이트 태그 수정 완료!")
        print("   총 수정 게이트 수:")
        print(f"   - G1→T2 (입문): {update_in.rowcount}개")
        print(f"   - G1→T3 (출문): {update_out.rowcount}개")
        print(f"   - T1→T2 (입문): {update_t1_in.rowcount}개")
        print(f"   - T1→T3 (출문): {update_t1_out.rowcount}개")
        print(f"   - 총 수정: {update_in.rowcount + update_out.rowcount + update_t1_in.rowcount + update_t1_out.rowcount}개")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_gate_tags()