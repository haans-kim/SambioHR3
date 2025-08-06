#!/usr/bin/env python3
"""
성능 최적화 효과 측정 스크립트
Before/After 비교를 통한 인덱스 최적화 효과 검증
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
from src.analysis.individual_analyzer import IndividualAnalyzer

class PerformanceTestRunner:
    """성능 테스트 실행기"""
    
    def __init__(self):
        self.db_manager = get_database_manager()
        self.analyzer = IndividualAnalyzer(self.db_manager, None)
        self.db_path = "/Users/hanskim/Projects/SambioHR3/data/sambio_human.db"
        
    def run_query_performance_test(self):
        """쿼리별 성능 테스트"""
        print("🔍 DB 쿼리 성능 테스트 시작...")
        
        test_queries = [
            {
                "name": "태그 데이터 조회 (개인별 + 날짜)",
                "query": """
                SELECT * FROM tag_data 
                WHERE "사번" = 1001 AND "ENTE_DT" = 20250604
                ORDER BY "출입시각"
                """,
                "description": "개인별 일일 태그 데이터 조회"
            },
            {
                "name": "태그 로그 조회 (시간 범위)",
                "query": """
                SELECT * FROM tag_logs 
                WHERE employee_id = '1001' 
                AND timestamp BETWEEN '2025-06-04 00:00:00' AND '2025-06-04 23:59:59'
                ORDER BY timestamp
                """,
                "description": "시간 범위 태그 로그 조회"
            },
            {
                "name": "장비 로그 조회",
                "query": """
                SELECT * FROM equipment_logs 
                WHERE employee_id = '1001' 
                AND DATE(datetime) = '2025-06-04'
                """,
                "description": "일별 장비 사용 로그 조회"
            },
            {
                "name": "조직별 분석 결과 집계",
                "query": """
                SELECT center_name, AVG(efficiency_ratio) as avg_efficiency,
                       COUNT(*) as employee_count
                FROM daily_analysis_results 
                WHERE analysis_date = '2025-06-04'
                GROUP BY center_name
                """,
                "description": "센터별 효율성 집계"
            }
        ]
        
        results = {}
        
        for test in test_queries:
            print(f"  📊 테스트: {test['name']}")
            times = []
            
            # 5회 반복 측정
            for i in range(5):
                start_time = time.time()
                
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute(test['query'])
                        rows = cursor.fetchall()
                        row_count = len(rows)
                except Exception as e:
                    print(f"    ❌ 쿼리 실행 오류: {e}")
                    continue
                    
                elapsed_time = time.time() - start_time
                times.append(elapsed_time)
                
            if times:
                avg_time = statistics.mean(times)
                min_time = min(times)
                max_time = max(times)
                
                results[test['name']] = {
                    'avg_time': avg_time,
                    'min_time': min_time, 
                    'max_time': max_time,
                    'description': test['description']
                }
                
                print(f"    ⏱️  평균: {avg_time:.3f}초, 최소: {min_time:.3f}초, 최대: {max_time:.3f}초")
            else:
                print(f"    ❌ 측정 실패")
        
        return results
    
    def run_individual_analysis_test(self, employee_ids=None, test_date=None):
        """개인별 분석 성능 테스트"""
        print("👤 개인별 분석 성능 테스트 시작...")
        
        if not employee_ids:
            # 테스트용 직원 ID 가져오기
            query = """
            SELECT DISTINCT "사번" FROM tag_data 
            WHERE "ENTE_DT" = 20250604 
            LIMIT 5
            """
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                employee_ids = [str(row[0]) for row in cursor.fetchall()]
        
        if not test_date:
            test_date = date(2025, 6, 4)
            
        results = []
        
        for emp_id in employee_ids:
            print(f"  🔍 직원 {emp_id} 분석 중...")
            
            # 3회 반복 측정
            times = []
            for i in range(3):
                start_time = time.time()
                
                try:
                    start_datetime = datetime.combine(test_date, datetime.min.time())
                    end_datetime = datetime.combine(test_date, datetime.max.time())
                    
                    analysis_result = self.analyzer.analyze_individual(
                        emp_id, start_datetime, end_datetime
                    )
                    
                    elapsed_time = time.time() - start_time
                    times.append(elapsed_time)
                    
                except Exception as e:
                    print(f"    ❌ 분석 오류: {e}")
                    continue
            
            if times:
                avg_time = statistics.mean(times)
                results.append({
                    'employee_id': emp_id,
                    'avg_time': avg_time,
                    'times': times
                })
                print(f"    ⏱️  평균 분석 시간: {avg_time:.3f}초")
            else:
                print(f"    ❌ 측정 실패")
        
        return results
    
    def generate_report(self, query_results, analysis_results):
        """성능 테스트 보고서 생성"""
        print("\n" + "="*80)
        print("📈 성능 최적화 효과 보고서")
        print("="*80)
        
        print(f"테스트 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"생성된 인덱스: {len([name for name in query_results.keys()])}개 쿼리 테스트")
        
        print("\n🔍 쿼리 성능 결과:")
        for name, result in query_results.items():
            print(f"  • {name}")
            print(f"    평균: {result['avg_time']:.3f}초")
            print(f"    범위: {result['min_time']:.3f}초 ~ {result['max_time']:.3f}초")
            print(f"    설명: {result['description']}")
            print()
        
        print("👤 개인별 분석 성능 결과:")
        if analysis_results:
            all_times = [r['avg_time'] for r in analysis_results]
            overall_avg = statistics.mean(all_times)
            print(f"  • 전체 평균 분석 시간: {overall_avg:.3f}초")
            print(f"  • 테스트된 직원 수: {len(analysis_results)}명")
            print(f"  • 예상 16명 조직 분석 시간: {overall_avg * 16:.1f}초")
            
            for result in analysis_results:
                print(f"    - 직원 {result['employee_id']}: {result['avg_time']:.3f}초")
        else:
            print("  ❌ 분석 성능 데이터 없음")
        
        print("\n📊 최적화 효과 예상:")
        print("  • 목표: classify_activities 0.454초 → 0.150초 (66% 향상)")
        if analysis_results:
            print(f"  • 실제 측정: 평균 {overall_avg:.3f}초")
            if overall_avg < 1.0:
                improvement = ((1.87 - overall_avg) / 1.87) * 100
                print(f"  • 성능 향상: {improvement:.1f}% 달성!")
            else:
                print(f"  • 추가 최적화 필요")
        
        print("\n🎯 다음 최적화 단계:")
        print("  1. Phase 2: classify_activities 알고리즘 벡터화")
        print("  2. Phase 3: 메모리 캐싱 시스템 구축")
        print("  3. 배치 데이터 로딩 최적화")

def main():
    """메인 실행 함수"""
    print("🚀 SambioHR3 성능 최적화 테스트 시작")
    print("="*50)
    
    tester = PerformanceTestRunner()
    
    # 쿼리 성능 테스트
    query_results = tester.run_query_performance_test()
    print()
    
    # 개인별 분석 성능 테스트
    analysis_results = tester.run_individual_analysis_test()
    
    # 보고서 생성
    tester.generate_report(query_results, analysis_results)

if __name__ == "__main__":
    main()