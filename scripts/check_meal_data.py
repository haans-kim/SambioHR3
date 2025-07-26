#!/usr/bin/env python3
"""
식사 데이터 확인 스크립트
특정 사번의 식사 데이터를 확인합니다.
"""

import pandas as pd
import sys
import os
from datetime import datetime, timedelta

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_processing import PickleManager

def check_meal_data(employee_id='20240596', check_date='2025-06-02'):
    """특정 직원의 식사 데이터 확인"""
    
    pickle_manager = PickleManager()
    meal_data = pickle_manager.load_dataframe(name='meal_data')
    
    if meal_data is None:
        print("식사 데이터가 없습니다.")
        return
    
    print(f"전체 식사 데이터: {len(meal_data)}행")
    print(f"컬럼: {list(meal_data.columns)}")
    
    # 날짜 컬럼 찾기
    date_column = None
    if '취식일시' in meal_data.columns:
        date_column = '취식일시'
    elif 'meal_datetime' in meal_data.columns:
        date_column = 'meal_datetime'
    
    if date_column:
        meal_data[date_column] = pd.to_datetime(meal_data[date_column])
    
    # 사번 컬럼 찾기
    emp_column = None
    if '사번' in meal_data.columns:
        emp_column = '사번'
    elif 'employee_id' in meal_data.columns:
        emp_column = 'employee_id'
    
    if emp_column and date_column:
        # 사번 변환
        try:
            emp_id = int(employee_id)
            meal_data[emp_column] = pd.to_numeric(meal_data[emp_column], errors='coerce')
            employee_meals = meal_data[meal_data[emp_column] == emp_id]
        except:
            meal_data[emp_column] = meal_data[emp_column].astype(str)
            employee_meals = meal_data[meal_data[emp_column] == str(employee_id)]
        
        print(f"\n{employee_id} 직원의 전체 식사 데이터: {len(employee_meals)}건")
        
        # 날짜별로 정렬
        if not employee_meals.empty:
            employee_meals = employee_meals.sort_values(date_column)
            
            # 최근 10일간 데이터 표시
            check_date_obj = pd.to_datetime(check_date)
            start_date = check_date_obj - timedelta(days=5)
            end_date = check_date_obj + timedelta(days=5)
            
            recent_meals = employee_meals[
                (employee_meals[date_column] >= start_date) & 
                (employee_meals[date_column] <= end_date)
            ]
            
            print(f"\n{start_date.date()} ~ {end_date.date()} 기간 식사 데이터:")
            for idx, row in recent_meals.iterrows():
                meal_time = row[date_column]
                meal_type = row.get('식사대분류', row.get('meal_category', 'N/A'))
                location = row.get('배식구', row.get('식당명', 'N/A'))
                print(f"  - {meal_time}: {meal_type} @ {location}")
        
        # 특정 날짜 (6월 1일, 6월 2일) 데이터 확인
        june1 = pd.to_datetime('2025-06-01')
        june2 = pd.to_datetime('2025-06-02')
        
        june1_meals = employee_meals[employee_meals[date_column].dt.date == june1.date()]
        june2_meals = employee_meals[employee_meals[date_column].dt.date == june2.date()]
        
        print(f"\n2025-06-01 식사: {len(june1_meals)}건")
        for idx, row in june1_meals.iterrows():
            meal_time = row[date_column]
            meal_type = row.get('식사대분류', row.get('meal_category', 'N/A'))
            print(f"  - {meal_time.strftime('%H:%M')}: {meal_type}")
            
        print(f"\n2025-06-02 식사: {len(june2_meals)}건")
        for idx, row in june2_meals.iterrows():
            meal_time = row[date_column]
            meal_type = row.get('식사대분류', row.get('meal_category', 'N/A'))
            print(f"  - {meal_time.strftime('%H:%M')}: {meal_type}")

if __name__ == "__main__":
    check_meal_data()