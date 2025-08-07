#!/usr/bin/env python3
"""
tag_data와 claim_data 모두에 데이터가 있는 직원 찾기
"""

import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.data_processing import PickleManager

def find_valid_employees():
    """tag_data와 claim_data 모두에 데이터가 있는 직원 찾기"""
    
    pickle_mgr = PickleManager(base_path="data/pickles")
    
    # 데이터 로드
    claim_df = pickle_mgr.load_dataframe('claim_data')
    tag_df = pickle_mgr.load_dataframe('tag_data')
    org_df = pickle_mgr.load_dataframe('organization_data')
    
    # claim_data와 tag_data에 모두 있는 사번 찾기
    claim_employees = set(claim_df['사번'].unique())
    tag_employees = set(tag_df['사번'].unique())
    
    # 교집합
    common_employees = claim_employees & tag_employees
    
    print(f"claim_data 직원 수: {len(claim_employees)}")
    print(f"tag_data 직원 수: {len(tag_employees)}")
    print(f"공통 직원 수: {len(common_employees)}")
    
    # People센터 직원 중 데이터가 있는 직원 찾기
    if '센터' in org_df.columns:
        people_employees = org_df[org_df['센터'] == 'People센터']['사번'].tolist()
        people_with_data = [emp for emp in people_employees if emp in common_employees]
        
        print(f"\nPeople센터 직원 중 데이터가 있는 직원:")
        for emp in people_with_data[:5]:  # 상위 5명만
            # 각 직원의 데이터 확인
            claim_count = len(claim_df[claim_df['사번'] == emp])
            tag_count = len(tag_df[tag_df['사번'] == emp])
            emp_info = org_df[org_df['사번'] == emp].iloc[0]
            print(f"  - {emp} ({emp_info['성명']}): claim={claim_count}행, tag={tag_count}행")
            
            # 첫 번째 직원의 세부 정보 확인
            if emp == people_with_data[0]:
                print(f"\n    첫 번째 직원 {emp} 상세:")
                # claim 데이터 날짜 범위
                emp_claim = claim_df[claim_df['사번'] == emp]
                if not emp_claim.empty:
                    dates = emp_claim['근무일'].unique()
                    print(f"    근무일 범위: {min(dates)} ~ {max(dates)}")
                # tag 데이터 날짜 범위
                emp_tag = tag_df[tag_df['사번'] == emp]
                if not emp_tag.empty:
                    dates = emp_tag['ENTE_DT'].unique()
                    print(f"    태그 날짜 범위: {min(dates)} ~ {max(dates)}")
    
    # 데이터가 많은 직원 샘플
    print(f"\n데이터가 많은 직원 샘플 (상위 5명):")
    for emp in list(common_employees)[:5]:
        claim_count = len(claim_df[claim_df['사번'] == emp])
        tag_count = len(tag_df[tag_df['사번'] == emp])
        emp_info = org_df[org_df['사번'] == emp]
        name = emp_info.iloc[0]['성명'] if not emp_info.empty else '이름없음'
        dept = emp_info.iloc[0]['부서명'] if not emp_info.empty else '부서없음'
        print(f"  - {emp} ({name}, {dept}): claim={claim_count}행, tag={tag_count}행")

if __name__ == "__main__":
    find_valid_employees()