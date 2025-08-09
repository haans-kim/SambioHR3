"""
간소화된 싱글톤 vs 멀티프로세싱 비교 테스트
daily_work_data 테이블 사용하여 ADC T/F 조직 분석
"""

import sys
import os
from datetime import date, datetime
import time
import pandas as pd
from multiprocessing import Pool

# 프로젝트 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import get_database_manager, get_pickle_manager
from src.analysis import IndividualAnalyzer
from src.ui.components.individual_dashboard import IndividualDashboard


def find_test_employees():
    """테스트용 직원 찾기"""
    pickle_manager = get_pickle_manager()
    org_data = pickle_manager.load_dataframe('organization_data')
    
    # ADC T/F 조직 찾기
    adc_members = org_data[
        (org_data['팀'].str.contains('ADC', na=False)) | 
        (org_data['그룹'].str.contains('ADC', na=False))
    ]
    
    if adc_members.empty:
        # 대체: 첫 번째 팀의 5명
        first_team = org_data['팀'].dropna().iloc[0]
        adc_members = org_data[org_data['팀'] == first_team]
        print(f"테스트 조직: {first_team}")
    else:
        print(f"테스트 조직: ADC T/F")
    
    # 5명만 선택
    employee_ids = adc_members['사번'].astype(str).tolist()[:5]
    employee_names = adc_members['성명'].tolist()[:5]
    
    return list(zip(employee_ids, employee_names))


def singleton_analyze_employee(employee_id, employee_name, analysis_date):
    """싱글톤 방식으로 직원 분석"""
    try:
        db_manager = get_database_manager()
        
        # daily_work_data에서 데이터 조회
        query = """
        SELECT * FROM daily_work_data 
        WHERE employee_id = :employee_id 
        AND date(work_date) = :analysis_date
        """
        
        params = {
            'employee_id': employee_id,
            'analysis_date': analysis_date.strftime('%Y-%m-%d')
        }
        
        data = db_manager.execute_query(query, params)
        
        if not data:
            return None
        
        # 결과 생성
        result = {
            'employee_id': employee_id,
            'date': analysis_date.strftime('%Y-%m-%d'),
            'work_hours': data[0]['actual_work_time'] if data else 0,
            'meal_time': data[0]['meal_time'] if data else 0,
            'rest_time': data[0]['rest_time'] if data else 0,
            'efficiency': data[0]['efficiency_ratio'] if data else 0,
            'method': 'singleton'
        }
        
        return result
        
    except Exception as e:
        print(f"싱글톤 분석 오류 {employee_id}: {e}")
        return None


def parallel_analyze_employee(args):
    """병렬 처리용 직원 분석 함수"""
    employee_id, employee_name, analysis_date = args
    
    try:
        # 새로운 DB 연결 (프로세스별)
        from src.database import DatabaseManager
        db_manager = DatabaseManager()
        
        # daily_work_data에서 데이터 조회
        query = """
        SELECT * FROM daily_work_data 
        WHERE employee_id = :employee_id 
        AND date(work_date) = :analysis_date
        """
        
        params = {
            'employee_id': employee_id,
            'analysis_date': analysis_date.strftime('%Y-%m-%d')
        }
        
        data = db_manager.execute_query(query, params)
        
        if not data:
            return None
        
        # 결과 생성
        result = {
            'employee_id': employee_id,
            'date': analysis_date.strftime('%Y-%m-%d'),
            'work_hours': data[0]['actual_work_time'] if data else 0,
            'meal_time': data[0]['meal_time'] if data else 0,
            'rest_time': data[0]['rest_time'] if data else 0,
            'efficiency': data[0]['efficiency_ratio'] if data else 0,
            'method': 'multiprocessing'
        }
        
        return result
        
    except Exception as e:
        print(f"병렬 분석 오류 {employee_id}: {e}")
        return None


def run_singleton_test(employees, start_date, end_date):
    """싱글톤 모드 테스트"""
    print("\n🔵 싱글톤 모드 실행")
    print("-" * 60)
    
    start_time = time.time()
    results = []
    
    for emp_id, emp_name in employees:
        for day in pd.date_range(start_date, end_date):
            result = singleton_analyze_employee(emp_id, emp_name, day.date())
            if result:
                results.append(result)
                print(f"  ✓ {emp_id} - {day.date()}: {result['work_hours']:.1f}시간 근무")
    
    end_time = time.time()
    
    print(f"\n처리 시간: {end_time - start_time:.2f}초")
    print(f"성공: {len(results)}건")
    
    return {
        'time': end_time - start_time,
        'results': results
    }


def run_multiprocessing_test(employees, start_date, end_date):
    """멀티프로세싱 모드 테스트"""
    print("\n🟢 멀티프로세싱 모드 실행 (4 workers)")
    print("-" * 60)
    
    # 작업 목록 생성
    tasks = []
    for emp_id, emp_name in employees:
        for day in pd.date_range(start_date, end_date):
            tasks.append((emp_id, emp_name, day.date()))
    
    start_time = time.time()
    
    # 멀티프로세싱 실행
    with Pool(processes=4) as pool:
        results = pool.map(parallel_analyze_employee, tasks)
    
    # None 제거
    results = [r for r in results if r is not None]
    
    end_time = time.time()
    
    for result in results[:5]:  # 처음 5개만 출력
        print(f"  ✓ {result['employee_id']} - {result['date']}: {result['work_hours']:.1f}시간 근무")
    
    print(f"\n처리 시간: {end_time - start_time:.2f}초")
    print(f"성공: {len(results)}건")
    
    return {
        'time': end_time - start_time,
        'results': results
    }


def compare_results(singleton_data, multiprocessing_data):
    """결과 비교"""
    print("\n" + "="*60)
    print("📊 비교 결과")
    print("="*60)
    
    # 시간 비교
    s_time = singleton_data['time']
    m_time = multiprocessing_data['time']
    
    print(f"\n⏱️  처리 시간:")
    print(f"  싱글톤: {s_time:.2f}초")
    print(f"  멀티프로세싱: {m_time:.2f}초")
    if m_time > 0:
        print(f"  속도 향상: {s_time/m_time:.1f}배")
    
    # 결과 비교
    s_results = {(r['employee_id'], r['date']): r for r in singleton_data['results']}
    m_results = {(r['employee_id'], r['date']): r for r in multiprocessing_data['results']}
    
    print(f"\n📈 처리 결과:")
    print(f"  싱글톤: {len(s_results)}건")
    print(f"  멀티프로세싱: {len(m_results)}건")
    
    # 데이터 일치성 검사
    print(f"\n🔍 데이터 일치성:")
    
    matching_keys = set(s_results.keys()) & set(m_results.keys())
    differences = []
    
    for key in matching_keys:
        s_data = s_results[key]
        m_data = m_results[key]
        
        # 주요 지표 비교
        if (abs(s_data['work_hours'] - m_data['work_hours']) > 0.1 or 
            abs(s_data['meal_time'] - m_data['meal_time']) > 0.1 or
            abs(s_data['efficiency'] - m_data['efficiency']) > 0.01):
            
            differences.append({
                'key': key,
                'singleton': s_data,
                'multiprocessing': m_data
            })
    
    if differences:
        print(f"  ⚠️  차이 발견: {len(differences)}건")
        for diff in differences[:3]:  # 처음 3개만 출력
            key = diff['key']
            s = diff['singleton']
            m = diff['multiprocessing']
            print(f"\n  {key[0]} - {key[1]}:")
            print(f"    싱글톤: 근무 {s['work_hours']:.1f}시간, 효율 {s['efficiency']:.2f}")
            print(f"    멀티프로세싱: 근무 {m['work_hours']:.1f}시간, 효율 {m['efficiency']:.2f}")
    else:
        print(f"  ✅ 모든 데이터 일치!")


def main():
    print("="*60)
    print("싱글톤 vs 멀티프로세싱 간소화 비교 테스트")
    print("="*60)
    
    # 테스트 직원 찾기
    employees = find_test_employees()
    print(f"\n테스트 대상: {len(employees)}명")
    for emp_id, emp_name in employees:
        print(f"  - {emp_id} ({emp_name})")
    
    # 날짜 설정 (2025년)
    start_date = date(2025, 6, 3)
    end_date = date(2025, 6, 5)
    print(f"\n분석 기간: {start_date} ~ {end_date}")
    
    # 싱글톤 테스트
    singleton_data = run_singleton_test(employees, start_date, end_date)
    
    # 멀티프로세싱 테스트
    multiprocessing_data = run_multiprocessing_test(employees, start_date, end_date)
    
    # 결과 비교
    compare_results(singleton_data, multiprocessing_data)
    
    print("\n" + "="*60)
    print("테스트 완료")
    print("="*60)


if __name__ == "__main__":
    main()