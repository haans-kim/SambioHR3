#!/usr/bin/env python3
"""Pickle 데이터 구조 확인"""

import pandas as pd
import os
import sys

# 프로젝트 루트 경로 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from src.data_processing.pickle_manager import PickleManager

def check_pickle_structure():
    """Pickle 파일 구조 확인"""
    
    pickle_manager = PickleManager()
    
    # tag_data pickle 로드
    print("=== Tag Data Pickle 구조 확인 ===\n")
    
    tag_data = pickle_manager.load_dataframe('tag_data')
    if tag_data is not None:
        print(f"행 수: {len(tag_data)}")
        print(f"컬럼: {tag_data.columns.tolist()}\n")
        
        # 701-10-1-1 데이터 확인
        if 'DR_NO' in tag_data.columns:
            gate_data = tag_data[tag_data['DR_NO'] == '701-10-1-1']
            print(f"701-10-1-1 데이터: {len(gate_data)}개")
            
            if not gate_data.empty:
                print("\n샘플 데이터:")
                print(gate_data.head(3).to_string())
                
                # datetime 컬럼이 있는지 확인
                if 'datetime' in gate_data.columns:
                    # 2025-06-30 07:35 근처 데이터 확인
                    morning_data = gate_data[
                        (gate_data['datetime'].dt.date == pd.to_datetime('2025-06-30').date()) &
                        (gate_data['datetime'].dt.hour == 7) &
                        (gate_data['datetime'].dt.minute >= 30) &
                        (gate_data['datetime'].dt.minute <= 40)
                    ]
                    
                    if not morning_data.empty:
                        print(f"\n2025-06-30 07:35 근처 데이터:")
                        for idx, row in morning_data.iterrows():
                            print(f"  {row['datetime']} | {row.get('employee_id', 'N/A')} | {row.get('DR_NM', 'N/A')}")

if __name__ == "__main__":
    check_pickle_structure()