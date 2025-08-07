"""
개선된 활동 분류기 - 활동 밀도 기반 실근무 추정
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple, Optional
import logging

from .activity_density_analyzer import ActivityDensityAnalyzer

logger = logging.getLogger(__name__)


class ImprovedActivityClassifier:
    """개선된 활동 분류기"""
    
    def __init__(self, db_manager=None):
        self.db_manager = db_manager
        self.density_analyzer = ActivityDensityAnalyzer()
        
        # 실근무 인정 기준
        self.WORK_RECOGNITION_RULES = {
            'min_confidence': 50,           # 최소 신뢰도
            'min_density': 0.5,             # 최소 활동 밀도 (시간당 0.5회)
            'max_idle_minutes': 60,         # 최대 무활동 시간 (60분)
            'meal_duration_minutes': 60,    # 식사 시간 (60분)
        }
    
    def classify_with_density(self, daily_data: pd.DataFrame, 
                             employee_id: str = None, 
                             selected_date: date = None) -> Tuple[pd.DataFrame, Dict]:
        """
        활동 밀도를 고려한 개선된 분류
        
        Returns:
            (분류된 데이터, 분석 결과 딕셔너리)
        """
        logger.info(f"개선된 분류 시작: {employee_id} / {selected_date}")
        
        # timestamp 컬럼 확인/생성
        if 'timestamp' not in daily_data.columns:
            if 'datetime' in daily_data.columns:
                daily_data['timestamp'] = pd.to_datetime(daily_data['datetime'])
            else:
                logger.error("timestamp 또는 datetime 컬럼이 없습니다")
                return daily_data, {}
        
        # 1단계: 활동 밀도 분석 적용
        analyzed_data, actual_work_mask = self.density_analyzer.apply_comprehensive_analysis(daily_data.copy())
        
        # 2단계: 실근무 시간 계산
        work_time_results = self.calculate_actual_work_time(analyzed_data, actual_work_mask)
        
        # 3단계: 비근무 구간 상세 분석
        non_work_analysis = self.analyze_non_work_periods(analyzed_data, actual_work_mask)
        
        # 4단계: 개선 효과 측정
        improvement_metrics = self.measure_improvement(daily_data, analyzed_data, actual_work_mask)
        
        # 결과 통합
        results = {
            'analyzed_data': analyzed_data,
            'actual_work_mask': actual_work_mask,
            'work_time': work_time_results,
            'non_work_analysis': non_work_analysis,
            'improvement_metrics': improvement_metrics,
            'employee_id': employee_id,
            'date': selected_date
        }
        
        # 로깅
        self.log_analysis_results(results)
        
        return analyzed_data, results
    
    def calculate_actual_work_time(self, data: pd.DataFrame, work_mask: pd.Series) -> Dict:
        """
        실제 근무 시간 계산
        
        Returns:
            근무 시간 분석 결과
        """
        results = {
            'total_records': len(data),
            'work_records': work_mask.sum(),
            'non_work_records': (~work_mask).sum()
        }
        
        # 시간 계산 (레코드 간격 기준)
        if len(data) > 1:
            # 각 레코드의 지속 시간 계산
            data['duration'] = data['timestamp'].diff().shift(-1).fillna(pd.Timedelta(minutes=5))
            
            # 실근무 시간
            work_duration = data.loc[work_mask, 'duration'].sum()
            results['actual_work_hours'] = work_duration.total_seconds() / 3600
            
            # 비근무 시간
            non_work_duration = data.loc[~work_mask, 'duration'].sum()
            results['non_work_hours'] = non_work_duration.total_seconds() / 3600
            
            # 전체 시간
            total_duration = data['duration'].sum()
            results['total_hours'] = total_duration.total_seconds() / 3600
            
            # 근무율
            if results['total_hours'] > 0:
                results['work_ratio'] = results['actual_work_hours'] / results['total_hours'] * 100
            else:
                results['work_ratio'] = 0
        else:
            results['actual_work_hours'] = 0
            results['non_work_hours'] = 0
            results['total_hours'] = 0
            results['work_ratio'] = 0
        
        return results
    
    def analyze_non_work_periods(self, data: pd.DataFrame, work_mask: pd.Series) -> Dict:
        """
        비근무 구간 상세 분석
        
        Returns:
            비근무 구간 분석 결과
        """
        non_work_data = data[~work_mask].copy()
        
        if non_work_data.empty:
            return {
                'total_non_work_periods': 0,
                'categories': {},
                'locations': {}
            }
        
        # 비근무 활동 유형별 집계
        activity_counts = non_work_data['activity_code'].value_counts().to_dict()
        
        # 비근무 위치별 집계
        if 'DR_NM' in non_work_data.columns:
            location_counts = non_work_data['DR_NM'].value_counts().head(10).to_dict()
        else:
            location_counts = {}
        
        # 연속된 비근무 구간 찾기
        non_work_periods = []
        current_period = None
        
        for i, row in data.iterrows():
            if not work_mask.loc[i]:  # 비근무
                if current_period is None:
                    current_period = {
                        'start': row['timestamp'],
                        'start_idx': i,
                        'activities': [row.get('activity_code', 'UNKNOWN')]
                    }
                else:
                    current_period['activities'].append(row.get('activity_code', 'UNKNOWN'))
            else:  # 근무
                if current_period is not None:
                    current_period['end'] = row['timestamp']
                    current_period['duration_minutes'] = (
                        current_period['end'] - current_period['start']
                    ).total_seconds() / 60
                    non_work_periods.append(current_period)
                    current_period = None
        
        # 마지막 구간 처리
        if current_period is not None:
            current_period['end'] = data.iloc[-1]['timestamp']
            current_period['duration_minutes'] = (
                current_period['end'] - current_period['start']
            ).total_seconds() / 60
            non_work_periods.append(current_period)
        
        # 긴 비근무 구간 (30분 이상)
        long_non_work_periods = [p for p in non_work_periods if p['duration_minutes'] >= 30]
        
        return {
            'total_non_work_periods': len(non_work_periods),
            'long_non_work_periods': len(long_non_work_periods),
            'categories': activity_counts,
            'locations': location_counts,
            'periods': long_non_work_periods[:5]  # 상위 5개만
        }
    
    def measure_improvement(self, original_data: pd.DataFrame, 
                           improved_data: pd.DataFrame, 
                           actual_work_mask: pd.Series) -> Dict:
        """
        개선 효과 측정
        
        Returns:
            개선 지표
        """
        # 원본 데이터의 근무 판정 (단순 방식)
        simple_work_mask = original_data['activity_code'].isin([
            'WORK', 'EQUIPMENT_OPERATION', 'G3_MEETING',
            'KNOX_APPROVAL', 'KNOX_MAIL', 'EAM_WORK', 'LAMS_WORK', 'MES_WORK'
        ])
        
        # 차이 계산
        removed_work = simple_work_mask & (~actual_work_mask)  # 제거된 근무
        added_work = (~simple_work_mask) & actual_work_mask    # 추가된 근무
        
        metrics = {
            'original_work_count': simple_work_mask.sum(),
            'improved_work_count': actual_work_mask.sum(),
            'removed_count': removed_work.sum(),
            'added_count': added_work.sum(),
            'net_change': actual_work_mask.sum() - simple_work_mask.sum()
        }
        
        # 시간 차이 계산
        if 'duration' in improved_data.columns:
            original_hours = improved_data.loc[simple_work_mask, 'duration'].sum().total_seconds() / 3600
            improved_hours = improved_data.loc[actual_work_mask, 'duration'].sum().total_seconds() / 3600
            
            metrics['original_work_hours'] = original_hours
            metrics['improved_work_hours'] = improved_hours
            metrics['hour_difference'] = improved_hours - original_hours
            metrics['hour_change_percent'] = (
                (improved_hours - original_hours) / original_hours * 100 
                if original_hours > 0 else 0
            )
        
        return metrics
    
    def log_analysis_results(self, results: Dict):
        """분석 결과 로깅"""
        logger.info("=" * 60)
        logger.info(f"📊 개선된 활동 분류 결과 - {results.get('employee_id')} / {results.get('date')}")
        logger.info("-" * 60)
        
        # 근무 시간 분석
        work_time = results.get('work_time', {})
        logger.info(f"⏱️ 근무 시간 분석:")
        logger.info(f"  - 실근무: {work_time.get('actual_work_hours', 0):.1f}시간")
        logger.info(f"  - 비근무: {work_time.get('non_work_hours', 0):.1f}시간")
        logger.info(f"  - 근무율: {work_time.get('work_ratio', 0):.1f}%")
        
        # 비근무 구간 분석
        non_work = results.get('non_work_analysis', {})
        logger.info(f"🔍 비근무 구간 분석:")
        logger.info(f"  - 총 비근무 구간: {non_work.get('total_non_work_periods', 0)}개")
        logger.info(f"  - 30분 이상 구간: {non_work.get('long_non_work_periods', 0)}개")
        
        # 개선 효과
        improvement = results.get('improvement_metrics', {})
        if improvement:
            logger.info(f"📈 개선 효과:")
            logger.info(f"  - 원본 근무시간: {improvement.get('original_work_hours', 0):.1f}시간")
            logger.info(f"  - 개선 근무시간: {improvement.get('improved_work_hours', 0):.1f}시간")
            logger.info(f"  - 차이: {improvement.get('hour_difference', 0):.1f}시간 "
                       f"({improvement.get('hour_change_percent', 0):.1f}%)")
        
        logger.info("=" * 60)
    
    def batch_analyze_organization(self, organization_data: pd.DataFrame, 
                                  analysis_date: date) -> pd.DataFrame:
        """
        조직 전체 배치 분석
        
        Args:
            organization_data: 조직 구성원 정보
            analysis_date: 분석 날짜
            
        Returns:
            분석 결과 DataFrame
        """
        results = []
        
        total_employees = len(organization_data)
        logger.info(f"조직 배치 분석 시작: {total_employees}명 / {analysis_date}")
        
        for idx, employee in organization_data.iterrows():
            employee_id = employee['사번']
            
            try:
                # 직원 일일 데이터 로드 (구현 필요)
                daily_data = self.load_employee_daily_data(employee_id, analysis_date)
                
                if daily_data is not None and not daily_data.empty:
                    # 개선된 분류 적용
                    _, analysis_results = self.classify_with_density(
                        daily_data, employee_id, analysis_date
                    )
                    
                    # 결과 저장
                    work_time = analysis_results.get('work_time', {})
                    improvement = analysis_results.get('improvement_metrics', {})
                    
                    results.append({
                        '사번': employee_id,
                        '성명': employee.get('성명'),
                        '부서': employee.get('부서'),
                        '센터': employee.get('센터'),
                        '팀': employee.get('팀'),
                        '분석일': analysis_date,
                        '실근무시간': work_time.get('actual_work_hours', 0),
                        '비근무시간': work_time.get('non_work_hours', 0),
                        '근무율': work_time.get('work_ratio', 0),
                        '개선전_근무시간': improvement.get('original_work_hours', 0),
                        '개선_차이': improvement.get('hour_difference', 0),
                        '상태': '성공'
                    })
                else:
                    results.append({
                        '사번': employee_id,
                        '성명': employee.get('성명'),
                        '부서': employee.get('부서'),
                        '상태': '데이터없음'
                    })
                    
            except Exception as e:
                logger.error(f"직원 {employee_id} 분석 실패: {e}")
                results.append({
                    '사번': employee_id,
                    '성명': employee.get('성명'),
                    '상태': f'실패: {str(e)[:50]}'
                })
            
            # 진행률 로깅
            if (idx + 1) % 10 == 0:
                logger.info(f"진행률: {idx + 1}/{total_employees} ({(idx + 1)/total_employees*100:.1f}%)")
        
        return pd.DataFrame(results)
    
    def load_employee_daily_data(self, employee_id: str, analysis_date: date) -> Optional[pd.DataFrame]:
        """직원 일일 데이터 로드 (구현 필요)"""
        # TODO: 실제 데이터 로드 로직 구현
        # pickle_manager 또는 DB에서 데이터 로드
        pass