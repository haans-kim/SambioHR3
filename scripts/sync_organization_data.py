#!/usr/bin/env python3
"""
organization_data 테이블의 실제 데이터를 organization_master로 동기화
"""

import sqlite3
from pathlib import Path

def sync_organization_data():
    """organization_data에서 organization_master로 데이터 동기화"""
    
    db_path = Path("data/sambio_human.db")
    if not db_path.exists():
        print(f"Error: Database file not found at {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 기존 organization_master 데이터 삭제
        print("1. 기존 샘플 데이터 삭제...")
        cursor.execute("DELETE FROM organization_master")
        
        # organization_data에서 고유한 센터 정보 추출
        print("2. 센터 데이터 추출 및 삽입...")
        cursor.execute("""
            INSERT OR IGNORE INTO organization_master (org_code, org_name, org_level, parent_org_code, display_order, is_active)
            SELECT 
                org_code,
                org_name,
                org_level,
                parent_org_code,
                display_order,
                is_active
            FROM (
                SELECT DISTINCT 
                    센터 as org_name,
                    'CENTER_' || ROW_NUMBER() OVER (ORDER BY 센터) as org_code,
                    'center' as org_level,
                    NULL as parent_org_code,
                    ROW_NUMBER() OVER (ORDER BY 센터) as display_order,
                    1 as is_active
                FROM organization_data
                WHERE 센터 IS NOT NULL AND 센터 != '' AND 센터 != '-'
                GROUP BY 센터
            )
        """)
        center_count = cursor.rowcount
        print(f"  - {center_count}개 센터 추가")
        
        # BU 데이터 추출 (그룹 레벨로 매핑)
        print("3. BU(그룹) 데이터 추출 및 삽입...")
        cursor.execute("""
            INSERT INTO organization_master (org_code, org_name, org_level, parent_org_code, display_order, is_active)
            SELECT DISTINCT 
                'GROUP_' || SUBSTR(부서코드, 1, 8) as org_code,
                BU as org_name,
                'group' as org_level,
                'CENTER_' || SUBSTR(부서코드, 1, 6) as parent_org_code,
                ROW_NUMBER() OVER (ORDER BY BU) as display_order,
                1 as is_active
            FROM organization_data
            WHERE BU IS NOT NULL AND BU != '' AND BU != '-'
                AND 센터 IS NOT NULL AND 센터 != '' AND 센터 != '-'
        """)
        group_count = cursor.rowcount
        print(f"  - {group_count}개 BU(그룹) 추가")
        
        # 팀 데이터 추출
        print("4. 팀 데이터 추출 및 삽입...")
        cursor.execute("""
            INSERT INTO organization_master (org_code, org_name, org_level, parent_org_code, display_order, is_active)
            SELECT DISTINCT 
                'TEAM_' || 부서코드 as org_code,
                팀 as org_name,
                'team' as org_level,
                'GROUP_' || SUBSTR(부서코드, 1, 8) as parent_org_code,
                ROW_NUMBER() OVER (ORDER BY 팀) as display_order,
                1 as is_active
            FROM organization_data
            WHERE 팀 IS NOT NULL AND 팀 != '' AND 팀 != '-'
                AND BU IS NOT NULL AND BU != '' AND BU != '-'
        """)
        team_count = cursor.rowcount
        print(f"  - {team_count}개 팀 추가")
        
        conn.commit()
        print("\n✅ 동기화 완료!")
        
        # 최종 데이터 확인
        print("\n현재 organization_master 테이블 상태:")
        cursor.execute("SELECT org_level, COUNT(*) FROM organization_master GROUP BY org_level")
        for row in cursor.fetchall():
            print(f"  - {row[0]}: {row[1]}개")
        
        # 샘플 데이터 출력
        print("\n샘플 조직 데이터:")
        cursor.execute("SELECT org_level, org_code, org_name FROM organization_master ORDER BY org_level, org_name LIMIT 10")
        for row in cursor.fetchall():
            print(f"  [{row[0]}] {row[2]} ({row[1]})")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    import sys
    success = sync_organization_data()
    sys.exit(0 if success else 1)