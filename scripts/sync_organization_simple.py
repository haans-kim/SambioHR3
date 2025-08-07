#!/usr/bin/env python3
"""
organization_data 테이블의 실제 데이터를 organization_master로 간단하게 동기화
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
        print("1. 기존 데이터 삭제...")
        cursor.execute("DELETE FROM organization_master")
        
        # 고유한 센터 목록 추출
        print("2. 센터 목록 추출...")
        cursor.execute("""
            SELECT DISTINCT 센터 
            FROM organization_data 
            WHERE 센터 IS NOT NULL AND 센터 != '' AND 센터 != '-'
            ORDER BY 센터
        """)
        centers = cursor.fetchall()
        
        # 센터 데이터 삽입
        print("3. 센터 데이터 삽입...")
        for idx, (center_name,) in enumerate(centers, 1):
            cursor.execute("""
                INSERT INTO organization_master 
                (org_code, org_name, org_level, parent_org_code, display_order, is_active)
                VALUES (?, ?, 'center', NULL, ?, 1)
            """, (f"CENTER_{idx:03d}", center_name, idx))
        print(f"  - {len(centers)}개 센터 추가")
        
        # 고유한 팀 목록 추출
        print("4. 팀 목록 추출...")
        cursor.execute("""
            SELECT DISTINCT 팀, 센터
            FROM organization_data 
            WHERE 팀 IS NOT NULL AND 팀 != '' AND 팀 != '-'
                AND 센터 IS NOT NULL AND 센터 != '' AND 센터 != '-'
            ORDER BY 센터, 팀
        """)
        teams = cursor.fetchall()
        
        # 센터 코드 매핑 생성
        center_map = {name: f"CENTER_{idx:03d}" for idx, (name,) in enumerate(centers, 1)}
        
        # 팀 데이터 삽입
        print("5. 팀 데이터 삽입...")
        for idx, (team_name, center_name) in enumerate(teams, 1):
            parent_code = center_map.get(center_name)
            if parent_code:
                cursor.execute("""
                    INSERT INTO organization_master 
                    (org_code, org_name, org_level, parent_org_code, display_order, is_active)
                    VALUES (?, ?, 'team', ?, ?, 1)
                """, (f"TEAM_{idx:04d}", team_name, parent_code, idx))
        print(f"  - {len(teams)}개 팀 추가")
        
        # 고유한 그룹 목록 추출 (그룹 필드가 있는 경우)
        print("6. 그룹 목록 추출...")
        cursor.execute("""
            SELECT DISTINCT 그룹, 팀, 센터
            FROM organization_data 
            WHERE 그룹 IS NOT NULL AND 그룹 != '' AND 그룹 != '-'
                AND 팀 IS NOT NULL AND 팀 != '' AND 팀 != '-'
            ORDER BY 센터, 팀, 그룹
        """)
        groups = cursor.fetchall()
        
        # 팀 코드 매핑 생성
        team_map = {}
        for idx, (team_name, center_name) in enumerate(teams, 1):
            team_map[team_name] = f"TEAM_{idx:04d}"
        
        # 그룹 데이터 삽입
        print("7. 그룹 데이터 삽입...")
        for idx, (group_name, team_name, center_name) in enumerate(groups, 1):
            parent_code = team_map.get(team_name)
            if parent_code:
                cursor.execute("""
                    INSERT OR IGNORE INTO organization_master 
                    (org_code, org_name, org_level, parent_org_code, display_order, is_active)
                    VALUES (?, ?, 'group', ?, ?, 1)
                """, (f"GROUP_{idx:04d}", group_name, parent_code, idx))
        print(f"  - {len(groups)}개 그룹 추가")
        
        conn.commit()
        print("\n✅ 동기화 완료!")
        
        # 최종 데이터 확인
        print("\n현재 organization_master 테이블 상태:")
        cursor.execute("SELECT org_level, COUNT(*) FROM organization_master GROUP BY org_level")
        for row in cursor.fetchall():
            print(f"  - {row[0]}: {row[1]}개")
        
        # 샘플 데이터 출력
        print("\n샘플 조직 데이터 (각 레벨별 5개씩):")
        for level in ['center', 'team', 'group']:
            print(f"\n[{level}]")
            cursor.execute("""
                SELECT org_name, org_code 
                FROM organization_master 
                WHERE org_level = ? 
                ORDER BY org_name 
                LIMIT 5
            """, (level,))
            for row in cursor.fetchall():
                print(f"  - {row[0]} ({row[1]})")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    import sys
    success = sync_organization_data()
    sys.exit(0 if success else 1)