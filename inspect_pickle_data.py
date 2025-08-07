#!/usr/bin/env python3
"""
Pickle 파일 데이터 구조 확인 스크립트
"""

import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.data_processing import PickleManager

def inspect_pickle_data():
    """Pickle 파일 데이터 구조 확인"""
    
    pickle_mgr = PickleManager(base_path="data/pickles")
    
    # claim_data 확인
    print("=== claim_data 구조 확인 ===")
    try:
        claim_df = pickle_mgr.load_dataframe('claim_data')
        print(f"Shape: {claim_df.shape}")
        print(f"Columns: {list(claim_df.columns)}")
        print(f"\n첫 5행:")
        print(claim_df.head())
        
        # 사번 타입 확인
        if '사번' in claim_df.columns:
            print(f"\n사번 타입: {claim_df['사번'].dtype}")
            print(f"사번 샘플: {claim_df['사번'].head().tolist()}")
            
            # 20110198 직원 데이터 확인
            emp_data = claim_df[claim_df['사번'] == 20110198]
            if emp_data.empty:
                emp_data = claim_df[claim_df['사번'] == '20110198']
            
            print(f"\n직원 20110198 데이터: {len(emp_data)}행")
            if not emp_data.empty:
                print(emp_data.head())
    except Exception as e:
        print(f"claim_data 로드 실패: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # tag_data 확인
    print("=== tag_data 구조 확인 ===")
    try:
        tag_df = pickle_mgr.load_dataframe('tag_data')
        print(f"Shape: {tag_df.shape}")
        print(f"Columns: {list(tag_df.columns)}")
        print(f"\n첫 5행:")
        print(tag_df.head())
        
        # EMP_NO 타입 확인
        if 'EMP_NO' in tag_df.columns:
            print(f"\nEMP_NO 타입: {tag_df['EMP_NO'].dtype}")
            print(f"EMP_NO 샘플: {tag_df['EMP_NO'].head().tolist()}")
            
            # 20110198 직원 데이터 확인
            emp_data = tag_df[tag_df['EMP_NO'] == 20110198]
            if emp_data.empty:
                emp_data = tag_df[tag_df['EMP_NO'] == '20110198']
            
            print(f"\n직원 20110198 데이터: {len(emp_data)}행")
            if not emp_data.empty:
                print(emp_data.head())
    except Exception as e:
        print(f"tag_data 로드 실패: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # organization_data 확인
    print("=== organization_data 구조 확인 ===")
    try:
        org_df = pickle_mgr.load_dataframe('organization_data')
        print(f"Shape: {org_df.shape}")
        print(f"Columns: {list(org_df.columns)}")
        print(f"\n첫 5행:")
        print(org_df.head())
        
        # People센터 데이터 확인
        if 'CEN_NM' in org_df.columns or '센터' in org_df.columns:
            for col in org_df.columns:
                if 'People' in str(org_df[col].unique()):
                    print(f"\nPeople센터 발견 (컬럼: {col})")
                    people_data = org_df[org_df[col].str.contains('People', na=False)]
                    print(f"People센터 직원 수: {len(people_data)}명")
                    if '사번' in people_data.columns:
                        print(f"사번 샘플: {people_data['사번'].head(10).tolist()}")
                    break
    except Exception as e:
        print(f"organization_data 로드 실패: {e}")

if __name__ == "__main__":
    inspect_pickle_data()