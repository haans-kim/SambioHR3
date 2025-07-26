#!/usr/bin/env python3
"""
태그 전이 확률 엑셀 파일 읽기
"""

import pandas as pd
import sys
import os

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def read_transition_probabilities():
    """태그 전이 확률 엑셀 파일 읽기"""
    
    file_path = '/Users/hanskim/Project/SambioHR2/doc/tag_transition_probabilities 1.xlsx'
    
    try:
        # 엑셀 파일의 모든 시트 이름 가져오기
        xl_file = pd.ExcelFile(file_path)
        sheet_names = xl_file.sheet_names
        
        print(f"엑셀 파일 시트 목록: {sheet_names}")
        print(f"총 {len(sheet_names)}개의 시트\n")
        
        # 각 시트 내용 확인
        for sheet_name in sheet_names:
            print(f"\n{'='*60}")
            print(f"시트: {sheet_name}")
            print('='*60)
            
            try:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                
                print(f"데이터 크기: {df.shape}")
                print(f"컬럼: {list(df.columns)}")
                
                # 처음 10행 출력
                print(f"\n처음 10행:")
                print(df.head(10).to_string())
                
                # 데이터 타입별 정보
                if not df.empty:
                    print(f"\n데이터 타입:")
                    print(df.dtypes)
                    
                    # 수치 데이터가 있으면 요약 통계
                    numeric_cols = df.select_dtypes(include=['number']).columns
                    if len(numeric_cols) > 0:
                        print(f"\n수치 데이터 요약:")
                        print(df[numeric_cols].describe())
                
            except Exception as e:
                print(f"시트 읽기 오류: {e}")
                
    except Exception as e:
        print(f"파일 읽기 오류: {e}")

if __name__ == "__main__":
    read_transition_probabilities()