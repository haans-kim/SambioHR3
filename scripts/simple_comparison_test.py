"""
간단한 싱글톤 vs 멀티프로세싱 비교 테스트
ADC T/F 조직 분석 비교
"""

import sys
import os
from datetime import date, datetime
import time

# 프로젝트 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import get_database_manager, get_pickle_manager
from src.analysis import IndividualAnalyzer
from src.ui.components.individual_dashboard import IndividualDashboard
import pandas as pd


def find_adc_tf_members():
    """ADC T/F 조직 구성원 찾기"""
    pickle_manager = get_pickle_manager()
    org_data = pickle_manager.load_dataframe('organization_data')
    
    # ADC가 포함된 팀/그룹 찾기
    adc_members = org_data[
        (org_data['팀'].str.contains('ADC', na=False)) | 
        (org_data['그룹'].str.contains('ADC', na=False))
    ]
    
    if adc_members.empty:
        # 첫 번째 팀 선택
        first_team = org_data['팀'].dropna().iloc[0]
        adc_members = org_data[org_data['팀'] == first_team]
        print(f"ADC를 찾을 수 없어 '{first_team}' 팀을 사용합니다.")
    
    # 최대 5명으로 제한
    employee_ids = adc_members['사번'].astype(str).tolist()[:5]
    return employee_ids


def run_singleton_test(employee_ids, start_date, end_date):
    """싱글톤 모드 테스트"""
    print("\n🔵 싱글톤 모드 테스트")
    print("-" * 50)
    
    db_manager = get_database_manager()
    individual_analyzer = IndividualAnalyzer(db_manager)
    dashboard = IndividualDashboard(individual_analyzer)
    
    start_time = time.time()
    success_count = 0
    results = []
    
    for emp_id in employee_ids:
        for day in pd.date_range(start_date, end_date):
            try:
                # 데이터 로드
                daily_data = dashboard.load_employee_daily_data(emp_id, day.date())
                if daily_data is None or daily_data.empty:
                    continue
                
                # 활동 분류
                classified_data = dashboard.classify_activities(daily_data)
                if classified_data is None or classified_data.empty:
                    continue
                
                # 분석
                analysis_result = dashboard.analyze_daily_data(
                    emp_id, day.date(), classified_data
                )
                
                if analysis_result:
                    success_count += 1
                    # 주요 지표 저장
                    results.append({
                        'employee_id': emp_id,
                        'date': day.date(),
                        'total_hours': analysis_result.get('total_hours', 0),
                        'activity_count': len(analysis_result.get('activity_summary', {}))
                    })
                    
            except Exception as e:
                print(f"  오류 {emp_id} {day.date()}: {e}")
    
    end_time = time.time()
    
    print(f"  처리 시간: {end_time - start_time:.1f}초")
    print(f"  성공: {success_count}건")
    print(f"  첫 번째 결과 예시: {results[0] if results else 'None'}")
    
    return {
        'time': end_time - start_time,
        'success': success_count,
        'results': results
    }


def run_multiprocessing_test(employee_ids, start_date, end_date):
    """멀티프로세싱 모드 테스트 (간단 버전)"""
    print("\n🟢 멀티프로세싱 모드 테스트")
    print("-" * 50)
    
    from concurrent.futures import ProcessPoolExecutor
    import multiprocessing
    
    def analyze_task(args):
        """단일 작업 분석"""
        emp_id, day = args
        try:
            from src.database import get_database_manager
            from src.analysis import IndividualAnalyzer
            from src.ui.components.individual_dashboard import IndividualDashboard
            
            db_manager = get_database_manager()
            individual_analyzer = IndividualAnalyzer(db_manager)
            dashboard = IndividualDashboard(individual_analyzer)
            
            # 데이터 로드
            daily_data = dashboard.load_employee_daily_data(emp_id, day)
            if daily_data is None or daily_data.empty:
                return None
            
            # 활동 분류
            classified_data = dashboard.classify_activities(daily_data)
            if classified_data is None or classified_data.empty:
                return None
            
            # 분석
            analysis_result = dashboard.analyze_daily_data(
                emp_id, day, classified_data
            )
            
            if analysis_result:
                return {
                    'employee_id': emp_id,
                    'date': day,
                    'total_hours': analysis_result.get('total_hours', 0),
                    'activity_count': len(analysis_result.get('activity_summary', {}))
                }
            return None
            
        except Exception as e:
            print(f"워커 오류: {e}")
            return None
    
    # 작업 목록 생성
    tasks = []
    for emp_id in employee_ids:
        for day in pd.date_range(start_date, end_date):
            tasks.append((emp_id, day.date()))
    
    start_time = time.time()
    results = []
    
    # 멀티프로세싱 실행
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(analyze_task, task) for task in tasks]
        
        for future in futures:
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                print(f"  Future 오류: {e}")
    
    end_time = time.time()
    
    print(f"  처리 시간: {end_time - start_time:.1f}초")
    print(f"  성공: {len(results)}건")
    print(f"  첫 번째 결과 예시: {results[0] if results else 'None'}")
    
    return {
        'time': end_time - start_time,
        'success': len(results),
        'results': results
    }


def compare_results(singleton_result, multiprocessing_result):
    """결과 비교"""
    print("\n📊 결과 비교")
    print("=" * 50)
    
    # 시간 비교
    print(f"처리 시간:")
    print(f"  싱글톤: {singleton_result['time']:.1f}초")
    print(f"  멀티프로세싱: {multiprocessing_result['time']:.1f}초")
    print(f"  속도 향상: {singleton_result['time']/multiprocessing_result['time']:.1f}배")
    
    # 성공률 비교
    print(f"\n성공률:")
    print(f"  싱글톤: {singleton_result['success']}건")
    print(f"  멀티프로세싱: {multiprocessing_result['success']}건")
    
    # 데이터 일치성 확인
    print(f"\n데이터 일치성:")
    
    # 같은 직원-날짜의 결과 비교
    singleton_dict = {(r['employee_id'], r['date']): r for r in singleton_result['results']}
    multiprocessing_dict = {(r['employee_id'], r['date']): r for r in multiprocessing_result['results']}
    
    matching_keys = set(singleton_dict.keys()) & set(multiprocessing_dict.keys())
    
    if matching_keys:
        # 첫 번째 매칭 결과 비교
        key = list(matching_keys)[0]
        s_result = singleton_dict[key]
        m_result = multiprocessing_dict[key]
        
        print(f"  예시 ({key[0]}, {key[1]}):")
        print(f"    싱글톤 - 총 시간: {s_result['total_hours']:.1f}시간, 활동: {s_result['activity_count']}개")
        print(f"    멀티프로세싱 - 총 시간: {m_result['total_hours']:.1f}시간, 활동: {m_result['activity_count']}개")
        
        # 차이 계산
        time_diff = abs(s_result['total_hours'] - m_result['total_hours'])
        activity_diff = abs(s_result['activity_count'] - m_result['activity_count'])
        
        print(f"    차이 - 시간: {time_diff:.2f}시간, 활동 수: {activity_diff}개")


def main():
    """메인 실행"""
    print("=" * 50)
    print("싱글톤 vs 멀티프로세싱 비교 테스트")
    print("=" * 50)
    
    # ADC T/F 구성원 찾기
    employee_ids = find_adc_tf_members()
    print(f"\n테스트 대상: {len(employee_ids)}명")
    print(f"직원 ID: {', '.join(employee_ids)}")
    
    # 날짜 설정
    start_date = date(2024, 6, 3)
    end_date = date(2024, 6, 5)
    print(f"분석 기간: {start_date} ~ {end_date}")
    
    # 싱글톤 테스트
    singleton_result = run_singleton_test(employee_ids, start_date, end_date)
    
    # 멀티프로세싱 테스트
    multiprocessing_result = run_multiprocessing_test(employee_ids, start_date, end_date)
    
    # 결과 비교
    compare_results(singleton_result, multiprocessing_result)


if __name__ == "__main__":
    main()