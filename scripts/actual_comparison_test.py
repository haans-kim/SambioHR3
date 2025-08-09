"""
실제 작동하는 싱글톤 vs 멀티프로세싱 비교 테스트
"""

import sys
import os
from datetime import date, datetime
import time
import hashlib
import json

# 프로젝트 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import get_database_manager, get_pickle_manager
from src.analysis import IndividualAnalyzer
import pandas as pd
import numpy as np
from multiprocessing import Pool
import pickle


def find_test_employees():
    """테스트용 직원 찾기"""
    pickle_manager = get_pickle_manager()
    org_data = pickle_manager.load_dataframe('organization_data')
    
    # ADC 팀 찾기
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
        analyzer = IndividualAnalyzer(db_manager)
        
        # 데이터 조회
        query = """
        SELECT * FROM tag_logs 
        WHERE employee_id = :employee_id 
        AND date(timestamp) = :analysis_date
        ORDER BY timestamp
        """
        
        params = {
            'employee_id': employee_id,
            'analysis_date': analysis_date.strftime('%Y-%m-%d')
        }
        
        data = db_manager.execute_query(query, params)
        
        if not data:
            return None
        
        # 간단한 분석 수행
        df = pd.DataFrame(data)
        
        # 주요 지표 계산
        result = {
            'employee_id': employee_id,
            'date': analysis_date.strftime('%Y-%m-%d'),
            'tag_count': len(df),
            'unique_locations': df['tag_location'].nunique() if 'tag_location' in df.columns else 0,
            'start_time': df['timestamp'].min() if 'timestamp' in df.columns else None,
            'end_time': df['timestamp'].max() if 'timestamp' in df.columns else None,
        }
        
        # 체류시간 계산
        if result['start_time'] and result['end_time']:
            start = pd.to_datetime(result['start_time'])
            end = pd.to_datetime(result['end_time'])
            result['total_hours'] = (end - start).total_seconds() / 3600
        else:
            result['total_hours'] = 0
        
        # 결과 해시 (비교용)
        result['data_hash'] = hashlib.md5(
            json.dumps(result, sort_keys=True, default=str).encode()
        ).hexdigest()[:8]
        
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
        
        # 데이터 조회
        query = """
        SELECT * FROM tag_logs 
        WHERE employee_id = :employee_id 
        AND date(timestamp) = :analysis_date
        ORDER BY timestamp
        """
        
        params = {
            'employee_id': employee_id,
            'analysis_date': analysis_date.strftime('%Y-%m-%d')
        }
        
        data = db_manager.execute_query(query, params)
        
        if not data:
            return None
        
        # 간단한 분석 수행
        df = pd.DataFrame(data)
        
        # 주요 지표 계산
        result = {
            'employee_id': employee_id,
            'date': analysis_date.strftime('%Y-%m-%d'),
            'tag_count': len(df),
            'unique_locations': df['tag_location'].nunique() if 'tag_location' in df.columns else 0,
            'start_time': df['timestamp'].min() if 'timestamp' in df.columns else None,
            'end_time': df['timestamp'].max() if 'timestamp' in df.columns else None,
        }
        
        # 체류시간 계산
        if result['start_time'] and result['end_time']:
            start = pd.to_datetime(result['start_time'])
            end = pd.to_datetime(result['end_time'])
            result['total_hours'] = (end - start).total_seconds() / 3600
        else:
            result['total_hours'] = 0
        
        # 결과 해시 (비교용)
        result['data_hash'] = hashlib.md5(
            json.dumps(result, sort_keys=True, default=str).encode()
        ).hexdigest()[:8]
        
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
                print(f"  ✓ {emp_id} - {day.date()}: {result['tag_count']}개 태그, {result['total_hours']:.1f}시간")
    
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
        print(f"  ✓ {result['employee_id']} - {result['date']}: {result['tag_count']}개 태그, {result['total_hours']:.1f}시간")
    
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
        if (s_data['tag_count'] != m_data['tag_count'] or 
            abs(s_data['total_hours'] - m_data['total_hours']) > 0.1 or
            s_data['data_hash'] != m_data['data_hash']):
            
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
            print(f"    싱글톤: 태그 {s['tag_count']}개, {s['total_hours']:.1f}시간, hash={s['data_hash']}")
            print(f"    멀티프로세싱: 태그 {m['tag_count']}개, {m['total_hours']:.1f}시간, hash={m['data_hash']}")
    else:
        print(f"  ✅ 모든 데이터 일치!")
    
    # 해시 비교
    s_hashes = set(r['data_hash'] for r in singleton_data['results'])
    m_hashes = set(r['data_hash'] for r in multiprocessing_data['results'])
    
    if s_hashes == m_hashes:
        print(f"\n✅ 데이터 해시 완전 일치")
    else:
        print(f"\n⚠️  데이터 해시 불일치")
        print(f"  싱글톤 고유: {len(s_hashes - m_hashes)}개")
        print(f"  멀티프로세싱 고유: {len(m_hashes - s_hashes)}개")


def main():
    print("="*60)
    print("싱글톤 vs 멀티프로세싱 실제 비교 테스트")
    print("="*60)
    
    # 테스트 직원 찾기
    employees = find_test_employees()
    print(f"\n테스트 대상: {len(employees)}명")
    for emp_id, emp_name in employees:
        print(f"  - {emp_id} ({emp_name})")
    
    # 날짜 설정
    start_date = date(2024, 6, 3)
    end_date = date(2024, 6, 5)
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