"""
근무시간 추정률 및 신뢰도 계산 모듈
태그 데이터의 밀도와 패턴에 따른 추정 신뢰도 계산
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple, Optional
import logging
from .office_worker_estimator import OfficeWorkerEstimator

logger = logging.getLogger(__name__)


class WorkTimeEstimator:
    """근무시간 추정 및 신뢰도 계산"""
    
    def __init__(self):
        # 직군별 기본 추정률 (생산직 vs 사무직)
        self.BASE_ESTIMATION_RATES = {
            'production': 0.85,  # 생산직: 태그 데이터 풍부
            'office': 0.65,      # 사무직: 태그 데이터 제한적
            'unknown': 0.70      # 미분류
        }
        
        # 데이터 품질 지표
        self.DATA_QUALITY_WEIGHTS = {
            'tag_coverage': 0.3,      # 태그 커버리지 (빈도)
            'activity_density': 0.3,   # 활동 밀도 (O태그, Knox)
            'time_continuity': 0.2,    # 시간 연속성
            'location_diversity': 0.2   # 위치 다양성
        }
        
        # 사무직 특화 추정기
        self.office_estimator = OfficeWorkerEstimator()
    
    def calculate_estimation_metrics(self, daily_data: pd.DataFrame, 
                                    employee_info: Dict = None) -> Dict:
        """
        근무시간 추정 지표 계산
        
        Returns:
            추정 지표 딕셔너리
        """
        metrics = {
            'estimation_rate': 0.0,      # 추정률 (0-100%)
            'confidence_interval': (0, 0), # 신뢰구간
            'variance': 0.0,              # 분산
            'data_quality_score': 0.0,    # 데이터 품질 점수
            'estimation_type': 'unknown', # 추정 유형
            'quality_breakdown': {},       # 품질 세부 항목
            'office_estimation': None      # 사무직 특화 추정 결과
        }
        
        if daily_data.empty:
            return metrics
        
        # 1. 직군 판별
        job_type = self.identify_job_type(daily_data, employee_info)
        metrics['estimation_type'] = job_type
        
        # 2. 사무직인 경우 특화 추정 사용
        if job_type == 'office':
            office_result = self.office_estimator.estimate_office_work_time(
                daily_data, employee_info
            )
            metrics['office_estimation'] = office_result
            
            # 꼬리물기 확률이 높으면 낮은 신뢰도
            if office_result['tailgating_probability'] > 0.7:
                metrics['estimation_rate'] = 30.0
                metrics['confidence_interval'] = (20, 40)
                metrics['variance'] = 0.08
                metrics['data_quality_score'] = 0.3
                
                # 품질 세부 항목
                metrics['quality_breakdown'] = {
                    'tag_coverage': 0.2,
                    'activity_density': 0.2,
                    'time_continuity': 0.3,
                    'location_diversity': 0.4,
                    'tailgating_warning': True
                }
                
                logger.warning(f"사무직 꼬리물기 의심: 확률 {office_result['tailgating_probability']:.1%}")
                return metrics
        
        # 2. 데이터 품질 평가
        quality_scores = self.assess_data_quality(daily_data)
        metrics['quality_breakdown'] = quality_scores
        
        # 3. 종합 데이터 품질 점수 계산
        total_quality = sum(
            score * self.DATA_QUALITY_WEIGHTS.get(key, 0)
            for key, score in quality_scores.items()
        )
        metrics['data_quality_score'] = total_quality
        
        # 4. 추정률 계산
        base_rate = self.BASE_ESTIMATION_RATES[job_type]
        adjusted_rate = self.adjust_estimation_rate(base_rate, total_quality)
        metrics['estimation_rate'] = adjusted_rate * 100  # 백분율로 변환
        
        # 5. 분산 및 신뢰구간 계산
        variance = self.calculate_variance(daily_data, job_type)
        metrics['variance'] = variance
        
        # 신뢰구간 계산 (95% 신뢰수준)
        std_dev = np.sqrt(variance)
        confidence_margin = 1.96 * std_dev  # 95% 신뢰구간
        
        metrics['confidence_interval'] = (
            max(0, adjusted_rate - confidence_margin) * 100,
            min(100, adjusted_rate + confidence_margin) * 100
        )
        
        return metrics
    
    def identify_job_type(self, daily_data: pd.DataFrame, 
                          employee_info: Dict = None) -> str:
        """
        직군 판별 (생산직/사무직)
        
        Returns:
            'production', 'office', 또는 'unknown'
        """
        # 직원 정보에서 직군 확인
        if employee_info:
            # 부서명이나 직군으로 판별
            dept = str(employee_info.get('부서', '')).lower()
            position = str(employee_info.get('직급', '')).lower()
            job_type = str(employee_info.get('직군', '')).lower()
            
            # 사무직 키워드
            office_keywords = ['사무', '관리', '경영', '인사', '재무', '영업', '마케팅', 
                             '기획', '지원', '총무', '경리', 'it', '전산', '연구', '개발']
            # 생산직 키워드
            production_keywords = ['생산', '제조', '현장', '기술', '품질', '공정', '조립', 
                                  '포장', '물류', '창고', '운송']
            
            # 키워드 매칭
            for keyword in office_keywords:
                if keyword in dept or keyword in position or keyword in job_type:
                    logger.info(f"사무직 판별: {dept} / {position} / {job_type}")
                    return 'office'
            
            for keyword in production_keywords:
                if keyword in dept or keyword in position or keyword in job_type:
                    logger.info(f"생산직 판별: {dept} / {position} / {job_type}")
                    return 'production'
        
        # 태그 패턴으로 추정 (사무직은 태그가 적음을 고려)
        total_records = len(daily_data)
        
        if total_records == 0:
            return 'unknown'
        
        # 시간당 태그 수 계산
        time_col = 'timestamp' if 'timestamp' in daily_data.columns else 'datetime'
        if time_col in daily_data.columns:
            if daily_data[time_col].dtype == 'object' or daily_data[time_col].dtype == 'str':
                daily_data[time_col] = pd.to_datetime(daily_data[time_col])
            
            time_range = (daily_data[time_col].max() - daily_data[time_col].min()).total_seconds() / 3600
            tags_per_hour = total_records / time_range if time_range > 0 else 0
            
            # 사무직: 시간당 태그 5개 미만 (드문 태그)
            if tags_per_hour < 5:
                logger.info(f"사무직 추정: 시간당 태그 {tags_per_hour:.1f}개")
                return 'office'
            # 생산직: 시간당 태그 10개 이상 (빈번한 태그)
            elif tags_per_hour > 10:
                logger.info(f"생산직 추정: 시간당 태그 {tags_per_hour:.1f}개")
                return 'production'
        
        return 'unknown'
    
    def assess_data_quality(self, daily_data: pd.DataFrame) -> Dict[str, float]:
        """
        데이터 품질 평가
        
        Returns:
            품질 점수 딕셔너리 (각 항목 0-1 점수)
        """
        scores = {}
        
        # timestamp 또는 datetime 컬럼 확인
        time_col = 'timestamp' if 'timestamp' in daily_data.columns else 'datetime'
        
        # 1. 태그 커버리지 (시간당 태그 수)
        if len(daily_data) > 0 and time_col in daily_data.columns:
            # datetime 컬럼을 pd.Timestamp로 변환
            if daily_data[time_col].dtype == 'object' or daily_data[time_col].dtype == 'str':
                daily_data[time_col] = pd.to_datetime(daily_data[time_col])
            
            time_range = (daily_data[time_col].max() - daily_data[time_col].min()).total_seconds() / 3600
            if time_range > 0:
                tags_per_hour = len(daily_data) / time_range
                # 시간당 10개 이상이면 100%, 2개 이하면 20%
                scores['tag_coverage'] = min(1.0, max(0.2, tags_per_hour / 10))
            else:
                scores['tag_coverage'] = 0.2
        else:
            scores['tag_coverage'] = 0.0
        
        # 2. 활동 밀도 (O태그, Knox 데이터 비율)
        activity_count = 0
        if 'INOUT_GB' in daily_data.columns:
            activity_count += (daily_data['INOUT_GB'] == 'O').sum()
        if 'source' in daily_data.columns:
            activity_count += daily_data['source'].isin(['Knox_Approval', 'Knox_Mail', 'EAM', 'LAMS', 'MES']).sum()
        
        activity_ratio = activity_count / len(daily_data) if len(daily_data) > 0 else 0
        scores['activity_density'] = min(1.0, activity_ratio * 3)  # 33% 이상이면 100%
        
        # 3. 시간 연속성 (태그 간 시간 간격)
        if len(daily_data) > 1 and time_col in daily_data.columns:
            time_gaps = daily_data[time_col].diff().dropna()
            if len(time_gaps) > 0:
                median_gap = time_gaps.median().total_seconds() / 60  # 분 단위
                
                # 중간 간격이 10분 이하면 100%, 60분 이상이면 20%
                if median_gap <= 10:
                    scores['time_continuity'] = 1.0
                elif median_gap >= 60:
                    scores['time_continuity'] = 0.2
                else:
                    scores['time_continuity'] = 1.0 - (median_gap - 10) / 50 * 0.8
            else:
                scores['time_continuity'] = 0.2
        else:
            scores['time_continuity'] = 0.2
        
        # 4. 위치 다양성 (다양한 위치에서 태그)
        if 'DR_NM' in daily_data.columns:
            unique_locations = daily_data['DR_NM'].nunique()
            # 10개 이상 위치면 100%, 2개 이하면 30%
            scores['location_diversity'] = min(1.0, max(0.3, unique_locations / 10))
        else:
            scores['location_diversity'] = 0.3
        
        return scores
    
    def adjust_estimation_rate(self, base_rate: float, quality_score: float) -> float:
        """
        데이터 품질에 따른 추정률 조정
        
        Args:
            base_rate: 기본 추정률 (직군별)
            quality_score: 데이터 품질 점수 (0-1)
            
        Returns:
            조정된 추정률 (0-1)
        """
        # 품질이 좋으면 추정률 상승, 나쁘면 하락
        # 품질 0.5를 기준으로 ±20% 조정
        adjustment_factor = 1 + (quality_score - 0.5) * 0.4
        adjusted_rate = base_rate * adjustment_factor
        
        # 0-1 범위로 제한
        return max(0.3, min(0.95, adjusted_rate))
    
    def calculate_variance(self, daily_data: pd.DataFrame, job_type: str) -> float:
        """
        추정 분산 계산
        
        Returns:
            분산 값
        """
        base_variance = {
            'production': 0.01,  # 생산직: 낮은 분산
            'office': 0.04,      # 사무직: 높은 분산
            'unknown': 0.025     # 미분류: 중간 분산
        }
        
        variance = base_variance[job_type]
        
        # 데이터가 적으면 분산 증가
        if len(daily_data) < 50:
            variance *= 2.0
        elif len(daily_data) < 100:
            variance *= 1.5
        
        # timestamp 또는 datetime 컬럼 확인
        time_col = 'timestamp' if 'timestamp' in daily_data.columns else 'datetime'
        
        # 시간 간격이 불규칙하면 분산 증가
        if len(daily_data) > 1 and time_col in daily_data.columns:
            # datetime 컬럼을 pd.Timestamp로 변환
            if daily_data[time_col].dtype == 'object' or daily_data[time_col].dtype == 'str':
                daily_data[time_col] = pd.to_datetime(daily_data[time_col])
                
            time_gaps = daily_data[time_col].diff().dropna()
            if len(time_gaps) > 0:
                gap_std = time_gaps.std().total_seconds() / 60  # 분 단위
                
                if gap_std > 30:  # 표준편차 30분 이상
                    variance *= 1.5
        
        return variance
    
    def create_estimation_summary(self, metrics: Dict, 
                                 actual_work_hours: float = None) -> Dict:
        """
        추정 요약 정보 생성
        
        Returns:
            UI 표시용 요약 정보
        """
        summary = {
            'title': self.get_estimation_title(metrics['estimation_rate']),
            'color': self.get_estimation_color(metrics['estimation_rate']),
            'description': self.get_estimation_description(metrics),
            'recommendations': self.get_recommendations(metrics)
        }
        
        # 실제 근무시간과 추정 정보 결합
        if actual_work_hours is not None:
            lower_bound = actual_work_hours * metrics['confidence_interval'][0] / 100
            upper_bound = actual_work_hours * metrics['confidence_interval'][1] / 100
            
            summary['estimated_hours'] = {
                'point_estimate': actual_work_hours,
                'lower_bound': lower_bound,
                'upper_bound': upper_bound,
                'display': f"{actual_work_hours:.1f}시간 (±{(upper_bound-lower_bound)/2:.1f}시간)"
            }
        
        return summary
    
    def get_estimation_title(self, rate: float) -> str:
        """추정률에 따른 타이틀"""
        if rate >= 90:
            return "매우 높은 신뢰도"
        elif rate >= 80:
            return "높은 신뢰도"
        elif rate >= 70:
            return "보통 신뢰도"
        elif rate >= 60:
            return "낮은 신뢰도"
        else:
            return "매우 낮은 신뢰도"
    
    def get_estimation_color(self, rate: float) -> str:
        """추정률에 따른 색상"""
        if rate >= 90:
            return "#2E7D32"  # 진한 초록
        elif rate >= 80:
            return "#43A047"  # 초록
        elif rate >= 70:
            return "#FFA726"  # 주황
        elif rate >= 60:
            return "#EF5350"  # 빨강
        else:
            return "#B71C1C"  # 진한 빨강
    
    def get_estimation_description(self, metrics: Dict) -> str:
        """추정 설명 생성"""
        rate = metrics['estimation_rate']
        quality = metrics['data_quality_score']
        job_type = metrics['estimation_type']
        
        job_type_kr = {
            'production': '생산직',
            'office': '사무직', 
            'unknown': '미분류'
        }[job_type]
        
        return (
            f"{job_type_kr} 근무자로 추정되며, "
            f"데이터 품질 점수는 {quality*100:.1f}%입니다. "
            f"추정률 {rate:.1f}%로 근무시간을 산출했습니다."
        )
    
    def get_recommendations(self, metrics: Dict) -> List[str]:
        """개선 권장사항 생성"""
        recommendations = []
        breakdown = metrics.get('quality_breakdown', {})
        
        if breakdown.get('tag_coverage', 1) < 0.5:
            recommendations.append("📍 태그 리더기 추가 설치로 데이터 수집 개선 필요")
        
        if breakdown.get('activity_density', 1) < 0.5:
            recommendations.append("💻 시스템 사용 로그 연동 확대 필요")
        
        if breakdown.get('time_continuity', 1) < 0.5:
            recommendations.append("⏰ 태그 인식 간격이 너무 깁니다")
        
        if breakdown.get('location_diversity', 1) < 0.5:
            recommendations.append("🗺️ 이동 경로 태그 포인트 보강 필요")
        
        if not recommendations:
            recommendations.append("✅ 데이터 품질이 양호합니다")
        
        return recommendations