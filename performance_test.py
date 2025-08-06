"""
성능 측정 테스트 스크립트
individual_analyzer의 병목 구간 파악
"""

import time
import functools
from datetime import datetime, date
from contextlib import contextmanager
import pandas as pd
from typing import Dict, Any, List

from src.database import DatabaseManager
from src.analysis.individual_analyzer import IndividualAnalyzer
from src.analysis.organization_analyzer import OrganizationAnalyzer

# 시간 측정 데코레이터
def time_it(name: str, results: Dict[str, List[float]]):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            elapsed_time = time.time() - start_time
            
            if name not in results:
                results[name] = []
            results[name].append(elapsed_time)
            
            return result
        return wrapper
    return decorator

# 컨텍스트 매니저로 구간 측정
@contextmanager
def measure_section(name: str, results: Dict[str, List[float]]):
    start_time = time.time()
    try:
        yield
    finally:
        elapsed_time = time.time() - start_time
        if name not in results:
            results[name] = []
        results[name].append(elapsed_time)

def monkey_patch_analyzer(analyzer: IndividualAnalyzer, results: Dict[str, List[float]]):
    """IndividualAnalyzer의 메서드들을 시간 측정 버전으로 교체"""
    
    # 원본 메서드 저장
    original_get_data = analyzer._get_data
    original_apply_tag_based = analyzer._apply_tag_based_analysis
    original_analyze_work_time = analyzer._analyze_work_time
    original_analyze_shift = analyzer._analyze_shift_patterns
    original_analyze_meal = analyzer._analyze_meal_times
    original_analyze_activities = analyzer._analyze_activities
    original_analyze_efficiency = analyzer._analyze_efficiency
    original_analyze_timelines = analyzer._analyze_daily_timelines
    original_assess_quality = analyzer._assess_data_quality
    
    # 시간 측정 래퍼
    @time_it("_get_data", results)
    def wrapped_get_data(*args, **kwargs):
        return original_get_data(*args, **kwargs)
    
    @time_it("_apply_tag_based_analysis", results)
    def wrapped_apply_tag_based(*args, **kwargs):
        return original_apply_tag_based(*args, **kwargs)
    
    @time_it("_analyze_work_time", results)
    def wrapped_analyze_work_time(*args, **kwargs):
        return original_analyze_work_time(*args, **kwargs)
    
    @time_it("_analyze_shift_patterns", results)
    def wrapped_analyze_shift(*args, **kwargs):
        return original_analyze_shift(*args, **kwargs)
    
    @time_it("_analyze_meal_times", results)
    def wrapped_analyze_meal(*args, **kwargs):
        return original_analyze_meal(*args, **kwargs)
    
    @time_it("_analyze_activities", results)
    def wrapped_analyze_activities(*args, **kwargs):
        return original_analyze_activities(*args, **kwargs)
    
    @time_it("_analyze_efficiency", results)
    def wrapped_analyze_efficiency(*args, **kwargs):
        return original_analyze_efficiency(*args, **kwargs)
    
    @time_it("_analyze_daily_timelines", results)
    def wrapped_analyze_timelines(*args, **kwargs):
        return original_analyze_timelines(*args, **kwargs)
    
    @time_it("_assess_data_quality", results)
    def wrapped_assess_quality(*args, **kwargs):
        return original_assess_quality(*args, **kwargs)
    
    # 메서드 교체
    analyzer._get_data = wrapped_get_data
    analyzer._apply_tag_based_analysis = wrapped_apply_tag_based
    analyzer._analyze_work_time = wrapped_analyze_work_time
    analyzer._analyze_shift_patterns = wrapped_analyze_shift
    analyzer._analyze_meal_times = wrapped_analyze_meal
    analyzer._analyze_activities = wrapped_analyze_activities
    analyzer._analyze_efficiency = wrapped_analyze_efficiency
    analyzer._analyze_daily_timelines = wrapped_analyze_timelines
    analyzer._assess_data_quality = wrapped_assess_quality

def run_performance_test():
    """성능 테스트 실행"""
    
    print("=" * 60)
    print("성능 측정 테스트 시작")
    print("=" * 60)
    
    # Pickle 파일에서 직원 정보 로드
    from src.data_processing import PickleManager
    pickle_manager = PickleManager()
    
    # 데이터베이스 연결
    db_manager = DatabaseManager()
    
    # 실제 데이터가 있는 직원 ID 사용
    # 2025년 6월에 활발한 사용자 5명
    employee_ids = ['20210869', '20210349', '20211309', '20220763', '20160642']
    
    print(f"테스트 대상 직원: {employee_ids}")
    
    # 측정 결과 저장
    results = {}
    
    # 분석기 초기화
    individual_analyzer = IndividualAnalyzer(db_manager)
    monkey_patch_analyzer(individual_analyzer, results)
    
    organization_analyzer = OrganizationAnalyzer(db_manager, individual_analyzer)
    
    # 2025년 6월 15일로 테스트 (실제 데이터가 있는 날짜)
    test_date = date(2025, 6, 15)
    start_date = datetime.combine(test_date, datetime.min.time())
    end_date = datetime.combine(test_date, datetime.max.time())
    
    print(f"테스트 날짜: {test_date}")
    print("\n개인별 분석 시작...")
    print("-" * 40)
    
    # 각 직원별로 분석 실행
    analysis_results = []
    for idx, employee_id in enumerate(employee_ids, 1):
        print(f"\n[{idx}/5] 직원 {employee_id} 분석 중...")
        
        start_time = time.time()
        
        with measure_section(f"전체_분석_{employee_id}", results):
            try:
                result = individual_analyzer.analyze_individual(
                    employee_id, start_date, end_date
                )
                elapsed = time.time() - start_time
                print(f"  - 완료: {elapsed:.2f}초")
                
                # 분석 결과 저장
                analysis_results.append({
                    'employee_id': employee_id,
                    'elapsed_time': elapsed,
                    'result': result
                })
                
                # 주요 결과 출력
                print(f"  - 근무시간: {result.get('work_time_analysis', {}).get('actual_work_hours', 0)}시간")
                print(f"  - 식사횟수: 아침 {result.get('meal_time_analysis', {}).get('breakfast_count', 0)}회, "
                      f"점심 {result.get('meal_time_analysis', {}).get('lunch_count', 0)}회, "
                      f"저녁 {result.get('meal_time_analysis', {}).get('dinner_count', 0)}회")
                print(f"  - 활동 요약: {result.get('activity_analysis', {}).get('state_distribution', {})}")
                
            except Exception as e:
                print(f"  - 실패: {e}")
                analysis_results.append({
                    'employee_id': employee_id,
                    'elapsed_time': time.time() - start_time,
                    'error': str(e)
                })
    
    # 결과 출력
    print("\n" + "=" * 60)
    print("성능 측정 결과")
    print("=" * 60)
    
    # 메서드별 평균 시간 계산
    method_stats = {}
    for method_name, times in results.items():
        if times:
            method_stats[method_name] = {
                'count': len(times),
                'total': sum(times),
                'avg': sum(times) / len(times),
                'min': min(times),
                'max': max(times)
            }
    
    # 시간 순으로 정렬
    sorted_stats = sorted(method_stats.items(), key=lambda x: x[1]['total'], reverse=True)
    
    print("\n총 실행 시간 기준 TOP 10 병목 구간:")
    print("-" * 60)
    print(f"{'메서드':<35} {'횟수':>6} {'총시간':>8} {'평균':>8} {'최대':>8}")
    print("-" * 60)
    
    for method_name, stats in sorted_stats[:10]:
        print(f"{method_name:<35} {stats['count']:>6} "
              f"{stats['total']:>8.3f} {stats['avg']:>8.3f} {stats['max']:>8.3f}")
    
    # 데이터 로딩 관련 통계
    print("\n데이터 로딩 패턴 분석:")
    print("-" * 60)
    
    data_loading_methods = ['_get_data', 'tag_logs', 'claim_data', 'abc_activity_data']
    for method in data_loading_methods:
        if method in method_stats:
            stats = method_stats[method]
            print(f"{method}: {stats['count']}회 호출, "
                  f"총 {stats['total']:.3f}초, 평균 {stats['avg']:.3f}초")
    
    # 분석 단계별 시간
    print("\n분석 단계별 시간 분포:")
    print("-" * 60)
    
    analysis_phases = [
        ('데이터 로딩', ['_get_data']),
        ('태그 기반 분석', ['_apply_tag_based_analysis']),
        ('근무시간 분석', ['_analyze_work_time']),
        ('교대패턴 분석', ['_analyze_shift_patterns']),
        ('식사시간 분석', ['_analyze_meal_times']),
        ('활동 분석', ['_analyze_activities']),
        ('효율성 분석', ['_analyze_efficiency']),
        ('타임라인 분석', ['_analyze_daily_timelines']),
        ('데이터 품질 평가', ['_assess_data_quality'])
    ]
    
    for phase_name, methods in analysis_phases:
        phase_time = sum(method_stats.get(m, {}).get('total', 0) for m in methods)
        if phase_time > 0:
            print(f"{phase_name:<20}: {phase_time:>8.3f}초")
    
    # 전체 분석 시간
    print("\n전체 분석 시간:")
    print("-" * 60)
    
    total_analysis_times = [v for k, v in results.items() if k.startswith("전체_분석_")]
    if total_analysis_times:
        for times in total_analysis_times:
            if times:
                print(f"개별 직원 분석 시간: {times[0]:.3f}초")
        
        all_times = [t for times_list in total_analysis_times for t in times_list]
        print(f"\n평균: {sum(all_times)/len(all_times):.3f}초")
        print(f"최소: {min(all_times):.3f}초")
        print(f"최대: {max(all_times):.3f}초")
    
    # 상세 분석 결과 요약
    print("\n" + "=" * 60)
    print("상세 분석 결과 요약")
    print("=" * 60)
    
    for result_data in analysis_results:
        print(f"\n직원 ID: {result_data['employee_id']}")
        print(f"처리 시간: {result_data['elapsed_time']:.3f}초")
        
        if 'error' in result_data:
            print(f"  오류: {result_data['error']}")
        else:
            result = result_data['result']
            
            # 근무 시간 분석
            work_analysis = result.get('work_time_analysis', {})
            print(f"\n  근무시간 분석:")
            print(f"    - 실제 근무시간: {work_analysis.get('actual_work_hours', 0)}시간")
            print(f"    - 신청 근무시간: {work_analysis.get('claimed_work_hours', 0)}시간")
            print(f"    - 차이: {work_analysis.get('difference_hours', 0)}시간")
            print(f"    - 정확도: {work_analysis.get('accuracy_ratio', 0)}%")
            
            # 식사 시간 분석
            meal_analysis = result.get('meal_time_analysis', {})
            print(f"\n  식사시간 분석:")
            print(f"    - 아침: {meal_analysis.get('breakfast_count', 0)}회")
            print(f"    - 점심: {meal_analysis.get('lunch_count', 0)}회")
            print(f"    - 저녁: {meal_analysis.get('dinner_count', 0)}회")
            print(f"    - 야식: {meal_analysis.get('midnight_meal_count', 0)}회")
            print(f"    - 평균 식사시간: {meal_analysis.get('avg_meal_duration', 0)}분")
            
            # 활동 분석
            activity_analysis = result.get('activity_analysis', {})
            print(f"\n  활동 분석:")
            state_dist = activity_analysis.get('state_distribution', {})
            if state_dist:
                for state, minutes in sorted(state_dist.items(), key=lambda x: x[1], reverse=True)[:5]:
                    hours = minutes / 60
                    print(f"    - {state}: {hours:.1f}시간 ({minutes:.0f}분)")
            
            # 타임라인 분석
            timeline_analysis = result.get('timeline_analysis', {})
            daily_timelines = timeline_analysis.get('daily_timelines', {})
            if daily_timelines:
                for date_str, timeline_data in list(daily_timelines.items())[:1]:  # 첫 날짜만
                    timeline = timeline_data.get('timeline', [])
                    print(f"\n  타임라인 (이벤트 수): {len(timeline)}개")
                    if timeline:
                        print(f"    - 첫 이벤트: {timeline[0].get('timestamp', 'N/A')}")
                        print(f"    - 마지막 이벤트: {timeline[-1].get('timestamp', 'N/A')}")
        
        print("-" * 40)

if __name__ == "__main__":
    run_performance_test()