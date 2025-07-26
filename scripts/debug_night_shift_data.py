#!/usr/bin/env python3
"""
야간 근무자 데이터 범위 디버깅
"""

import pandas as pd
import sys
import os
from datetime import datetime, timedelta, date

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ui.components.individual_dashboard import IndividualDashboard
from src.database import DatabaseManager

def debug_night_shift_data():
    """야간 근무자 데이터 범위 확인"""
    
    # DB 매니저와 대시보드 초기화
    db_manager = DatabaseManager()
    dashboard = IndividualDashboard(db_manager)
    
    # 테스트 대상
    employee_id = '20240596'
    selected_date = date(2025, 6, 2)
    
    print(f"\n=== {employee_id} 직원의 {selected_date} 데이터 범위 확인 ===\n")
    
    # 데이터 가져오기
    daily_data = dashboard.get_daily_tag_data(employee_id, selected_date)
    
    if daily_data is None or daily_data.empty:
        print("데이터가 없습니다.")
        return
    
    print(f"전체 데이터: {len(daily_data)}건")
    print(f"시작: {daily_data['datetime'].min()}")
    print(f"종료: {daily_data['datetime'].max()}")
    
    # 시간대별 데이터 확인
    print("\n시간대별 데이터 분포:")
    for hour in range(24):
        hour_data = daily_data[daily_data['datetime'].dt.hour == hour]
        if len(hour_data) > 0:
            print(f"  {hour:02d}시: {len(hour_data)}건")
    
    # COMMUTE_OUT 찾기
    print("\n출퇴근 태그:")
    commute_in = daily_data[daily_data['INOUT_GB'] == '입문']
    commute_out = daily_data[daily_data['INOUT_GB'] == '출문']
    
    print(f"입문: {len(commute_in)}건")
    for idx, row in commute_in.iterrows():
        print(f"  - {row['datetime']}: {row['DR_NM']}")
    
    print(f"출문: {len(commute_out)}건")
    for idx, row in commute_out.iterrows():
        print(f"  - {row['datetime']}: {row['DR_NM']}")
    
    # 활동 분류 후 COMMUTE_OUT 확인
    classified_data = dashboard.classify_activities(daily_data, employee_id, selected_date)
    
    print("\n분류 후 출퇴근 활동:")
    commute_activities = classified_data[classified_data['activity_code'].isin(['COMMUTE_IN', 'COMMUTE_OUT'])]
    for idx, row in commute_activities.iterrows():
        print(f"  - {row['datetime']}: {row['activity_code']}")
    
    # 퇴근 시간 이후 데이터
    if 'COMMUTE_OUT' in classified_data['activity_code'].values:
        commute_out_time = classified_data[classified_data['activity_code'] == 'COMMUTE_OUT']['datetime'].iloc[0]
        print(f"\n퇴근 시간: {commute_out_time}")
        
        after_commute = classified_data[classified_data['datetime'] > commute_out_time]
        print(f"퇴근 후 데이터: {len(after_commute)}건")
        
        if len(after_commute) > 0:
            print("퇴근 후 데이터 샘플:")
            for idx, row in after_commute.head(10).iterrows():
                print(f"  - {row['datetime']}: {row.get('activity_code', 'N/A')}")

if __name__ == "__main__":
    debug_night_shift_data()