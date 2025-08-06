#!/usr/bin/env python3
"""
실제 조직 대시보드 성능 테스트
execute_organization_analysis의 실제 병목 측정
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

class RealPerformanceTest:
    """실제 조직 대시보드 성능 테스트"""
    
    def __init__(self):
        self.db_manager = get_database_manager()
        self.pickle_manager = PickleManager()
        
    def test_individual_dashboard_execute_analysis(self, employee_ids=None, test_date=None):
        """실제 individual_dashboard.execute_analysis 성능 테스트"""
        print("🔍 실제 IndividualDashboard.execute_analysis 성능 테스트")
        print("="*60)
        
        if not test_date:
            test_date = date(2025, 6, 4)
            
        if not employee_ids:
            # pickle 데이터에서 직원 목록 가져오기
            tag_data = self.pickle_manager.load_dataframe('tag_data')
            if tag_data is not None and '사번' in tag_data.columns:
                available_employees = tag_data['사번'].unique()[:5]  # 처음 5명만
                employee_ids = [str(emp) for emp in available_employees]
            else:
                print("❌ 태그 데이터를 찾을 수 없습니다.")
                return []
                
        # IndividualAnalyzer와 IndividualDashboard 생성
        individual_analyzer = IndividualAnalyzer(self.db_manager, None)
        individual_analyzer.pickle_manager = self.pickle_manager
        individual_dashboard = IndividualDashboard(individual_analyzer)
        
        results = []
        
        print(f"📊 테스트 대상: {len(employee_ids)}명")
        print(f"📅 테스트 날짜: {test_date}")
        print()
        
        for emp_id in employee_ids:
            print(f"  👤 직원 {emp_id} 분석 중...")
            
            # 세부 단계별 시간 측정
            step_times = {}
            
            try:
                # 전체 시간 측정 시작
                total_start = time.time()
                
                # 1. 태그 데이터 로드 시간 측정
                step_start = time.time()
                daily_tag_data = individual_dashboard.get_daily_tag_data(emp_id, test_date)
                step_times['tag_data_load'] = time.time() - step_start
                
                if daily_tag_data is None or daily_tag_data.empty:
                    print(f"    ❌ 태그 데이터 없음")
                    continue
                
                print(f"    📋 태그 데이터: {len(daily_tag_data)}건 ({step_times['tag_data_load']:.3f}초)")
                
                # 2. execute_analysis 실행 (핵심 병목)
                step_start = time.time()
                analysis_result = individual_dashboard.execute_analysis(
                    employee_id=emp_id,
                    selected_date=test_date,
                    return_data=True  # UI 렌더링 없이 데이터만 반환
                )
                step_times['execute_analysis'] = time.time() - step_start
                
                total_time = time.time() - total_start
                
                if analysis_result:
                    # 결과 정보 추출
                    work_analysis = analysis_result.get('work_time_analysis', {})
                    activity_summary = analysis_result.get('activity_summary', {})
                    
                    work_hours = work_analysis.get('actual_work_hours', 0)
                    efficiency = work_analysis.get('work_efficiency', 0)
                    
                    results.append({
                        'employee_id': emp_id,
                        'total_time': total_time,
                        'tag_data_load': step_times['tag_data_load'],
                        'execute_analysis': step_times['execute_analysis'],
                        'work_hours': work_hours,
                        'efficiency': efficiency,
                        'status': 'success'
                    })
                    
                    print(f"    ✅ 분석 완료!")
                    print(f"    ⏱️  총 시간: {total_time:.3f}초")
                    print(f"    📊 세부 시간:")
                    print(f"       - 태그 데이터 로드: {step_times['tag_data_load']:.3f}초")
                    print(f"       - execute_analysis: {step_times['execute_analysis']:.3f}초")
                    print(f"    📈 결과: 근무시간 {work_hours:.1f}시간, 효율성 {efficiency:.1f}%")
                
                else:
                    print(f"    ❌ 분석 결과 없음")
                    
            except Exception as e:
                print(f"    ❌ 분석 실패: {str(e)}")
                import traceback
                print(f"    상세 오류: {traceback.format_exc()}")
                continue
                
            print()
        
        return results
    
    def test_classify_activities_directly(self, employee_ids=None, test_date=None):
        """classify_activities 직접 테스트 (IndividualAnalyzer의 classify_activities)"""
        print("🔬 classify_activities 직접 성능 테스트")
        print("="*50)
        
        if not test_date:
            test_date = date(2025, 6, 4)
            
        if not employee_ids:
            # pickle 데이터에서 직원 목록 가져오기
            tag_data = self.pickle_manager.load_dataframe('tag_data')
            if tag_data is not None and '사번' in tag_data.columns:
                available_employees = tag_data['사번'].unique()[:3]  # 처음 3명만
                employee_ids = [str(emp) for emp in available_employees]
            else:
                print("❌ 태그 데이터를 찾을 수 없습니다.")
                return []
        
        # IndividualAnalyzer 생성
        individual_analyzer = IndividualAnalyzer(self.db_manager, None)
        individual_analyzer.pickle_manager = self.pickle_manager
        
        results = []
        
        for emp_id in employee_ids:
            print(f"  🧪 직원 {emp_id} classify_activities 테스트...")
            
            try:
                # 태그 데이터 가져오기
                tag_data = self.pickle_manager.load_dataframe('tag_data')
                if tag_data is None:
                    continue
                    
                # 해당 직원의 해당 날짜 데이터만 필터링
                emp_tag_data = tag_data[
                    (tag_data['사번'] == int(emp_id)) & 
                    (tag_data['ENTE_DT'] == int(test_date.strftime('%Y%m%d')))
                ]
                
                if emp_tag_data.empty:
                    print(f"    ❌ 태그 데이터 없음")
                    continue
                
                print(f"    📋 태그 데이터: {len(emp_tag_data)}건")
                
                # classify_activities 직접 호출
                start_time = time.time()
                
                # datetime 컬럼 생성 (IndividualAnalyzer에서 하는 것처럼)
                emp_tag_data = emp_tag_data.copy()
                emp_tag_data['datetime'] = individual_analyzer._create_datetime_column(emp_tag_data)
                
                # classify_activities 호출
                classified_activities = individual_analyzer.classify_activities(emp_tag_data)
                
                elapsed_time = time.time() - start_time
                
                results.append({
                    'employee_id': emp_id,
                    'tag_count': len(emp_tag_data),
                    'classify_time': elapsed_time,
                    'activity_count': len(classified_activities) if classified_activities else 0,
                    'status': 'success'
                })
                
                print(f"    ⏱️  classify_activities 시간: {elapsed_time:.3f}초")
                print(f"    📊 생성된 활동: {len(classified_activities) if classified_activities else 0}개")
                
            except Exception as e:
                print(f"    ❌ 테스트 실패: {str(e)}")
                continue
        
        return results
    
    def generate_detailed_report(self, dashboard_results, classify_results):
        """상세 성능 분석 보고서"""
        print("\n" + "="*80)
        print("📈 실제 성능 분석 보고서 - 인덱스 최적화 후")
        print("="*80)
        
        print(f"테스트 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        if dashboard_results:
            print("🎯 IndividualDashboard.execute_analysis 결과:")
            total_times = [r['total_time'] for r in dashboard_results]
            execute_times = [r['execute_analysis'] for r in dashboard_results]
            tag_load_times = [r['tag_data_load'] for r in dashboard_results]
            
            print(f"  • 테스트된 직원 수: {len(dashboard_results)}명")
            print(f"  • 평균 전체 분석 시간: {statistics.mean(total_times):.3f}초")
            print(f"  • 평균 execute_analysis 시간: {statistics.mean(execute_times):.3f}초")
            print(f"  • 평균 태그 데이터 로드 시간: {statistics.mean(tag_load_times):.3f}초")
            print()
            
            print("  세부 결과:")
            for result in dashboard_results:
                print(f"    - 직원 {result['employee_id']}:")
                print(f"      총 시간: {result['total_time']:.3f}초")
                print(f"      execute_analysis: {result['execute_analysis']:.3f}초 ({result['execute_analysis']/result['total_time']*100:.1f}%)")
                print(f"      태그 로드: {result['tag_data_load']:.3f}초 ({result['tag_data_load']/result['total_time']*100:.1f}%)")
            print()
        
        if classify_results:
            print("🔬 classify_activities 직접 테스트 결과:")
            classify_times = [r['classify_time'] for r in classify_results]
            print(f"  • 평균 classify_activities 시간: {statistics.mean(classify_times):.3f}초")
            
            for result in classify_results:
                print(f"    - 직원 {result['employee_id']}: {result['classify_time']:.3f}초 (태그 {result['tag_count']}건)")
            print()
        
        # 최적화 효과 비교
        print("📊 최적화 효과 비교:")
        print(f"  • 이전 성능 (스크린샷 기준):")
        print(f"    - classify_activities: 0.454초")
        print(f"    - tag_data 로드: 0.200초") 
        print(f"    - 전체 분석: 1.87초")
        print()
        
        if dashboard_results:
            avg_total = statistics.mean(total_times)
            avg_execute = statistics.mean(execute_times)
            avg_tag_load = statistics.mean(tag_load_times)
            
            print(f"  • 현재 성능 (인덱스 최적화 후):")
            print(f"    - 전체 분석: {avg_total:.3f}초")
            print(f"    - execute_analysis: {avg_execute:.3f}초")
            print(f"    - 태그 데이터 로드: {avg_tag_load:.3f}초")
            print()
            
            if classify_results:
                avg_classify = statistics.mean(classify_times)
                print(f"    - classify_activities: {avg_classify:.3f}초")
                
                # 성능 향상 계산
                classify_improvement = ((0.454 - avg_classify) / 0.454) * 100
                tag_improvement = ((0.200 - avg_tag_load) / 0.200) * 100 
                total_improvement = ((1.87 - avg_total) / 1.87) * 100
                
                print()
                print(f"  📈 성능 향상:")
                print(f"    - classify_activities: {classify_improvement:.1f}% 향상")
                print(f"    - 태그 데이터 로드: {tag_improvement:.1f}% 향상")
                print(f"    - 전체 분석: {total_improvement:.1f}% 향상")
                
                # 16명 조직 분석 시간 예상
                estimated_16_people = avg_total * 16
                print(f"    - 16명 조직 분석 예상 시간: {estimated_16_people:.1f}초")
                
                if estimated_16_people < 30:
                    print(f"    🎉 목표 달성! (이전 30초 → 현재 {estimated_16_people:.1f}초)")
                else:
                    print(f"    📈 추가 최적화 필요 (목표: 30초 이하)")

def main():
    """메인 실행 함수"""
    print("🚀 SambioHR3 실제 성능 테스트 (인덱스 최적화 후)")
    print("="*60)
    
    tester = RealPerformanceTest()
    
    # 1. 실제 IndividualDashboard.execute_analysis 테스트
    dashboard_results = tester.test_individual_dashboard_execute_analysis()
    print()
    
    # 2. classify_activities 직접 테스트  
    classify_results = tester.test_classify_activities_directly()
    
    # 3. 상세 보고서 생성
    tester.generate_detailed_report(dashboard_results, classify_results)

if __name__ == "__main__":
    main()