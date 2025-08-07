#!/usr/bin/env python3
"""
organization_master 테이블에 샘플 데이터 추가
"""

import sqlite3
from pathlib import Path

def populate_organization_master():
    """organization_master 테이블에 샘플 데이터 추가"""
    
    db_path = Path("data/sambio_human.db")
    if not db_path.exists():
        print(f"Error: Database file not found at {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 기존 데이터 확인
        cursor.execute("SELECT COUNT(*) FROM organization_master")
        count = cursor.fetchone()[0]
        print(f"현재 organization_master 테이블에 {count}개의 레코드가 있습니다.")
        
        if count == 0:
            print("샘플 데이터를 추가합니다...")
            
            # 센터 데이터
            centers = [
                ('CENTER_01', '제1생산센터', 'center', None, 1, 1),
                ('CENTER_02', '제2생산센터', 'center', None, 2, 1),
                ('CENTER_03', '품질관리센터', 'center', None, 3, 1),
            ]
            
            # 그룹 데이터
            groups = [
                ('GROUP_01A', '생산1그룹', 'group', 'CENTER_01', 1, 1),
                ('GROUP_01B', '생산2그룹', 'group', 'CENTER_01', 2, 1),
                ('GROUP_02A', '생산3그룹', 'group', 'CENTER_02', 1, 1),
                ('GROUP_02B', '생산4그룹', 'group', 'CENTER_02', 2, 1),
                ('GROUP_03A', '품질검사그룹', 'group', 'CENTER_03', 1, 1),
                ('GROUP_03B', '품질분석그룹', 'group', 'CENTER_03', 2, 1),
            ]
            
            # 팀 데이터
            teams = [
                ('TEAM_01A1', 'A라인 생산팀', 'team', 'GROUP_01A', 1, 1),
                ('TEAM_01A2', 'B라인 생산팀', 'team', 'GROUP_01A', 2, 1),
                ('TEAM_01B1', 'C라인 생산팀', 'team', 'GROUP_01B', 1, 1),
                ('TEAM_01B2', 'D라인 생산팀', 'team', 'GROUP_01B', 2, 1),
                ('TEAM_02A1', 'E라인 생산팀', 'team', 'GROUP_02A', 1, 1),
                ('TEAM_02A2', 'F라인 생산팀', 'team', 'GROUP_02A', 2, 1),
                ('TEAM_02B1', 'G라인 생산팀', 'team', 'GROUP_02B', 1, 1),
                ('TEAM_02B2', 'H라인 생산팀', 'team', 'GROUP_02B', 2, 1),
                ('TEAM_03A1', '입고검사팀', 'team', 'GROUP_03A', 1, 1),
                ('TEAM_03A2', '출하검사팀', 'team', 'GROUP_03A', 2, 1),
                ('TEAM_03B1', '품질분석팀', 'team', 'GROUP_03B', 1, 1),
                ('TEAM_03B2', '품질개선팀', 'team', 'GROUP_03B', 2, 1),
            ]
            
            # 데이터 삽입
            insert_query = """
            INSERT INTO organization_master 
            (org_code, org_name, org_level, parent_org_code, display_order, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
            """
            
            cursor.executemany(insert_query, centers)
            print(f"  - {len(centers)}개 센터 추가")
            
            cursor.executemany(insert_query, groups)
            print(f"  - {len(groups)}개 그룹 추가")
            
            cursor.executemany(insert_query, teams)
            print(f"  - {len(teams)}개 팀 추가")
            
            conn.commit()
            print("\n✅ 샘플 데이터 추가 완료!")
        else:
            print("이미 데이터가 있으므로 추가하지 않습니다.")
        
        # 최종 데이터 확인
        print("\n현재 organization_master 테이블 상태:")
        cursor.execute("SELECT org_level, COUNT(*) FROM organization_master GROUP BY org_level")
        for row in cursor.fetchall():
            print(f"  - {row[0]}: {row[1]}개")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    import sys
    success = populate_organization_master()
    sys.exit(0 if success else 1)