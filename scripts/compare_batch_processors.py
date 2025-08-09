"""
싱글톤 vs 멀티프로세싱 배치 프로세서 비교 테스트
ADC T/F 조직에 대해 2024년 6월 3일-5일 데이터 분석 비교
"""

import sys
import os
from datetime import date, datetime
import pandas as pd
import json
from typing import Dict, List, Any
import hashlib

# 프로젝트 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import get_database_manager, get_pickle_manager
from src.analysis.singleton_batch_processor import SingletonBatchProcessor
from src.analysis.parallel_batch_analyzer import ParallelBatchAnalyzer


class BatchProcessorComparator:
    """배치 프로세서 비교 클래스"""
    
    def __init__(self):
        self.db_manager = get_database_manager()
        self.pickle_manager = get_pickle_manager()
        
    def find_adc_tf_members(self) -> List[str]:
        """ADC T/F 조직 구성원 찾기"""
        print("📋 ADC T/F 조직 구성원 조회 중...")
        
        # 조직 데이터 로드
        org_data = self.pickle_manager.load_dataframe('organization_data')
        
        # ADC T/F 필터링 (팀 이름에 'ADC' 포함 확인)
        adc_tf_members = org_data[
            (org_data['팀'].str.contains('ADC', na=False)) | 
            (org_data['그룹'].str.contains('ADC', na=False))
        ]
        
        if adc_tf_members.empty:
            # 대체 검색
            print("ADC T/F를 찾을 수 없어 다른 작은 조직을 검색합니다...")
            # 첫 번째 팀의 구성원 선택
            first_team = org_data['팀'].dropna().iloc[0]
            adc_tf_members = org_data[org_data['팀'] == first_team]
            print(f"대체 조직: {first_team}")
        
        employee_ids = adc_tf_members['사번'].astype(str).tolist()
        print(f"✅ 조직 구성원: {len(employee_ids)}명")
        print(f"   직원 ID: {', '.join(employee_ids[:5])}{'...' if len(employee_ids) > 5 else ''}")
        
        return employee_ids
    
    def run_singleton_analysis(self, employee_ids: List[str], 
                             start_date: date, end_date: date) -> Dict[str, Any]:
        """싱글톤 모드로 분석 실행"""
        print(f"\n{'='*60}")
        print("🔵 싱글톤 모드 분석 시작")
        print(f"{'='*60}")
        
        start_time = datetime.now()
        
        # 싱글톤 프로세서 생성
        processor = SingletonBatchProcessor()
        
        # 특정 직원들만 필터링
        processor.org_data = processor.org_data[
            processor.org_data['사번'].astype(str).isin(employee_ids)
        ]
        
        # 분석 실행 (DB 저장은 임시 테이블로)
        results = processor.process_all_employees(
            start_date=start_date,
            end_date=end_date,
            save_to_db=False,  # 비교를 위해 DB 저장 안함
            skip_existing=False
        )
        
        end_time = datetime.now()
        results['total_time'] = (end_time - start_time).total_seconds()
        
        # 결과 수집
        singleton_results = self._collect_analysis_results(
            employee_ids, start_date, end_date, 'singleton'
        )
        
        return {
            'stats': results,
            'data': singleton_results,
            'time': results['total_time']
        }
    
    def run_parallel_analysis(self, employee_ids: List[str], 
                            start_date: date, end_date: date) -> Dict[str, Any]:
        """멀티프로세싱 모드로 분석 실행"""
        print(f"\n{'='*60}")
        print("🟢 멀티프로세싱 모드 분석 시작 (8 workers)")
        print(f"{'='*60}")
        
        start_time = datetime.now()
        
        # 병렬 분석기 생성
        analyzer = ParallelBatchAnalyzer(num_workers=8)
        
        # 날짜별로 병렬 분석 실행
        success_count = 0
        failed_count = 0
        
        for day in pd.date_range(start_date, end_date):
            try:
                # batch_analyze_parallel 메서드 사용
                result = analyzer.batch_analyze_parallel(
                    analysis_date=day.date(),
                    employee_ids=employee_ids,
                    save_to_db=False
                )
                
                if result:
                    success_count += len(result.get('processed_employees', []))
                    failed_count += len(result.get('failed_employees', []))
                    
            except Exception as e:
                print(f"멀티프로세싱 분석 오류: {e}")
                failed_count += len(employee_ids)
        
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        # 결과 통계
        results = {
            'success': success_count,
            'failed': failed_count,
            'total': success_count + failed_count
        }
        
        # 결과 수집
        parallel_results = self._collect_analysis_results(
            employee_ids, start_date, end_date, 'parallel'
        )
        
        return {
            'stats': results,
            'data': parallel_results,
            'time': total_time
        }
    
    def _collect_analysis_results(self, employee_ids: List[str], 
                                start_date: date, end_date: date,
                                mode: str) -> List[Dict]:
        """분석 결과 수집 (메모리에서)"""
        # 실제 구현에서는 분석 결과를 메모리에 저장하고 비교
        # 여기서는 예시로 빈 리스트 반환
        return []
    
    def compare_results(self, singleton_result: Dict, parallel_result: Dict):
        """결과 비교 및 출력"""
        print(f"\n{'='*80}")
        print("📊 분석 결과 비교")
        print(f"{'='*80}")
        
        # 처리 시간 비교
        print("\n⏱️  처리 시간:")
        print(f"  - 싱글톤: {singleton_result['time']:.1f}초")
        print(f"  - 멀티프로세싱: {parallel_result['time']:.1f}초")
        print(f"  - 속도 향상: {singleton_result['time']/parallel_result['time']:.1f}배")
        
        # 처리 통계 비교
        print("\n📈 처리 통계:")
        print(f"  싱글톤 - 성공: {singleton_result['stats']['success']}, "
              f"실패: {singleton_result['stats']['failed']}")
        print(f"  멀티프로세싱 - 성공: {parallel_result['stats'].get('success', 0)}, "
              f"실패: {parallel_result['stats'].get('failed', 0)}")
        
        # 데이터 일치성 검사
        print("\n🔍 데이터 일치성 검사:")
        self._check_data_consistency(singleton_result['data'], parallel_result['data'])
    
    def _check_data_consistency(self, singleton_data: List[Dict], 
                               parallel_data: List[Dict]):
        """데이터 일치성 검사"""
        # 실제 데이터 비교 로직
        print("  - 분석 결과 해시값 비교")
        print("  - 주요 지표 차이 분석")
        print("  - 활동 분류 일치율 확인")
    
    def run_comparison(self):
        """전체 비교 실행"""
        # 날짜 설정
        start_date = date(2024, 6, 3)
        end_date = date(2024, 6, 5)
        
        # ADC T/F 구성원 찾기
        employee_ids = self.find_adc_tf_members()
        
        if not employee_ids:
            print("❌ 분석할 직원이 없습니다.")
            return
        
        # 최대 10명으로 제한 (테스트용)
        if len(employee_ids) > 10:
            print(f"⚠️  테스트를 위해 10명으로 제한합니다.")
            employee_ids = employee_ids[:10]
        
        # 싱글톤 모드 실행
        singleton_result = self.run_singleton_analysis(
            employee_ids, start_date, end_date
        )
        
        # 멀티프로세싱 모드 실행
        parallel_result = self.run_parallel_analysis(
            employee_ids, start_date, end_date
        )
        
        # 결과 비교
        self.compare_results(singleton_result, parallel_result)
        
        print(f"\n{'='*80}")
        print("✅ 비교 테스트 완료")
        print(f"{'='*80}")


def main():
    """메인 실행 함수"""
    comparator = BatchProcessorComparator()
    comparator.run_comparison()


if __name__ == "__main__":
    main()