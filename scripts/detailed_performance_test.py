#!/usr/bin/env python3
"""
execute_analysis 세부 단계별 성능 분석
각 함수별 시간 측정으로 정확한 병목 파악
"""

import time
import sqlite3
import statistics
from datetime import datetime, date, timedelta
from pathlib import Path
import sys

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.database import get_database_manager
from src.data_processing import PickleManager
from src.ui.components.individual_dashboard import IndividualDashboard
from src.analysis.individual_analyzer import IndividualAnalyzer

class DetailedPerformanceAnalyzer:
    """세부 성능 분석기"""
    
    def __init__(self):
        self.db_manager = get_database_manager()
        self.pickle_manager = PickleManager()
        
    def analyze_execute_analysis_steps(self, employee_id="20170124", test_date=None):
        """execute_analysis의 각 단계별 성능 분석"""
        print("🔍 execute_analysis 세부 단계별 성능 분석")
        print("="*60)
        
        if not test_date:
            test_date = date(2025, 6, 4)
            
        # IndividualAnalyzer와 IndividualDashboard 생성
        individual_analyzer = IndividualAnalyzer(self.db_manager, None)
        individual_analyzer.pickle_manager = self.pickle_manager
        individual_dashboard = IndividualDashboard(individual_analyzer)
        
        step_times = {}
        
        print(f"👤 직원 {employee_id} 세부 분석 시작...")
        print(f"📅 분석 날짜: {test_date}")
        print()
        
        try:
            # 1. get_daily_tag_data
            print("1️⃣ get_daily_tag_data 실행...")
            step_start = time.time()
            daily_data = individual_dashboard.get_daily_tag_data(employee_id, test_date)
            step_times['get_daily_tag_data'] = time.time() - step_start
            print(f"   ⏱️ 시간: {step_times['get_daily_tag_data']:.3f}초")
            print(f"   📊 데이터: {len(daily_data) if daily_data is not None else 0}건")
            
            if daily_data is None or daily_data.empty:
                print("❌ 태그 데이터 없음, 분석 중단")
                return step_times
                
            # 2. get_employee_equipment_data
            print("\n2️⃣ get_employee_equipment_data 실행...")
            step_start = time.time()
            equipment_data = individual_dashboard.get_employee_equipment_data(employee_id, test_date)
            step_times['get_employee_equipment_data'] = time.time() - step_start
            print(f"   ⏱️ 시간: {step_times['get_employee_equipment_data']:.3f}초")
            print(f"   📊 데이터: {len(equipment_data) if equipment_data is not None else 0}건")
            
            # 3. get_employee_attendance_data
            print("\n3️⃣ get_employee_attendance_data 실행...")
            step_start = time.time()
            attendance_data = individual_dashboard.get_employee_attendance_data(employee_id, test_date)
            step_times['get_employee_attendance_data'] = time.time() - step_start
            print(f"   ⏱️ 시간: {step_times['get_employee_attendance_data']:.3f}초")
            print(f"   📊 데이터: {len(attendance_data) if attendance_data is not None else 0}건")
            
            # 4. classify_activities (가장 큰 병목 예상)
            print("\n4️⃣ classify_activities 실행...")
            step_start = time.time()
            classified_data = individual_dashboard.classify_activities(daily_data, employee_id, test_date)
            step_times['classify_activities'] = time.time() - step_start
            print(f"   ⏱️ 시간: {step_times['classify_activities']:.3f}초")
            print(f"   📊 입력: {len(daily_data)}건 → 출력: {len(classified_data) if classified_data is not None else 0}건")
            
            # 5. analyze_daily_data
            print("\n5️⃣ analyze_daily_data 실행...")
            step_start = time.time()
            analysis_result = individual_dashboard.analyze_daily_data(employee_id, test_date, classified_data)
            step_times['analyze_daily_data'] = time.time() - step_start
            print(f"   ⏱️ 시간: {step_times['analyze_daily_data']:.3f}초")
            print(f"   📊 결과: {'성공' if analysis_result else '실패'}")
            
            # 전체 시간 계산
            total_time = sum(step_times.values())
            step_times['total_time'] = total_time
            
            print(f"\n📈 전체 분석 완료: {total_time:.3f}초")
            
        except Exception as e:
            print(f"❌ 분석 실패: {str(e)}")
            import traceback
            print(f"상세 오류: {traceback.format_exc()}")
            
        return step_times
    
    def analyze_classify_activities_detail(self, employee_id="20170124", test_date=None):
        """classify_activities 함수의 내부 성능 분석"""
        print("\n🔬 classify_activities 내부 성능 분석")
        print("="*50)
        
        if not test_date:
            test_date = date(2025, 6, 4)
            
        individual_analyzer = IndividualAnalyzer(self.db_manager, None)
        individual_analyzer.pickle_manager = self.pickle_manager
        individual_dashboard = IndividualDashboard(individual_analyzer)
        
        # 태그 데이터 가져오기
        daily_data = individual_dashboard.get_daily_tag_data(employee_id, test_date)
        if daily_data is None or daily_data.empty:
            print("❌ 태그 데이터 없음")
            return {}
            
        print(f"📊 입력 데이터: {len(daily_data)}건")
        
        # classify_activities 실행하면서 내부 단계별 측정 
        # (함수 내부에 시간 측정 코드를 임시로 추가해야 함)
        print("⚠️ classify_activities 내부 분석을 위해서는 함수 수정이 필요합니다.")
        
        # 대신 classify_activities의 주요 작업들을 개별적으로 측정
        sub_step_times = {}
        
        try:
            # 기본 컬럼 생성 시간 측정
            step_start = time.time()
            test_data = daily_data.copy()
            # datetime 컬럼이 있는지 확인
            if 'datetime' not in test_data.columns:
                test_data['datetime'] = individual_dashboard._create_datetime_if_missing(test_data)
            sub_step_times['datetime_creation'] = time.time() - step_start
            
            print(f"   datetime 생성: {sub_step_times['datetime_creation']:.3f}초")
            
            # classify_activities 전체 실행
            step_start = time.time()
            result = individual_dashboard.classify_activities(daily_data, employee_id, test_date)
            sub_step_times['full_classify'] = time.time() - step_start
            
            print(f"   전체 classify_activities: {sub_step_times['full_classify']:.3f}초")
            
        except Exception as e:
            print(f"❌ classify_activities 분석 실패: {e}")
            
        return sub_step_times
        
    def generate_detailed_report(self, step_times, classify_details):
        """상세 성능 분석 보고서"""
        print("\n" + "="*80)
        print("📊 execute_analysis 세부 성능 분석 보고서")
        print("="*80)
        
        print(f"테스트 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        if step_times:
            total_time = step_times.get('total_time', sum(v for k, v in step_times.items() if k != 'total_time'))
            
            print("🎯 단계별 성능 분석:")
            print(f"  • 전체 실행 시간: {total_time:.3f}초")
            print()
            
            # 각 단계별 시간과 비율
            steps = [
                ('get_daily_tag_data', '태그 데이터 로드'),
                ('get_employee_equipment_data', '장비 데이터 로드'),  
                ('get_employee_attendance_data', '근태 데이터 로드'),
                ('classify_activities', '활동 분류'),
                ('analyze_daily_data', '데이터 분석')
            ]
            
            for step_key, step_name in steps:
                if step_key in step_times:
                    step_time = step_times[step_key]
                    percentage = (step_time / total_time) * 100
                    print(f"  • {step_name}: {step_time:.3f}초 ({percentage:.1f}%)")
                    
            print()
            
            # 병목 분석
            max_time_key = max((k for k in step_times.keys() if k != 'total_time'), 
                              key=lambda x: step_times[x])
            max_time = step_times[max_time_key]
            max_percentage = (max_time / total_time) * 100
            
            print("🚨 병목 분석:")
            print(f"  • 가장 오래 걸리는 단계: {max_time_key}")
            print(f"  • 시간: {max_time:.3f}초 ({max_percentage:.1f}%)")
            
            # classify_activities가 병목인 경우 추가 분석
            if max_time_key == 'classify_activities' and max_time > 0.3:
                print(f"  • ⚠️ classify_activities가 {max_time:.3f}초로 병목!")
                print(f"  • 태그 수 대비 매우 비효율적 (일반적으로 0.01~0.05초 예상)")
                print(f"  • 내부 로직 최적화 필요")
            
            print()
        
        if classify_details:
            print("🔬 classify_activities 세부 분석:")
            for key, value in classify_details.items():
                print(f"  • {key}: {value:.3f}초")
            print()
        
        print("💡 최적화 권장사항:")
        if step_times.get('classify_activities', 0) > 0.3:
            print("  1. classify_activities 함수 내부 로직 리팩터링")
            print("  2. 반복문을 벡터화 연산으로 변경")
            print("  3. 불필요한 데이터 복사 제거")
        if step_times.get('get_daily_tag_data', 0) > 0.2:
            print("  4. 캐시 효율성 개선 (이미 일부 적용)")
        print("  5. 전체 파이프라인 병렬 처리 검토")

def main():
    """메인 실행 함수"""
    print("🚀 execute_analysis 세부 성능 분석 시작")
    print("="*50)
    
    analyzer = DetailedPerformanceAnalyzer()
    
    # 1. 전체 단계별 성능 분석
    step_times = analyzer.analyze_execute_analysis_steps()
    
    # 2. classify_activities 세부 분석
    classify_details = analyzer.analyze_classify_activities_detail()
    
    # 3. 상세 보고서 생성
    analyzer.generate_detailed_report(step_times, classify_details)

if __name__ == "__main__":
    main()