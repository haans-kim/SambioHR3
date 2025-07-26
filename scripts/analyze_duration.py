#!/usr/bin/env python3
"""
duration 계산 분석
"""

import pandas as pd
import sys
import os
from datetime import datetime, timedelta, date

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ui.components.individual_dashboard import IndividualDashboard
from src.database import DatabaseManager

def analyze_duration():
    """duration 계산 분석"""
    
    # DB 매니저와 대시보드 초기화
    db_manager = DatabaseManager()
    dashboard = IndividualDashboard(db_manager)
    
    # 테스트 대상
    employee_id = '20240596'
    selected_date = date(2025, 6, 2)
    
    print(f"\n=== {employee_id} 직원의 {selected_date} Duration 분석 ===\n")
    
    # 데이터 가져오기
    daily_data = dashboard.get_daily_tag_data(employee_id, selected_date)
    
    # 활동 분류
    classified_data = dashboard.classify_activities(daily_data, employee_id, selected_date)
    
    # Duration 분석
    print('Duration 분석:')
    print(f'전체 레코드 수: {len(classified_data)}')
    print(f'총 duration 합계: {classified_data["duration_minutes"].sum():.1f}분 = {classified_data["duration_minutes"].sum()/60:.1f}시간')
    print()
    
    # EQUIPMENT_OPERATION만 확인
    equipment_ops = classified_data[classified_data['activity_code'] == 'EQUIPMENT_OPERATION']
    print(f'EQUIPMENT_OPERATION 레코드 수: {len(equipment_ops)}')
    print(f'EQUIPMENT_OPERATION duration 합계: {equipment_ops["duration_minutes"].sum():.1f}분 = {equipment_ops["duration_minutes"].sum()/60:.1f}시간')
    print(f'EQUIPMENT_OPERATION 평균 duration: {equipment_ops["duration_minutes"].mean():.1f}분')
    print(f'EQUIPMENT_OPERATION 최대 duration: {equipment_ops["duration_minutes"].max():.1f}분')
    print(f'EQUIPMENT_OPERATION 최소 duration: {equipment_ops["duration_minutes"].min():.1f}분')
    print()
    
    # 30분 이상인 것들 확인
    long_durations = equipment_ops[equipment_ops['duration_minutes'] > 30]
    print(f'30분 초과 EQUIPMENT_OPERATION: {len(long_durations)}건')
    if len(long_durations) > 0:
        print('샘플:')
        for idx, row in long_durations.head(5).iterrows():
            print(f'  - {row["datetime"]}: {row["duration_minutes"]:.1f}분')
    print()
    
    # 모든 레코드의 datetime 확인
    print('시간 순서 확인 (처음 10개):')
    for i in range(min(10, len(classified_data))):
        row = classified_data.iloc[i]
        print(f'{i}: {row["datetime"]} - {row["activity_code"]} - {row["duration_minutes"]:.1f}분')
    
    # 중복 시간 확인
    print('\n중복된 datetime 확인:')
    duplicated_times = classified_data[classified_data['datetime'].duplicated()]
    print(f'중복된 시간: {len(duplicated_times)}건')
    if len(duplicated_times) > 0:
        print('중복 샘플:')
        for idx, row in duplicated_times.head(5).iterrows():
            print(f'  - {row["datetime"]}: {row["activity_code"]}')
    
    # 실제 근무 시간과 비교
    work_start = classified_data['datetime'].min()
    work_end = classified_data['datetime'].max()
    total_hours = (work_end - work_start).total_seconds() / 3600
    print(f'\n실제 근무 시간: {work_start} ~ {work_end} = {total_hours:.1f}시간')
    
    # activity_type별 집계
    print('\nactivity_type별 duration 합계:')
    type_summary = classified_data.groupby('activity_type')['duration_minutes'].sum()
    for act_type, minutes in type_summary.items():
        print(f'  {act_type}: {minutes:.1f}분 = {minutes/60:.1f}시간')
    
    # Fill gaps 테스트
    print('\n=== Fill Gaps 테스트 ===')
    filled_data = dashboard._fill_time_gaps(classified_data)
    print(f'채우기 전: {len(classified_data)}건')
    print(f'채우기 후: {len(filled_data)}건')
    print(f'채우기 후 총 duration: {filled_data["duration_minutes"].sum():.1f}분 = {filled_data["duration_minutes"].sum()/60:.1f}시간')
    
    # activity_type별 집계 (fill 후)
    print('\nFill 후 activity_type별 duration 합계:')
    filled_type_summary = filled_data.groupby('activity_type')['duration_minutes'].sum()
    for act_type, minutes in filled_type_summary.items():
        print(f'  {act_type}: {minutes:.1f}분 = {minutes/60:.1f}시간')
    
if __name__ == "__main__":
    analyze_duration()