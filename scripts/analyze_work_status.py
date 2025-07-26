#!/usr/bin/env python3
"""
work_status 분포 분석
"""

import pandas as pd
import sys
import os
from datetime import datetime, timedelta, date

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ui.components.individual_dashboard import IndividualDashboard
from src.database import DatabaseManager

def analyze_work_status():
    """work_status 분포 분석"""
    
    # DB 매니저와 대시보드 초기화
    db_manager = DatabaseManager()
    dashboard = IndividualDashboard(db_manager)
    
    # 테스트 대상
    employee_id = '20240596'
    selected_date = date(2025, 6, 2)
    
    print(f"\n=== {employee_id} 직원의 {selected_date} work_status 분석 ===\n")
    
    # 데이터 가져오기
    daily_data = dashboard.get_daily_tag_data(employee_id, selected_date)
    
    # 활동 분류
    classified_data = dashboard.classify_activities(daily_data, employee_id, selected_date)
    
    # work_status 분포
    print("=== work_status 분포 ===")
    if 'work_status' in classified_data.columns:
        status_counts = classified_data['work_status'].value_counts()
        for status, count in status_counts.items():
            print(f"{status}: {count}건")
    else:
        print("work_status 컬럼이 없습니다.")
    
    # work_status별 duration 합계
    print("\n=== work_status별 duration 합계 ===")
    if 'work_status' in classified_data.columns:
        status_duration = classified_data.groupby('work_status')['duration_minutes'].sum()
        for status, minutes in status_duration.items():
            print(f"{status}: {minutes:.1f}분 = {minutes/60:.1f}시간")
    
    # work_status가 'W'인 레코드 샘플
    print("\n=== work_status가 'W'인 레코드 샘플 ===")
    work_records = classified_data[classified_data['work_status'] == 'W']
    print(f"총 {len(work_records)}건")
    if len(work_records) > 0:
        for idx, row in work_records.head(10).iterrows():
            print(f"  - {row['datetime']}: {row['activity_code']} @ {row['DR_NM']} ({row['duration_minutes']:.1f}분)")
    
    # EQUIPMENT_OPERATION의 work_status 확인
    print("\n=== EQUIPMENT_OPERATION의 work_status 분포 ===")
    equipment_ops = classified_data[classified_data['activity_code'] == 'EQUIPMENT_OPERATION']
    if len(equipment_ops) > 0:
        equipment_status = equipment_ops['work_status'].value_counts()
        for status, count in equipment_status.items():
            print(f"{status}: {count}건")
        
        # 시간대별 분포
        print("\n=== EQUIPMENT_OPERATION 시간대별 분포 ===")
        equipment_ops['hour'] = equipment_ops['datetime'].dt.hour
        hour_counts = equipment_ops['hour'].value_counts().sort_index()
        for hour, count in hour_counts.items():
            print(f"{hour:02d}시: {count}건")
    
    # 퇴근 시간 찾기
    commute_out = classified_data[classified_data['activity_code'] == 'COMMUTE_OUT']
    if len(commute_out) > 0:
        commute_out_time = commute_out.iloc[0]['datetime']
        print(f"\n퇴근 시간: {commute_out_time}")
        
        # 퇴근 후 데이터
        after_commute = classified_data[classified_data['datetime'] > commute_out_time]
        print(f"퇴근 후 데이터: {len(after_commute)}건")
        
        if len(after_commute) > 0:
            after_status = after_commute['work_status'].value_counts()
            print("\n퇴근 후 work_status 분포:")
            for status, count in after_status.items():
                print(f"  {status}: {count}건")

if __name__ == "__main__":
    analyze_work_status()