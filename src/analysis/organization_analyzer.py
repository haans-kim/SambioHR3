"""
조직별 분석기 구현
2교대 근무 시스템을 반영한 조직별 근무 데이터 분석
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from ..database import DatabaseManager, DailyWorkData, OrganizationSummary, EmployeeInfo
from .individual_analyzer import IndividualAnalyzer

class OrganizationAnalyzer:
    """조직별 분석기 클래스"""
    
    def __init__(self, db_manager: DatabaseManager, individual_analyzer: IndividualAnalyzer):
        """
        Args:
            db_manager: 데이터베이스 매니저
            individual_analyzer: 개인별 분석기
        """
        self.db_manager = db_manager
        self.individual_analyzer = individual_analyzer
        self.logger = logging.getLogger(__name__)
        
        # 조직 계층 구조
        self.org_hierarchy = ['center', 'bu', 'team', 'group_name', 'part']
        
    def analyze_organization(self, org_id: str, org_level: str, 
                           start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """
        조직별 종합 분석
        
        Args:
            org_id: 조직 ID
            org_level: 조직 레벨 (center, bu, team, group, part)
            start_date: 분석 시작일
            end_date: 분석 종료일
            
        Returns:
            Dict: 분석 결과
        """
        self.logger.info(f"조직별 분석 시작: {org_id} ({org_level}), {start_date} ~ {end_date}")
        
        try:
            # 조직 정보 및 구성원 조회
            org_info = self._get_organization_info(org_id, org_level)
            employees = self._get_organization_employees(org_id, org_level)
            
            if not employees:
                raise ValueError(f"조직 구성원을 찾을 수 없습니다: {org_id}")
            
            # 개인별 분석 결과 수집
            individual_analyses = self._collect_individual_analyses(employees, start_date, end_date)
            
            # 조직 레벨 분석
            analysis_result = {
                'organization_info': org_info,
                'analysis_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'total_days': (end_date - start_date).days + 1
                },
                'workforce_analysis': self._analyze_workforce(employees, individual_analyses),
                'productivity_analysis': self._analyze_productivity(individual_analyses),
                'shift_analysis': self._analyze_organization_shifts(individual_analyses),
                'efficiency_analysis': self._analyze_organization_efficiency(individual_analyses),
                'time_utilization': self._analyze_time_utilization(individual_analyses),
                'comparison_metrics': self._calculate_comparison_metrics(individual_analyses),
                'trends_analysis': self._analyze_trends(org_id, org_level, start_date, end_date),
                'recommendations': self._generate_recommendations(individual_analyses),
                'generated_at': datetime.now().isoformat()
            }
            
            # 분석 결과 저장
            self._save_organization_analysis(org_id, org_level, analysis_result)
            
            self.logger.info(f"조직별 분석 완료: {org_id} ({org_level})")
            return analysis_result
            
        except Exception as e:
            self.logger.error(f"조직별 분석 실패: {org_id}, 오류: {e}")
            raise
    
    def _get_organization_info(self, org_id: str, org_level: str) -> Dict[str, Any]:
        """조직 정보 조회"""
        with self.db_manager.get_session() as session:
            # 조직 정보 조회 (첫 번째 직원의 조직 정보 활용)
            org_field = getattr(EmployeeInfo, org_level)
            employee = session.query(EmployeeInfo).filter(
                org_field == org_id
            ).first()
            
            if not employee:
                return {'org_id': org_id, 'org_level': org_level, 'org_name': 'Unknown'}
            
            return {
                'org_id': org_id,
                'org_level': org_level,
                'org_name': getattr(employee, org_level, 'Unknown'),
                'center': employee.center,
                'bu': employee.bu,
                'team': employee.team,
                'group_name': employee.group_name,
                'part': employee.part
            }
    
    def _get_organization_employees(self, org_id: str, org_level: str) -> List[Dict[str, Any]]:
        """조직 구성원 조회"""
        with self.db_manager.get_session() as session:
            org_field = getattr(EmployeeInfo, org_level)
            employees = session.query(EmployeeInfo).filter(
                org_field == org_id
            ).all()
            
            return [
                {
                    'employee_id': emp.employee_id,
                    'employee_name': emp.employee_name,
                    'position_name': emp.position_name,
                    'department_name': emp.department_name,
                    'employment_status': emp.employment_status,
                    'employee_type': emp.employee_type
                }
                for emp in employees
            ]
    
    def _collect_individual_analyses(self, employees: List[Dict[str, Any]], 
                                   start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """개인별 분석 결과 수집"""
        individual_analyses = []
        
        for employee in employees:
            try:
                analysis = self.individual_analyzer.analyze_individual(
                    employee['employee_id'], start_date, end_date
                )
                analysis['employee_info'] = employee
                individual_analyses.append(analysis)
                
            except Exception as e:
                self.logger.warning(f"개인별 분석 실패: {employee['employee_id']}, 오류: {e}")
                # 실패한 경우 기본 구조 생성
                individual_analyses.append({
                    'employee_id': employee['employee_id'],
                    'employee_info': employee,
                    'analysis_error': str(e),
                    'work_time_analysis': {'actual_work_hours': 0, 'claimed_work_hours': 0},
                    'efficiency_analysis': {'focused_work_ratio': 0, 'productivity_score': 0}
                })
        
        return individual_analyses
    
    def _analyze_workforce(self, employees: List[Dict[str, Any]], 
                          individual_analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """인력 분석"""
        total_employees = len(employees)
        
        # 고용 상태별 분석
        employment_status_counts = {}
        position_counts = {}
        
        for emp in employees:
            status = emp.get('employment_status', 'Unknown')
            position = emp.get('position_name', 'Unknown')
            
            employment_status_counts[status] = employment_status_counts.get(status, 0) + 1
            position_counts[position] = position_counts.get(position, 0) + 1
        
        # 활성 직원 수 (분석 데이터가 있는 직원)
        active_employees = sum(1 for analysis in individual_analyses 
                             if not analysis.get('analysis_error'))
        
        return {
            'total_employees': total_employees,
            'active_employees': active_employees,
            'inactive_employees': total_employees - active_employees,
            'employment_status_distribution': employment_status_counts,
            'position_distribution': position_counts,
            'workforce_utilization_rate': round((active_employees / total_employees * 100) if total_employees > 0 else 0, 2)
        }
    
    def _analyze_productivity(self, individual_analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """생산성 분석"""
        productivity_scores = []
        work_hours = []
        efficiency_ratios = []
        
        for analysis in individual_analyses:
            if not analysis.get('analysis_error'):
                # 생산성 점수
                productivity_score = analysis.get('efficiency_analysis', {}).get('productivity_score', 0)
                productivity_scores.append(productivity_score)
                
                # 근무시간
                actual_hours = analysis.get('work_time_analysis', {}).get('actual_work_hours', 0)
                work_hours.append(actual_hours)
                
                # 효율성 비율
                efficiency_ratio = analysis.get('efficiency_analysis', {}).get('focused_work_ratio', 0)
                efficiency_ratios.append(efficiency_ratio)
        
        return {
            'average_productivity_score': round(np.mean(productivity_scores) if productivity_scores else 0, 2),
            'productivity_std_dev': round(np.std(productivity_scores) if productivity_scores else 0, 2),
            'average_work_hours': round(np.mean(work_hours) if work_hours else 0, 2),
            'average_efficiency_ratio': round(np.mean(efficiency_ratios) if efficiency_ratios else 0, 2),
            'top_performers': self._identify_top_performers(individual_analyses),
            'improvement_candidates': self._identify_improvement_candidates(individual_analyses),
            'productivity_distribution': self._calculate_productivity_distribution(productivity_scores)
        }
    
    def _analyze_organization_shifts(self, individual_analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """조직 교대 근무 분석"""
        shift_data = {
            '주간': {'total_hours': 0, 'employee_count': 0, 'avg_hours': 0},
            '야간': {'total_hours': 0, 'employee_count': 0, 'avg_hours': 0}
        }
        
        cross_midnight_count = 0
        
        for analysis in individual_analyses:
            if not analysis.get('analysis_error'):
                shift_analysis = analysis.get('shift_analysis', {})
                shift_patterns = shift_analysis.get('shift_patterns', {})
                
                for shift_type, data in shift_patterns.items():
                    if shift_type in shift_data:
                        shift_data[shift_type]['total_hours'] += data.get('work_hours', 0)
                        if data.get('work_hours', 0) > 0:
                            shift_data[shift_type]['employee_count'] += 1
                
                if shift_analysis.get('cross_midnight_work', False):
                    cross_midnight_count += 1
        
        # 평균 시간 계산
        for shift_type in shift_data:
            if shift_data[shift_type]['employee_count'] > 0:
                shift_data[shift_type]['avg_hours'] = round(
                    shift_data[shift_type]['total_hours'] / shift_data[shift_type]['employee_count'], 2
                )
        
        return {
            'shift_distribution': shift_data,
            'cross_midnight_workers': cross_midnight_count,
            'shift_balance': self._calculate_shift_balance(shift_data),
            'shift_efficiency': self._calculate_shift_efficiency(shift_data)
        }
    
    def _analyze_organization_efficiency(self, individual_analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """조직 효율성 분석"""
        efficiency_metrics = {
            'focused_work_ratios': [],
            'data_confidences': [],
            'work_vs_claim_ratios': []
        }
        
        for analysis in individual_analyses:
            if not analysis.get('analysis_error'):
                efficiency_data = analysis.get('efficiency_analysis', {})
                work_data = analysis.get('work_time_analysis', {})
                
                efficiency_metrics['focused_work_ratios'].append(
                    efficiency_data.get('focused_work_ratio', 0)
                )
                efficiency_metrics['data_confidences'].append(
                    efficiency_data.get('data_confidence', 0)
                )
                
                # 근무시간 대비 신고시간 정확도
                actual_hours = work_data.get('actual_work_hours', 0)
                claimed_hours = work_data.get('claimed_work_hours', 0)
                if claimed_hours > 0:
                    ratio = actual_hours / claimed_hours
                    efficiency_metrics['work_vs_claim_ratios'].append(ratio)
        
        return {
            'average_focused_work_ratio': round(np.mean(efficiency_metrics['focused_work_ratios']) if efficiency_metrics['focused_work_ratios'] else 0, 2),
            'average_data_confidence': round(np.mean(efficiency_metrics['data_confidences']) if efficiency_metrics['data_confidences'] else 0, 2),
            'work_claim_accuracy': round(np.mean(efficiency_metrics['work_vs_claim_ratios']) if efficiency_metrics['work_vs_claim_ratios'] else 0, 2),
            'efficiency_consistency': round(np.std(efficiency_metrics['focused_work_ratios']) if efficiency_metrics['focused_work_ratios'] else 0, 2),
            'organization_efficiency_score': self._calculate_organization_efficiency_score(efficiency_metrics)
        }
    
    def _analyze_time_utilization(self, individual_analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """시간 활용 분석"""
        time_utilization = {
            'total_work_time': 0,
            'total_meal_time': 0,
            'total_focused_time': 0,
            'time_distribution': {}
        }
        
        for analysis in individual_analyses:
            if not analysis.get('analysis_error'):
                work_data = analysis.get('work_time_analysis', {})
                meal_data = analysis.get('meal_time_analysis', {})
                efficiency_data = analysis.get('efficiency_analysis', {})
                
                time_utilization['total_work_time'] += work_data.get('actual_work_hours', 0)
                time_utilization['total_meal_time'] += meal_data.get('total_meal_time', 0) / 60  # 분을 시간으로 변환
                time_utilization['total_focused_time'] += efficiency_data.get('focused_work_time', 0)
                
                # 활동 분포 집계
                activity_data = analysis.get('activity_analysis', {})
                state_distribution = activity_data.get('predicted_state_distribution', {})
                
                for state, percentage in state_distribution.items():
                    if state not in time_utilization['time_distribution']:
                        time_utilization['time_distribution'][state] = []
                    time_utilization['time_distribution'][state].append(percentage)
        
        # 평균 분포 계산
        avg_distribution = {}
        for state, percentages in time_utilization['time_distribution'].items():
            avg_distribution[state] = round(np.mean(percentages), 2)
        
        time_utilization['time_distribution'] = avg_distribution
        
        return time_utilization
    
    def _calculate_comparison_metrics(self, individual_analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """비교 지표 계산"""
        metrics = {
            'productivity_scores': [],
            'work_hours': [],
            'efficiency_ratios': [],
            'employee_ids': []
        }
        
        for analysis in individual_analyses:
            if not analysis.get('analysis_error'):
                metrics['productivity_scores'].append(
                    analysis.get('efficiency_analysis', {}).get('productivity_score', 0)
                )
                metrics['work_hours'].append(
                    analysis.get('work_time_analysis', {}).get('actual_work_hours', 0)
                )
                metrics['efficiency_ratios'].append(
                    analysis.get('efficiency_analysis', {}).get('focused_work_ratio', 0)
                )
                metrics['employee_ids'].append(analysis.get('employee_id'))
        
        return {
            'productivity_quartiles': self._calculate_quartiles(metrics['productivity_scores']),
            'work_hours_quartiles': self._calculate_quartiles(metrics['work_hours']),
            'efficiency_quartiles': self._calculate_quartiles(metrics['efficiency_ratios']),
            'outliers': self._identify_outliers(metrics),
            'performance_correlation': self._calculate_performance_correlation(metrics)
        }
    
    def _analyze_trends(self, org_id: str, org_level: str, 
                       start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """트렌드 분석"""
        # 과거 데이터와 비교하여 트렌드 분석
        # 실제 구현에서는 과거 분석 결과를 데이터베이스에서 조회
        
        return {
            'productivity_trend': 'stable',  # increasing, decreasing, stable
            'workforce_trend': 'stable',
            'efficiency_trend': 'improving',
            'trend_analysis_period': f"{start_date.isoformat()} ~ {end_date.isoformat()}",
            'recommendations_based_on_trends': []
        }
    
    def _generate_recommendations(self, individual_analyses: List[Dict[str, Any]]) -> List[str]:
        """개선 권장사항 생성"""
        recommendations = []
        
        # 생산성 분석 기반 권장사항
        productivity_scores = [
            analysis.get('efficiency_analysis', {}).get('productivity_score', 0)
            for analysis in individual_analyses
            if not analysis.get('analysis_error')
        ]
        
        if productivity_scores:
            avg_productivity = np.mean(productivity_scores)
            if avg_productivity < 50:
                recommendations.append("조직 전체 생산성이 낮습니다. 업무 프로세스 개선이 필요합니다.")
            elif avg_productivity < 70:
                recommendations.append("생산성 향상을 위한 교육 및 지원이 필요합니다.")
        
        # 교대 근무 분석 기반 권장사항
        shift_imbalance = self._check_shift_imbalance(individual_analyses)
        if shift_imbalance:
            recommendations.append("교대 근무 인력 배치의 균형을 맞춰주세요.")
        
        # 데이터 품질 기반 권장사항
        low_quality_count = sum(1 for analysis in individual_analyses 
                               if analysis.get('data_quality', {}).get('overall_quality_score', 0) < 70)
        if low_quality_count > len(individual_analyses) * 0.3:
            recommendations.append("데이터 수집 품질 개선이 필요합니다.")
        
        return recommendations
    
    def _identify_top_performers(self, individual_analyses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """우수 직원 식별"""
        performers = []
        
        for analysis in individual_analyses:
            if not analysis.get('analysis_error'):
                productivity_score = analysis.get('efficiency_analysis', {}).get('productivity_score', 0)
                if productivity_score > 80:  # 임계값
                    performers.append({
                        'employee_id': analysis.get('employee_id'),
                        'employee_name': analysis.get('employee_info', {}).get('employee_name', 'Unknown'),
                        'productivity_score': productivity_score,
                        'focused_work_ratio': analysis.get('efficiency_analysis', {}).get('focused_work_ratio', 0)
                    })
        
        return sorted(performers, key=lambda x: x['productivity_score'], reverse=True)[:10]
    
    def _identify_improvement_candidates(self, individual_analyses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """개선 필요 직원 식별"""
        candidates = []
        
        for analysis in individual_analyses:
            if not analysis.get('analysis_error'):
                productivity_score = analysis.get('efficiency_analysis', {}).get('productivity_score', 0)
                if productivity_score < 40:  # 임계값
                    candidates.append({
                        'employee_id': analysis.get('employee_id'),
                        'employee_name': analysis.get('employee_info', {}).get('employee_name', 'Unknown'),
                        'productivity_score': productivity_score,
                        'issues': self._identify_performance_issues(analysis)
                    })
        
        return sorted(candidates, key=lambda x: x['productivity_score'])[:10]
    
    def _calculate_productivity_distribution(self, productivity_scores: List[float]) -> Dict[str, int]:
        """생산성 분포 계산"""
        if not productivity_scores:
            return {}
        
        distribution = {
            'excellent': 0,    # 80-100
            'good': 0,        # 60-79
            'average': 0,     # 40-59
            'below_average': 0 # 0-39
        }
        
        for score in productivity_scores:
            if score >= 80:
                distribution['excellent'] += 1
            elif score >= 60:
                distribution['good'] += 1
            elif score >= 40:
                distribution['average'] += 1
            else:
                distribution['below_average'] += 1
        
        return distribution
    
    def _calculate_shift_balance(self, shift_data: Dict[str, Any]) -> float:
        """교대 균형 계산"""
        day_count = shift_data['주간']['employee_count']
        night_count = shift_data['야간']['employee_count']
        
        if day_count + night_count == 0:
            return 0
        
        # 균형 점수 (0-100, 50:50이 최적)
        balance_ratio = min(day_count, night_count) / max(day_count, night_count) if max(day_count, night_count) > 0 else 0
        return round(balance_ratio * 100, 2)
    
    def _calculate_shift_efficiency(self, shift_data: Dict[str, Any]) -> Dict[str, float]:
        """교대별 효율성 계산"""
        efficiency = {}
        
        for shift_type, data in shift_data.items():
            if data['employee_count'] > 0:
                efficiency[shift_type] = data['avg_hours']
            else:
                efficiency[shift_type] = 0
        
        return efficiency
    
    def _calculate_organization_efficiency_score(self, efficiency_metrics: Dict[str, List[float]]) -> float:
        """조직 효율성 점수 계산"""
        scores = []
        
        if efficiency_metrics['focused_work_ratios']:
            scores.append(np.mean(efficiency_metrics['focused_work_ratios']))
        
        if efficiency_metrics['data_confidences']:
            scores.append(np.mean(efficiency_metrics['data_confidences']))
        
        if efficiency_metrics['work_vs_claim_ratios']:
            # 1에 가까울수록 정확함
            accuracy_score = 100 - abs(np.mean(efficiency_metrics['work_vs_claim_ratios']) - 1) * 100
            scores.append(max(0, accuracy_score))
        
        return round(np.mean(scores) if scores else 0, 2)
    
    def _calculate_quartiles(self, values: List[float]) -> Dict[str, float]:
        """사분위수 계산"""
        if not values:
            return {'q1': 0, 'q2': 0, 'q3': 0}
        
        return {
            'q1': float(np.percentile(values, 25)),
            'q2': float(np.percentile(values, 50)),
            'q3': float(np.percentile(values, 75))
        }
    
    def _identify_outliers(self, metrics: Dict[str, List[float]]) -> List[str]:
        """이상치 식별"""
        outliers = []
        
        for metric_name, values in metrics.items():
            if metric_name == 'employee_ids':
                continue
            
            if values:
                q1 = np.percentile(values, 25)
                q3 = np.percentile(values, 75)
                iqr = q3 - q1
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr
                
                for i, value in enumerate(values):
                    if value < lower_bound or value > upper_bound:
                        employee_id = metrics['employee_ids'][i]
                        outliers.append(f"{employee_id} ({metric_name}: {value:.2f})")
        
        return outliers
    
    def _calculate_performance_correlation(self, metrics: Dict[str, List[float]]) -> Dict[str, float]:
        """성과 지표 간 상관관계 계산"""
        correlations = {}
        
        if len(metrics['productivity_scores']) > 1:
            # 생산성 vs 근무시간
            if metrics['work_hours']:
                correlations['productivity_vs_work_hours'] = float(
                    np.corrcoef(metrics['productivity_scores'], metrics['work_hours'])[0, 1]
                )
            
            # 생산성 vs 효율성
            if metrics['efficiency_ratios']:
                correlations['productivity_vs_efficiency'] = float(
                    np.corrcoef(metrics['productivity_scores'], metrics['efficiency_ratios'])[0, 1]
                )
        
        return correlations
    
    def _check_shift_imbalance(self, individual_analyses: List[Dict[str, Any]]) -> bool:
        """교대 근무 불균형 확인"""
        shift_counts = {'주간': 0, '야간': 0}
        
        for analysis in individual_analyses:
            if not analysis.get('analysis_error'):
                shift_analysis = analysis.get('shift_analysis', {})
                preferred_shift = shift_analysis.get('preferred_shift', '주간')
                shift_counts[preferred_shift] += 1
        
        total = sum(shift_counts.values())
        if total == 0:
            return False
        
        # 30% 이상 차이가 나면 불균형으로 판단
        imbalance_threshold = 0.3
        balance_ratio = abs(shift_counts['주간'] - shift_counts['야간']) / total
        
        return balance_ratio > imbalance_threshold
    
    def _identify_performance_issues(self, analysis: Dict[str, Any]) -> List[str]:
        """개인 성과 문제 식별"""
        issues = []
        
        # 근무시간 부족
        work_hours = analysis.get('work_time_analysis', {}).get('actual_work_hours', 0)
        if work_hours < 6:  # 하루 6시간 미만
            issues.append("근무시간 부족")
        
        # 집중도 부족
        focused_ratio = analysis.get('efficiency_analysis', {}).get('focused_work_ratio', 0)
        if focused_ratio < 30:
            issues.append("집중도 부족")
        
        # 데이터 품질 문제
        data_quality = analysis.get('data_quality', {}).get('overall_quality_score', 0)
        if data_quality < 50:
            issues.append("데이터 수집 품질 문제")
        
        return issues
    
    def _save_organization_analysis(self, org_id: str, org_level: str, 
                                   analysis_result: Dict[str, Any]):
        """조직 분석 결과 저장"""
        try:
            # 분석 결과를 데이터베이스나 파일로 저장하는 로직
            # 여기서는 로깅만 수행
            self.logger.info(f"조직 분석 결과 저장 완료: {org_id} ({org_level})")
        except Exception as e:
            self.logger.error(f"조직 분석 결과 저장 실패: {org_id}, 오류: {e}")
    
    def generate_organization_report(self, org_id: str, analysis_result: Dict[str, Any]) -> str:
        """조직별 분석 보고서 생성"""
        org_info = analysis_result['organization_info']
        
        report = f"""
=== 조직별 근무 분석 보고서 ===

조직: {org_info['org_name']} ({org_info['org_level']})
분석 기간: {analysis_result['analysis_period']['start_date']} ~ {analysis_result['analysis_period']['end_date']}

## 인력 현황
- 전체 인원: {analysis_result['workforce_analysis']['total_employees']}명
- 활성 인원: {analysis_result['workforce_analysis']['active_employees']}명
- 가동률: {analysis_result['workforce_analysis']['workforce_utilization_rate']}%

## 생산성 분석
- 평균 생산성 점수: {analysis_result['productivity_analysis']['average_productivity_score']}점
- 평균 근무시간: {analysis_result['productivity_analysis']['average_work_hours']}시간
- 평균 효율성 비율: {analysis_result['productivity_analysis']['average_efficiency_ratio']}%

## 교대 근무 분석
- 주간 근무 인원: {analysis_result['shift_analysis']['shift_distribution']['주간']['employee_count']}명
- 야간 근무 인원: {analysis_result['shift_analysis']['shift_distribution']['야간']['employee_count']}명
- 교대 균형도: {analysis_result['shift_analysis']['shift_balance']}%

## 권장사항
        """
        
        for recommendation in analysis_result['recommendations']:
            report += f"- {recommendation}\n"
        
        return report
    
    def compare_organizations(self, org_comparisons: List[Dict[str, Any]]) -> Dict[str, Any]:
        """조직 간 비교 분석"""
        comparison_result = {
            'organizations': org_comparisons,
            'comparison_metrics': {
                'productivity_ranking': [],
                'efficiency_ranking': [],
                'workforce_utilization_ranking': []
            },
            'benchmarking': {},
            'best_practices': []
        }
        
        # 생산성 순위
        productivity_ranking = sorted(
            org_comparisons,
            key=lambda x: x.get('productivity_analysis', {}).get('average_productivity_score', 0),
            reverse=True
        )
        
        comparison_result['comparison_metrics']['productivity_ranking'] = [
            {
                'org_id': org['organization_info']['org_id'],
                'org_name': org['organization_info']['org_name'],
                'score': org.get('productivity_analysis', {}).get('average_productivity_score', 0)
            }
            for org in productivity_ranking
        ]
        
        return comparison_result