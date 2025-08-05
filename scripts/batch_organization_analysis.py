"""
조직 단위 배치 분석 스크립트
개인별 분석 모듈의 시간 산정 로직을 활용하여 전체 조직 구성원을 일괄 분석
"""

import os
import sys
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
from tqdm import tqdm
import argparse

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import get_database_manager, get_pickle_manager
from src.analysis import IndividualAnalyzer
from src.analysis.analysis_result_saver import AnalysisResultSaver
from src.ui.components.individual_dashboard import IndividualDashboard


class BatchOrganizationAnalyzer:
    """조직 단위 배치 분석 클래스"""
    
    def __init__(self):
        self.db_manager = get_database_manager()
        self.pickle_manager = get_pickle_manager()
        self.analyzer = IndividualAnalyzer(self.db_manager)
        self.result_saver = AnalysisResultSaver()
        
        # IndividualDashboard의 분석 메서드들을 재사용
        self.dashboard = IndividualDashboard(self.analyzer)
        
        # 로깅 설정
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def get_organization_employees(self, 
                                 center_id: Optional[str] = None,
                                 group_id: Optional[str] = None,
                                 team_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """조직별 직원 목록 조회"""
        
        # 조직 현황 데이터에서 직원 정보 추출
        org_data = self.pickle_manager.load_dataframe(name='organization_data')
        
        if org_data is None:
            self.logger.error("조직 데이터를 찾을 수 없습니다.")
            return []
        
        # 필터링
        filtered_data = org_data.copy()
        
        if center_id:
            filtered_data = filtered_data[filtered_data['센터'] == center_id]
        if group_id:
            filtered_data = filtered_data[filtered_data['그룹'] == group_id]
        if team_id:
            filtered_data = filtered_data[filtered_data['팀'] == team_id]
        
        # 직원 정보 리스트 생성
        employees = []
        for _, row in filtered_data.iterrows():
            employees.append({
                'employee_id': row['사번'],
                'employee_name': row['성명'],
                'center_id': row['센터'],
                'center_name': row['센터'],
                'group_id': row['그룹'],
                'group_name': row['그룹'],
                'team_id': row['팀'],
                'team_name': row['팀'],
                'job_grade': row.get('직급2*')  # 직급 정보 추가
            })
        
        return employees
    
    def analyze_employee_simple(self, employee_id: str, analysis_date: date) -> Optional[Dict[str, Any]]:
        """
        개인별 분석 수행 (시간 산정 중심)
        네트워크 분석, Gantt 차트 등 시각화 요소 제외
        """
        try:
            # 1. 태그 데이터 가져오기
            daily_data = self.dashboard.get_daily_tag_data(employee_id, analysis_date)
            
            if daily_data is None or daily_data.empty:
                self.logger.warning(f"데이터 없음: {employee_id} - {analysis_date}")
                return None
            
            # 2. 장비 데이터 로드 (O 태그 변환용)
            equipment_data = self.dashboard.get_employee_equipment_data(employee_id, analysis_date)
            
            # 3. 활동 분류 수행
            classified_data = self.dashboard.classify_activities(daily_data, employee_id, analysis_date)
            
            # 4. 일일 분석 실행 (analyze_daily_data 호출)
            analysis_result = self.dashboard.analyze_daily_data(
                employee_id,
                analysis_date,
                classified_data
            )
            
            # 5. 불필요한 데이터 제거 (메모리 절약)
            if 'raw_data' in analysis_result:
                del analysis_result['raw_data']
            if 'daily_analysis' in analysis_result:
                del analysis_result['daily_analysis']
            if 'timeline_data' in analysis_result:
                del analysis_result['timeline_data']
            if 'activity_segments' in analysis_result and len(analysis_result['activity_segments']) > 100:
                # 세그먼트가 너무 많으면 요약만 유지
                analysis_result['segment_count'] = len(analysis_result['activity_segments'])
                del analysis_result['activity_segments']
            
            return analysis_result
            
        except Exception as e:
            self.logger.error(f"분석 오류 {employee_id}: {e}")
            return None
    
    def batch_analyze_organization(self, 
                                 analysis_date: date,
                                 center_id: Optional[str] = None,
                                 group_id: Optional[str] = None,
                                 team_id: Optional[str] = None,
                                 save_to_db: bool = True) -> Dict[str, Any]:
        """
        조직 단위 배치 분석 실행
        
        Args:
            analysis_date: 분석 날짜
            center_id: 센터 ID (None이면 전체)
            group_id: 그룹 ID
            team_id: 팀 ID
            save_to_db: DB 저장 여부
            
        Returns:
            분석 결과 요약
        """
        
        # 시작 시간
        start_time = datetime.now()
        
        # 분석할 직원 목록 조회
        employees = self.get_organization_employees(center_id, group_id, team_id)
        
        if not employees:
            self.logger.warning("분석할 직원이 없습니다.")
            return {'status': 'no_employees', 'total': 0}
        
        self.logger.info(f"분석 시작: {len(employees)}명, 날짜: {analysis_date}")
        
        # 분석 결과 저장
        results = []
        success_count = 0
        error_count = 0
        
        # 진행률 표시
        for employee in tqdm(employees, desc="직원별 분석 진행"):
            try:
                # 개인별 분석 수행
                analysis_result = self.analyze_employee_simple(
                    employee['employee_id'], 
                    analysis_date
                )
                
                if analysis_result:
                    # DB 저장
                    if save_to_db:
                        self.logger.info(f"저장 시도: {employee['employee_id']}")
                        saved = self.result_saver.save_individual_analysis(
                            analysis_result,
                            employee
                        )
                        if saved:
                            success_count += 1
                            self.logger.info(f"저장 성공: {employee['employee_id']}")
                        else:
                            error_count += 1
                            self.logger.error(f"저장 실패: {employee['employee_id']}")
                    else:
                        success_count += 1
                    
                    results.append(analysis_result)
                else:
                    error_count += 1
                    self.logger.warning(f"분석 결과 없음: {employee['employee_id']}")
                    
            except Exception as e:
                self.logger.error(f"직원 {employee['employee_id']} 분석 실패: {e}")
                error_count += 1
        
        # 소요 시간
        elapsed_time = (datetime.now() - start_time).total_seconds()
        
        # 결과 요약
        summary = {
            'status': 'completed',
            'analysis_date': analysis_date.isoformat(),
            'organization': {
                'center_id': center_id,
                'group_id': group_id,
                'team_id': team_id
            },
            'total_employees': len(employees),
            'analyzed_count': success_count,
            'error_count': error_count,
            'success_rate': round(success_count / len(employees) * 100, 1) if employees else 0,
            'elapsed_seconds': round(elapsed_time, 1),
            'saved_to_db': save_to_db
        }
        
        # 평균 지표 계산
        if results:
            avg_efficiency = sum(r['work_time_analysis']['efficiency_ratio'] for r in results) / len(results)
            avg_work_hours = sum(r['work_time_analysis']['actual_work_hours'] for r in results) / len(results)
            
            summary['averages'] = {
                'efficiency_ratio': round(avg_efficiency, 1),
                'actual_work_hours': round(avg_work_hours, 1)
            }
        
        self.logger.info(f"배치 분석 완료: {summary}")
        
        return summary
    
    def analyze_date_range(self,
                          start_date: date,
                          end_date: date,
                          center_id: Optional[str] = None,
                          group_id: Optional[str] = None,
                          team_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """날짜 범위에 대한 배치 분석"""
        
        results = []
        current_date = start_date
        
        while current_date <= end_date:
            self.logger.info(f"=== {current_date} 분석 시작 ===")
            
            summary = self.batch_analyze_organization(
                current_date,
                center_id=center_id,
                group_id=group_id,
                team_id=team_id,
                save_to_db=True
            )
            
            results.append(summary)
            current_date += timedelta(days=1)
        
        return results


def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description='조직 단위 배치 분석')
    
    parser.add_argument('--date', type=str, help='분석 날짜 (YYYY-MM-DD)')
    parser.add_argument('--start-date', type=str, help='시작 날짜 (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='종료 날짜 (YYYY-MM-DD)')
    parser.add_argument('--center', type=str, help='센터 ID')
    parser.add_argument('--group', type=str, help='그룹 ID')
    parser.add_argument('--team', type=str, help='팀 ID')
    parser.add_argument('--no-save', action='store_true', help='DB 저장 안함')
    
    args = parser.parse_args()
    
    # 배치 분석기 생성
    analyzer = BatchOrganizationAnalyzer()
    
    # 날짜 처리
    if args.date:
        # 단일 날짜 분석
        analysis_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        
        summary = analyzer.batch_analyze_organization(
            analysis_date,
            center_id=args.center,
            group_id=args.group,
            team_id=args.team,
            save_to_db=not args.no_save
        )
        
        print(f"\n분석 완료:")
        print(f"- 총 직원: {summary['total_employees']}명")
        print(f"- 분석 성공: {summary['analyzed_count']}명")
        print(f"- 성공률: {summary['success_rate']}%")
        print(f"- 소요 시간: {summary['elapsed_seconds']}초")
        
    elif args.start_date and args.end_date:
        # 날짜 범위 분석
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
        
        results = analyzer.analyze_date_range(
            start_date,
            end_date,
            center_id=args.center,
            group_id=args.group,
            team_id=args.team
        )
        
        print(f"\n전체 분석 완료:")
        print(f"- 분석 기간: {start_date} ~ {end_date}")
        print(f"- 총 {len(results)}일 분석")
        
        total_analyzed = sum(r['analyzed_count'] for r in results)
        total_employees = sum(r['total_employees'] for r in results)
        print(f"- 총 분석 건수: {total_analyzed}건")
        print(f"- 평균 성공률: {round(total_analyzed / total_employees * 100, 1)}%")
        
    else:
        print("날짜를 지정해주세요. (--date 또는 --start-date, --end-date)")


if __name__ == "__main__":
    main()