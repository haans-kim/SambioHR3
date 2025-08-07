#!/usr/bin/env python3
"""
classify_activities 함수 상세 프로파일링
각 주요 단계별 시간 측정으로 정확한 병목 파악
"""

import time
import logging
from datetime import date
from pathlib import Path
import sys

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.database import get_database_manager
from src.data_processing import PickleManager
from src.ui.components.individual_dashboard import IndividualDashboard
from src.analysis.individual_analyzer import IndividualAnalyzer

class ClassifyActivitiesProfiler:
    """classify_activities 함수 상세 프로파일러"""
    
    def __init__(self):
        self.db_manager = get_database_manager()
        self.pickle_manager = PickleManager()
        
        # 로깅 레벨 임시 변경으로 로깅 오버헤드 측정
        self.original_log_level = logging.root.level
        
    def profile_classify_activities(self, employee_id="20170124", test_date=None):
        """classify_activities 함수 상세 프로파일링"""
        print("🔬 classify_activities 상세 프로파일링")
        print("="*60)
        
        if not test_date:
            test_date = date(2025, 6, 4)
            
        # IndividualAnalyzer와 IndividualDashboard 생성
        individual_analyzer = IndividualAnalyzer(self.db_manager, None)
        individual_analyzer.pickle_manager = self.pickle_manager
        individual_dashboard = IndividualDashboard(individual_analyzer)
        
        # 태그 데이터 준비
        daily_data = individual_dashboard.get_daily_tag_data(employee_id, test_date)
        if daily_data is None or daily_data.empty:
            print("❌ 태그 데이터 없음")
            return {}
            
        print(f"📊 입력 데이터: {len(daily_data)}건")
        
        # 1. 로깅 레벨별 성능 비교
        logging_performance = self.compare_logging_levels(individual_dashboard, daily_data, employee_id, test_date)
        
        # 2. 주요 함수 호출별 시간 측정
        function_performance = self.profile_internal_functions(individual_dashboard, daily_data, employee_id, test_date)
        
        return {
            'logging_performance': logging_performance,
            'function_performance': function_performance
        }
    
    def compare_logging_levels(self, dashboard, daily_data, employee_id, test_date):
        """로깅 레벨별 성능 비교"""
        print("\n🔍 로깅 레벨별 성능 비교")
        print("-" * 40)
        
        results = {}
        
        # 로깅 레벨별 테스트
        levels = [
            (logging.CRITICAL, "CRITICAL (로깅 거의 없음)"),
            (logging.ERROR, "ERROR"),
            (logging.WARNING, "WARNING"),  
            (logging.INFO, "INFO (기본값)"),
            (logging.DEBUG, "DEBUG (최대 로깅)")
        ]
        
        for level, name in levels:
            # 로깅 레벨 변경
            logging.root.setLevel(level)
            dashboard.logger.setLevel(level)
            
            # 5회 측정 후 평균
            times = []
            for i in range(3):
                data_copy = daily_data.copy()
                
                start_time = time.time()
                dashboard.classify_activities(data_copy, employee_id, test_date)
                elapsed = time.time() - start_time
                times.append(elapsed)
            
            avg_time = sum(times) / len(times)
            results[level] = {
                'name': name,
                'avg_time': avg_time,
                'times': times
            }
            
            print(f"  {name}: {avg_time:.3f}초 (평균)")
        
        # 원래 로깅 레벨 복원
        logging.root.setLevel(self.original_log_level)
        dashboard.logger.setLevel(self.original_log_level)
        
        return results
    
    def profile_internal_functions(self, dashboard, daily_data, employee_id, test_date):
        """내부 함수 호출별 시간 측정"""
        print("\n🎯 내부 함수별 성능 프로파일링")
        print("-" * 40)
        
        times = {}
        
        # 1. get_tag_location_master 시간 측정
        start_time = time.time()
        tag_location_master = dashboard.get_tag_location_master()
        times['get_tag_location_master'] = time.time() - start_time
        print(f"  get_tag_location_master: {times['get_tag_location_master']:.3f}초")
        
        # 2. get_employee_work_type 시간 측정
        start_time = time.time()
        work_type = dashboard.get_employee_work_type(employee_id, test_date)
        times['get_employee_work_type'] = time.time() - start_time
        print(f"  get_employee_work_type: {times['get_employee_work_type']:.3f}초")
        
        # 3. 주요 DataFrame 연산들 추정
        data_copy = daily_data.copy()
        
        # 기본 컬럼 설정 시간
        start_time = time.time()
        if 'activity_code' not in data_copy.columns:
            data_copy['activity_code'] = 'WORK'
        if 'confidence' not in data_copy.columns:
            data_copy['confidence'] = 80
        times['basic_column_setup'] = time.time() - start_time
        print(f"  기본 컬럼 설정: {times['basic_column_setup']:.3f}초")
        
        # merge 연산 시간 (가장 비용이 클 것으로 예상)
        if tag_location_master is not None and not tag_location_master.empty:
            start_time = time.time()
            # DR_NO 문자열 변환 
            data_copy['DR_NO_str'] = data_copy['DR_NO'].astype(str).str.strip()
            tag_location_master['DR_NO_str'] = tag_location_master['DR_NO'].astype(str).str.strip()
            
            # 실제 merge 연산
            merged = data_copy.merge(
                tag_location_master[['DR_NO_str', 'Tag_Code']],
                on='DR_NO_str',
                how='left',
                suffixes=('', '_master')
            )
            times['dataframe_merge'] = time.time() - start_time
            print(f"  DataFrame merge: {times['dataframe_merge']:.3f}초")
        
        return times
    
    def analyze_function_complexity(self):
        """함수 복잡도 분석"""
        print("\n📊 classify_activities 함수 복잡도 분석")
        print("-" * 50)
        
        # 파일 읽기
        with open("/Users/hanskim/Projects/SambioHR3/src/ui/components/individual_dashboard.py", 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # classify_activities 함수 범위 찾기
        start_line = None
        end_line = None
        
        for i, line in enumerate(lines):
            if 'def classify_activities(' in line:
                start_line = i
            elif start_line is not None and line.startswith('    def ') and not line.startswith('        def'):
                end_line = i
                break
        
        if start_line is not None:
            if end_line is None:
                end_line = len(lines)
                
            func_lines = lines[start_line:end_line]
            
            # 복잡도 지표들 계산
            total_lines = len(func_lines)
            
            # 로깅 명령어 수
            log_count = sum(1 for line in func_lines 
                           if any(log_type in line for log_type in ['logger.info', 'logger.warning', 'logger.error', 'logger.debug']))
            
            # 조건문 수
            condition_count = sum(1 for line in func_lines 
                                 if any(keyword in line.strip() for keyword in ['if ', 'elif ', 'for ', 'while ']))
            
            # merge/join 연산 수  
            merge_count = sum(1 for line in func_lines if 'merge(' in line or 'join(' in line)
            
            # 반복문 내 DataFrame 연산 (성능 위험)
            loop_df_ops = sum(1 for line in func_lines 
                             if any(op in line for op in ['.loc[', '.iloc[', '.at[', '.iat[']) and 
                                any(indent in line[:20] for indent in ['        ', '            ']))
            
            print(f"  📝 총 라인 수: {total_lines:,}줄")
            print(f"  🔍 로깅 명령어: {log_count}개")
            print(f"  ⚡ 조건문/반복문: {condition_count}개")
            print(f"  🔗 DataFrame merge: {merge_count}개")
            print(f"  🚨 반복문 내 DataFrame 연산: {loop_df_ops}개")
            print()
            print(f"  💡 복잡도 점수: {(log_count * 0.1 + condition_count * 0.2 + merge_count * 2 + loop_df_ops * 5):.1f}")
            print(f"     (로깅×0.1 + 조건문×0.2 + merge×2 + 반복문DF연산×5)")
    
    def generate_optimization_report(self, results):
        """최적화 권장사항 보고서"""
        print("\n" + "="*80)
        print("📈 classify_activities 최적화 분석 보고서")
        print("="*80)
        
        logging_results = results.get('logging_performance', {})
        function_results = results.get('function_performance', {})
        
        # 로깅 오버헤드 분석
        if logging_results:
            critical_time = logging_results.get(logging.CRITICAL, {}).get('avg_time', 0)
            info_time = logging_results.get(logging.INFO, {}).get('avg_time', 0)
            
            if critical_time > 0:
                logging_overhead = ((info_time - critical_time) / info_time) * 100
                print(f"🔍 로깅 오버헤드 분석:")
                print(f"  • 로깅 없음: {critical_time:.3f}초")
                print(f"  • 기본 로깅: {info_time:.3f}초")
                print(f"  • 로깅 오버헤드: {logging_overhead:.1f}%")
                print()
        
        # 함수별 성능 분석
        if function_results:
            print("🎯 병목 함수 분석:")
            sorted_functions = sorted(function_results.items(), key=lambda x: x[1], reverse=True)
            for func_name, time_taken in sorted_functions:
                print(f"  • {func_name}: {time_taken:.3f}초")
            print()
        
        # 최적화 권장사항
        print("💡 최적화 권장사항:")
        print("  1. 🚨 로깅 레벨 최적화")
        print("     - 운영 환경에서는 WARNING 이상으로 설정")
        print("     - 디버그 로깅 373개 중 핵심만 유지")
        print()
        print("  2. 🔄 데이터 로드 캐싱")
        print("     - get_employee_work_type의 claim_data 캐싱")
        print("     - PerformanceCache에 추가")
        print()
        print("  3. 🏗️ 함수 분할")
        print("     - 1,558줄 거대 함수를 작은 함수들로 분할")
        print("     - 단일 책임 원칙 적용")
        print()
        print("  4. ⚡ DataFrame 연산 최적화")
        print("     - 반복적인 merge 연산을 한 번으로 통합")
        print("     - 벡터화 연산 활용")
        print()
        print("  5. 🎯 조건부 실행")
        print("     - 불필요한 연산들을 조건부로 실행")
        print("     - Early return 패턴 활용")

def main():
    """메인 실행 함수"""
    print("🚀 classify_activities 상세 프로파일링 시작")
    print("="*60)
    
    profiler = ClassifyActivitiesProfiler()
    
    # 1. 함수 복잡도 분석
    profiler.analyze_function_complexity()
    
    # 2. 성능 프로파일링
    results = profiler.profile_classify_activities()
    
    # 3. 최적화 권장사항 보고서
    profiler.generate_optimization_report(results)

if __name__ == "__main__":
    main()