#!/usr/bin/env python3
"""
전이 확률 데이터를 코드에서 사용할 수 있는 형태로 추출
"""

import pandas as pd
import json

def extract_transition_data():
    """전이 확률 데이터 추출 및 변환"""
    
    file_path = '/Users/hanskim/Project/SambioHR2/doc/tag_transition_probabilities 1.xlsx'
    
    # 전체 데이터 읽기
    df_all = pd.read_excel(file_path, sheet_name='전체데이터')
    
    # 태그 조합별, 시간 간격별 최대 확률 상태와 확률 추출
    transition_probs = {}
    
    for _, row in df_all.iterrows():
        tag_combo = row['태그조합']
        time_interval = row['시간간격']
        state = row['추정상태']
        prob = row['확률']
        
        if tag_combo not in transition_probs:
            transition_probs[tag_combo] = {}
        
        if time_interval not in transition_probs[tag_combo]:
            transition_probs[tag_combo][time_interval] = {}
        
        transition_probs[tag_combo][time_interval][state] = prob
    
    # 상태별 확률 요약 읽기
    df_summary = pd.read_excel(file_path, sheet_name='상태별확률요약')
    
    # 상태 매핑
    state_mapping = {
        '업무': 'work',
        '경유': 'movement',
        '비업무': 'non_work',
        '휴게': 'rest',
        '회의': 'meeting',
        '교육': 'training',
        '준비': 'preparation',
        '출입(IN)': 'entry',
        '출입(OUT)': 'exit'
    }
    
    # 시간 간격 매핑
    time_mapping = {
        '<5분': 'under_5min',
        '5-30분': '5_to_30min',
        '30분-2시간': '30min_to_2hr',
        '>2시간': 'over_2hr'
    }
    
    # 구조화된 데이터 생성
    structured_data = {
        'transition_probabilities': {},
        'time_intervals': {
            'under_5min': {'min': 0, 'max': 5},
            '5_to_30min': {'min': 5, 'max': 30},
            '30min_to_2hr': {'min': 30, 'max': 120},
            'over_2hr': {'min': 120, 'max': float('inf')}
        },
        'state_mapping': state_mapping,
        'tag_descriptions': {
            'G1': '주업무 수행하는 공간',
            'G2': '작업 전 준비 수행 공간',
            'G3': '회의 등 협업이 주로 이루어지는 공식 공간',
            'G4': '정기/비정기 교육이 이루어지는 공간',
            'N1': '식당 구역',
            'N2': '휴게 공간',
            'N3': '화장실 등 개인적인 용무를 위한 공간',
            'T1': '복도 계단 승강기 등 장거리 연결부',
            'T2': '입문',
            'T3': '출문'
        }
    }
    
    # 전이 확률 변환
    for tag_combo, time_data in transition_probs.items():
        structured_data['transition_probabilities'][tag_combo] = {}
        
        for time_interval, state_probs in time_data.items():
            time_key = time_mapping.get(time_interval, time_interval)
            structured_data['transition_probabilities'][tag_combo][time_key] = {}
            
            # 상태 이름 영문으로 변환
            for state, prob in state_probs.items():
                state_en = state_mapping.get(state, state.lower())
                structured_data['transition_probabilities'][tag_combo][time_key][state_en] = prob
    
    # JSON 파일로 저장
    output_path = '/Users/hanskim/Project/SambioHR2/data/tag_transition_probabilities.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(structured_data, f, ensure_ascii=False, indent=2)
    
    print(f"전이 확률 데이터를 {output_path}에 저장했습니다.")
    
    # 일부 데이터 출력하여 확인
    print("\n샘플 데이터:")
    print("G1→G1 전이 확률:")
    for time_interval, probs in structured_data['transition_probabilities'].get('G1→G1', {}).items():
        print(f"  {time_interval}: {probs}")

if __name__ == "__main__":
    extract_transition_data()