"""
데이터 모델 및 비즈니스 로직
데이터베이스 모델과 관련된 비즈니스 로직을 정의합니다.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, asc
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import logging

from .schema import (
    DailyWorkData, ShiftWorkData, OrganizationSummary, TagLogs,
    AbcActivityData, ClaimData, AttendanceData, NonWorkTimeData,
    EmployeeInfo, TagLocationMaster, OrganizationMapping,
    HmmModelConfig, ProcessingLog
)

class WorkDataModel:
    """근무 데이터 관련 모델"""
    
    def __init__(self, session: Session):
        self.session = session
        self.logger = logging.getLogger(__name__)
    
    def get_daily_work_data(self, employee_id: str, start_date: datetime, 
                          end_date: datetime) -> List[DailyWorkData]:
        """개인별 일간 근무 데이터 조회"""
        return self.session.query(DailyWorkData).filter(
            and_(
                DailyWorkData.employee_id == employee_id,
                DailyWorkData.work_date >= start_date,
                DailyWorkData.work_date <= end_date
            )
        ).order_by(DailyWorkData.work_date).all()
    
    def get_shift_work_summary(self, employee_id: str, month: int, year: int) -> Dict[str, Any]:
        """월별 교대근무 요약"""
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(days=1)
        
        # 교대별 근무 통계
        shift_stats = self.session.query(
            DailyWorkData.shift_type,
            func.count(DailyWorkData.id).label('work_days'),
            func.avg(DailyWorkData.actual_work_time).label('avg_work_time'),
            func.sum(DailyWorkData.actual_work_time).label('total_work_time')
        ).filter(
            and_(
                DailyWorkData.employee_id == employee_id,
                DailyWorkData.work_date >= start_date,
                DailyWorkData.work_date <= end_date
            )
        ).group_by(DailyWorkData.shift_type).all()
        
        # 식사시간 통계
        meal_stats = self.session.query(
            func.avg(DailyWorkData.breakfast_time).label('avg_breakfast'),
            func.avg(DailyWorkData.lunch_time).label('avg_lunch'),
            func.avg(DailyWorkData.dinner_time).label('avg_dinner'),
            func.avg(DailyWorkData.midnight_meal_time).label('avg_midnight_meal'),
            func.avg(DailyWorkData.meal_time).label('avg_total_meal')
        ).filter(
            and_(
                DailyWorkData.employee_id == employee_id,
                DailyWorkData.work_date >= start_date,
                DailyWorkData.work_date <= end_date
            )
        ).first()
        
        return {
            'period': f"{year}-{month:02d}",
            'shift_stats': [
                {
                    'shift_type': stat.shift_type,
                    'work_days': stat.work_days,
                    'avg_work_time': round(stat.avg_work_time or 0, 2),
                    'total_work_time': round(stat.total_work_time or 0, 2)
                }
                for stat in shift_stats
            ],
            'meal_stats': {
                'avg_breakfast': round(meal_stats.avg_breakfast or 0, 2),
                'avg_lunch': round(meal_stats.avg_lunch or 0, 2),
                'avg_dinner': round(meal_stats.avg_dinner or 0, 2),
                'avg_midnight_meal': round(meal_stats.avg_midnight_meal or 0, 2),
                'avg_total_meal': round(meal_stats.avg_total_meal or 0, 2)
            }
        }
    
    def get_efficiency_comparison(self, employee_id: str, start_date: datetime, 
                                end_date: datetime) -> Dict[str, Any]:
        """근무 효율성 비교 (Claim vs 실제)"""
        # 일간 데이터와 Claim 데이터 조인
        comparison_data = self.session.query(
            DailyWorkData.work_date,
            DailyWorkData.actual_work_time,
            DailyWorkData.efficiency_ratio,
            ClaimData.claimed_work_hours,
            ClaimData.actual_work_duration
        ).join(
            ClaimData,
            and_(
                DailyWorkData.employee_id == ClaimData.employee_id,
                DailyWorkData.work_date == ClaimData.work_date
            )
        ).filter(
            and_(
                DailyWorkData.employee_id == employee_id,
                DailyWorkData.work_date >= start_date,
                DailyWorkData.work_date <= end_date
            )
        ).all()
        
        if not comparison_data:
            return {'error': '데이터가 없습니다.'}
        
        # 통계 계산
        total_actual = sum(row.actual_work_time or 0 for row in comparison_data)
        total_claimed = sum(row.actual_work_duration or 0 for row in comparison_data)
        avg_efficiency = sum(row.efficiency_ratio or 0 for row in comparison_data) / len(comparison_data)
        
        return {
            'period': f"{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}",
            'total_actual_hours': round(total_actual, 2),
            'total_claimed_hours': round(total_claimed, 2),
            'difference_hours': round(total_actual - total_claimed, 2),
            'efficiency_ratio': round(avg_efficiency, 2),
            'accuracy_ratio': round((total_actual / total_claimed * 100) if total_claimed > 0 else 0, 2),
            'daily_data': [
                {
                    'date': row.work_date.strftime('%Y-%m-%d'),
                    'actual_hours': round(row.actual_work_time or 0, 2),
                    'claimed_hours': round(row.actual_work_duration or 0, 2),
                    'efficiency': round(row.efficiency_ratio or 0, 2)
                }
                for row in comparison_data
            ]
        }

class TagDataModel:
    """태그 데이터 관련 모델"""
    
    def __init__(self, session: Session):
        self.session = session
        self.logger = logging.getLogger(__name__)
    
    def get_daily_timeline(self, employee_id: str, date: datetime) -> List[Dict[str, Any]]:
        """일일 활동 타임라인 조회"""
        tag_logs = self.session.query(TagLogs).filter(
            and_(
                TagLogs.employee_id == employee_id,
                func.date(TagLogs.timestamp) == date.date()
            )
        ).order_by(TagLogs.timestamp).all()
        
        timeline = []
        for log in tag_logs:
            timeline.append({
                'timestamp': log.timestamp,
                'location': log.tag_location,
                'gate_name': log.gate_name,
                'action': log.action_type,
                'work_area_type': log.work_area_type,
                'meal_type': log.meal_type,
                'is_tailgating': log.is_tailgating,
                'confidence': log.confidence_score
            })
        
        return timeline
    
    def get_meal_time_analysis(self, employee_id: str, start_date: datetime, 
                             end_date: datetime) -> Dict[str, Any]:
        """식사시간 분석"""
        meal_data = self.session.query(
            TagLogs.meal_type,
            func.count(TagLogs.id).label('frequency'),
            func.avg(
                func.julianday(TagLogs.timestamp) * 24 * 60
            ).label('avg_time_minutes')
        ).filter(
            and_(
                TagLogs.employee_id == employee_id,
                TagLogs.meal_type.isnot(None),
                TagLogs.timestamp >= start_date,
                TagLogs.timestamp <= end_date
            )
        ).group_by(TagLogs.meal_type).all()
        
        meal_stats = {}
        for meal in meal_data:
            meal_stats[meal.meal_type] = {
                'frequency': meal.frequency,
                'avg_time': f"{int(meal.avg_time_minutes // 60):02d}:{int(meal.avg_time_minutes % 60):02d}"
            }
        
        return {
            'period': f"{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}",
            'meal_stats': meal_stats,
            'total_meal_events': sum(meal.frequency for meal in meal_data)
        }
    
    def get_location_frequency(self, employee_id: str, start_date: datetime, 
                             end_date: datetime) -> List[Dict[str, Any]]:
        """위치별 방문 빈도"""
        location_stats = self.session.query(
            TagLogs.tag_location,
            TagLogs.work_area_type,
            func.count(TagLogs.id).label('visit_count'),
            func.count(func.distinct(func.date(TagLogs.timestamp))).label('visit_days')
        ).filter(
            and_(
                TagLogs.employee_id == employee_id,
                TagLogs.timestamp >= start_date,
                TagLogs.timestamp <= end_date
            )
        ).group_by(TagLogs.tag_location, TagLogs.work_area_type).all()
        
        return [
            {
                'location': stat.tag_location,
                'work_area_type': stat.work_area_type,
                'visit_count': stat.visit_count,
                'visit_days': stat.visit_days,
                'avg_visits_per_day': round(stat.visit_count / stat.visit_days, 2)
            }
            for stat in location_stats
        ]

class OrganizationModel:
    """조직 관련 모델"""
    
    def __init__(self, session: Session):
        self.session = session
        self.logger = logging.getLogger(__name__)
    
    def get_organization_summary(self, org_id: str, start_date: datetime, 
                               end_date: datetime) -> Dict[str, Any]:
        """조직별 요약 데이터"""
        org_data = self.session.query(OrganizationSummary).filter(
            and_(
                OrganizationSummary.org_id == org_id,
                OrganizationSummary.date >= start_date,
                OrganizationSummary.date <= end_date
            )
        ).order_by(OrganizationSummary.date).all()
        
        if not org_data:
            return {'error': '조직 데이터가 없습니다.'}
        
        # 평균 통계 계산
        avg_work_time = sum(data.avg_work_time or 0 for data in org_data) / len(org_data)
        avg_efficiency = sum(data.avg_efficiency_ratio or 0 for data in org_data) / len(org_data)
        avg_operation_rate = sum(data.operation_rate or 0 for data in org_data) / len(org_data)
        
        return {
            'org_id': org_id,
            'org_name': org_data[0].org_name,
            'period': f"{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}",
            'avg_work_time': round(avg_work_time, 2),
            'avg_efficiency_ratio': round(avg_efficiency, 2),
            'avg_operation_rate': round(avg_operation_rate, 2),
            'total_employees': org_data[-1].total_employees,
            'daily_data': [
                {
                    'date': data.date.strftime('%Y-%m-%d'),
                    'avg_work_time': round(data.avg_work_time or 0, 2),
                    'efficiency_ratio': round(data.avg_efficiency_ratio or 0, 2),
                    'operation_rate': round(data.operation_rate or 0, 2),
                    'day_shift_count': data.day_shift_count,
                    'night_shift_count': data.night_shift_count
                }
                for data in org_data
            ]
        }
    
    def get_organization_ranking(self, metric: str, start_date: datetime, 
                               end_date: datetime, limit: int = 10) -> List[Dict[str, Any]]:
        """조직별 순위 (특정 지표 기준)"""
        valid_metrics = ['avg_work_time', 'avg_efficiency_ratio', 'operation_rate']
        if metric not in valid_metrics:
            raise ValueError(f"잘못된 지표: {metric}")
        
        # 기간별 평균 계산
        ranking_data = self.session.query(
            OrganizationSummary.org_id,
            OrganizationSummary.org_name,
            func.avg(getattr(OrganizationSummary, metric)).label('avg_metric'),
            func.sum(OrganizationSummary.total_employees).label('total_employees')
        ).filter(
            and_(
                OrganizationSummary.date >= start_date,
                OrganizationSummary.date <= end_date
            )
        ).group_by(
            OrganizationSummary.org_id,
            OrganizationSummary.org_name
        ).order_by(desc('avg_metric')).limit(limit).all()
        
        return [
            {
                'rank': idx + 1,
                'org_id': data.org_id,
                'org_name': data.org_name,
                'metric_value': round(data.avg_metric or 0, 2),
                'total_employees': data.total_employees
            }
            for idx, data in enumerate(ranking_data)
        ]

class EmployeeModel:
    """직원 관련 모델"""
    
    def __init__(self, session: Session):
        self.session = session
        self.logger = logging.getLogger(__name__)
    
    def get_employee_info(self, employee_id: str) -> Optional[Dict[str, Any]]:
        """직원 정보 조회"""
        employee = self.session.query(EmployeeInfo).filter(
            EmployeeInfo.employee_id == employee_id
        ).first()
        
        if not employee:
            return None
        
        return {
            'employee_id': employee.employee_id,
            'employee_name': employee.employee_name,
            'department': employee.department_name,
            'position': employee.position_name,
            'center': employee.center,
            'bu': employee.bu,
            'team': employee.team,
            'group': employee.group_name,
            'part': employee.part,
            'join_date': employee.company_join_date,
            'employment_status': employee.employment_status,
            'employee_type': employee.employee_type
        }
    
    def search_employees(self, keyword: str, limit: int = 50) -> List[Dict[str, Any]]:
        """직원 검색"""
        employees = self.session.query(EmployeeInfo).filter(
            or_(
                EmployeeInfo.employee_name.contains(keyword),
                EmployeeInfo.employee_id.contains(keyword),
                EmployeeInfo.department_name.contains(keyword)
            )
        ).limit(limit).all()
        
        return [
            {
                'employee_id': emp.employee_id,
                'employee_name': emp.employee_name,
                'department': emp.department_name,
                'position': emp.position_name,
                'center': emp.center
            }
            for emp in employees
        ]
    
    def get_department_employees(self, department_name: str) -> List[Dict[str, Any]]:
        """부서별 직원 목록"""
        employees = self.session.query(EmployeeInfo).filter(
            EmployeeInfo.department_name == department_name
        ).order_by(EmployeeInfo.employee_name).all()
        
        return [
            {
                'employee_id': emp.employee_id,
                'employee_name': emp.employee_name,
                'position': emp.position_name,
                'employment_status': emp.employment_status
            }
            for emp in employees
        ]

class HmmModelManager:
    """HMM 모델 관리"""
    
    def __init__(self, session: Session):
        self.session = session
        self.logger = logging.getLogger(__name__)
    
    def save_model_config(self, model_name: str, version: str, 
                         config_data: Dict[str, Any]) -> int:
        """HMM 모델 설정 저장"""
        import json
        
        model_config = HmmModelConfig(
            model_name=model_name,
            model_version=version,
            states=json.dumps(config_data['states']),
            transition_matrix=json.dumps(config_data['transition_matrix']),
            emission_matrix=json.dumps(config_data['emission_matrix']),
            initial_probabilities=json.dumps(config_data['initial_probabilities']),
            model_parameters=json.dumps(config_data.get('parameters', {})),
            training_accuracy=config_data.get('training_accuracy'),
            validation_accuracy=config_data.get('validation_accuracy')
        )
        
        self.session.add(model_config)
        self.session.commit()
        
        self.logger.info(f"HMM 모델 설정 저장 완료: {model_name} v{version}")
        return model_config.id
    
    def get_model_config(self, model_name: str, version: str = None) -> Optional[Dict[str, Any]]:
        """HMM 모델 설정 조회"""
        query = self.session.query(HmmModelConfig).filter(
            HmmModelConfig.model_name == model_name
        )
        
        if version:
            query = query.filter(HmmModelConfig.model_version == version)
        else:
            query = query.filter(HmmModelConfig.is_active == True)
        
        model_config = query.order_by(desc(HmmModelConfig.created_at)).first()
        
        if not model_config:
            return None
        
        import json
        
        return {
            'model_name': model_config.model_name,
            'model_version': model_config.model_version,
            'states': json.loads(model_config.states),
            'transition_matrix': json.loads(model_config.transition_matrix),
            'emission_matrix': json.loads(model_config.emission_matrix),
            'initial_probabilities': json.loads(model_config.initial_probabilities),
            'parameters': json.loads(model_config.model_parameters or '{}'),
            'training_accuracy': model_config.training_accuracy,
            'validation_accuracy': model_config.validation_accuracy,
            'created_at': model_config.created_at
        }