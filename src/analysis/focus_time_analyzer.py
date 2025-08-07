"""
집중근무 시간대 분석 모듈
직군별 활동 집중도 패턴 분석
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class FocusTimeAnalyzer:
    """집중근무 시간대 분석"""
    
    def __init__(self):
        # 시간대 구분 (1시간 단위)
        self.TIME_SLOTS = list(range(24))  # 0시~23시
        
        # 직군별 표준 근무 패턴
        self.WORK_PATTERNS = {
            'production': {
                'standard_hours': [(7, 12), (13, 18)],  # 오전/오후 생산시간
                'peak_threshold': 0.7,  # 피크 판정 임계값
                'min_density': 10,  # 시간당 최소 활동 수
            },
            'office': {
                'standard_hours': [(9, 12), (14, 18)],  # 오전/오후 업무시간
                'peak_threshold': 0.6,  # 피크 판정 임계값 (낮게 설정)
                'min_density': 3,  # 시간당 최소 활동 수 (낮게 설정)
            },
            'shift': {
                'standard_hours': [(8, 20), (20, 8)],  # 주간/야간 교대
                'peak_threshold': 0.7,
                'min_density': 8,
            }
        }
        
        # 활동 유형별 가중치
        self.ACTIVITY_WEIGHTS = {
            'O': 1.0,  # 장비 조작
            'Knox_Approval': 0.8,  # 결재
            'Knox_Mail': 0.6,  # 메일
            'G3': 0.9,  # 회의
            'EAM': 0.7,  # 시스템 사용
            'LAMS': 0.7,
            'MES': 0.8,
            'T2': 0.1,  # 입문 (낮은 가중치)
            'T1': 0.1,  # 퇴문 (낮은 가중치)
        }
    
    def analyze_focus_time(self, daily_data: pd.DataFrame, 
                           employee_info: Dict = None) -> Dict:
        """
        집중근무 시간대 분석
        
        Returns:
            분석 결과 딕셔너리
        """
        result = {
            'peak_hours': [],  # 집중 시간대
            'focus_score': 0.0,  # 집중도 점수
            'hourly_density': {},  # 시간별 활동 밀도
            'work_pattern': 'unknown',  # 근무 패턴
            'concentration_periods': [],  # 연속 집중 구간
            'distraction_periods': [],  # 분산 구간
            'job_type': 'unknown'
        }
        
        if daily_data.empty:
            return result
        
        # 시간 컬럼 확인
        time_col = 'timestamp' if 'timestamp' in daily_data.columns else 'datetime'
        if time_col not in daily_data.columns:
            return result
        
        # datetime 변환
        if daily_data[time_col].dtype == 'object' or daily_data[time_col].dtype == 'str':
            daily_data[time_col] = pd.to_datetime(daily_data[time_col])
        
        # 1. 직군 판별
        job_type = self.identify_job_type(daily_data, employee_info)
        result['job_type'] = job_type
        
        # 2. 시간별 활동 밀도 계산
        hourly_density = self.calculate_hourly_density(daily_data, time_col)
        result['hourly_density'] = hourly_density
        
        # 3. 피크 시간대 식별
        peak_hours = self.identify_peak_hours(hourly_density, job_type)
        result['peak_hours'] = peak_hours
        
        # 4. 집중도 점수 계산
        focus_score = self.calculate_focus_score(hourly_density, peak_hours, job_type)
        result['focus_score'] = focus_score
        
        # 5. 연속 집중 구간 분석
        concentration_periods = self.find_concentration_periods(daily_data, time_col)
        result['concentration_periods'] = concentration_periods
        
        # 6. 분산 구간 분석
        distraction_periods = self.find_distraction_periods(daily_data, time_col)
        result['distraction_periods'] = distraction_periods
        
        # 7. 근무 패턴 분류
        work_pattern = self.classify_work_pattern(hourly_density, job_type)
        result['work_pattern'] = work_pattern
        
        return result
    
    def identify_job_type(self, daily_data: pd.DataFrame, 
                          employee_info: Dict = None) -> str:
        """직군 판별 (생산직/사무직/교대근무)"""
        if employee_info:
            dept = str(employee_info.get('부서', '')).lower()
            position = str(employee_info.get('직급', '')).lower()
            
            # 교대근무 키워드
            if any(word in dept or word in position for word in ['교대', '야간', 'shift']):
                return 'shift'
            
            # 사무직 키워드
            office_keywords = ['사무', '관리', '경영', '인사', '재무', '영업', 
                             '기획', '지원', '총무', 'it', '전산']
            if any(word in dept or word in position for word in office_keywords):
                return 'office'
            
            # 생산직 키워드
            production_keywords = ['생산', '제조', '현장', '기술', '품질', '공정']
            if any(word in dept or word in position for word in production_keywords):
                return 'production'
        
        # 태그 패턴으로 추정
        if 'Tag_Code' in daily_data.columns:
            o_tags = (daily_data['Tag_Code'] == 'O').sum()
            total = len(daily_data)
            
            if o_tags / total > 0.3:  # O태그가 30% 이상이면 생산직
                return 'production'
        
        return 'office'  # 기본값
    
    def calculate_hourly_density(self, daily_data: pd.DataFrame, 
                                 time_col: str) -> Dict[int, float]:
        """시간별 활동 밀도 계산"""
        hourly_density = {hour: 0.0 for hour in range(24)}
        
        for _, row in daily_data.iterrows():
            hour = row[time_col].hour
            
            # 활동 유형별 가중치 적용
            weight = 1.0
            if 'Tag_Code' in row and pd.notna(row['Tag_Code']):
                weight = self.ACTIVITY_WEIGHTS.get(row['Tag_Code'], 0.5)
            elif 'source' in row and pd.notna(row['source']):
                weight = self.ACTIVITY_WEIGHTS.get(row['source'], 0.5)
            
            hourly_density[hour] += weight
        
        # 정규화 (0-1 범위)
        max_density = max(hourly_density.values()) if hourly_density else 1
        if max_density > 0:
            hourly_density = {h: d/max_density for h, d in hourly_density.items()}
        
        return hourly_density
    
    def identify_peak_hours(self, hourly_density: Dict[int, float], 
                           job_type: str) -> List[int]:
        """피크 시간대 식별"""
        threshold = self.WORK_PATTERNS[job_type]['peak_threshold'] \
                   if job_type in self.WORK_PATTERNS else 0.6
        
        peak_hours = []
        for hour, density in hourly_density.items():
            if density >= threshold:
                peak_hours.append(hour)
        
        # 연속된 시간대로 그룹화
        if peak_hours:
            peak_hours.sort()
        
        return peak_hours
    
    def calculate_focus_score(self, hourly_density: Dict[int, float],
                             peak_hours: List[int], job_type: str) -> float:
        """집중도 점수 계산 (0-100)"""
        if not peak_hours:
            return 0.0
        
        # 1. 피크 시간대 집중도
        peak_density = sum(hourly_density[h] for h in peak_hours) / len(peak_hours)
        
        # 2. 비피크 시간대 분산도
        non_peak_hours = [h for h in range(24) if h not in peak_hours]
        if non_peak_hours:
            non_peak_density = sum(hourly_density[h] for h in non_peak_hours) / len(non_peak_hours)
        else:
            non_peak_density = 0
        
        # 3. 집중도 = 피크 밀도 - 비피크 밀도
        concentration = peak_density - non_peak_density
        
        # 4. 연속성 보너스
        continuity_bonus = self.calculate_continuity_bonus(peak_hours)
        
        # 최종 점수 (0-100)
        focus_score = (concentration * 70 + continuity_bonus * 30)
        
        return max(0, min(100, focus_score))
    
    def calculate_continuity_bonus(self, peak_hours: List[int]) -> float:
        """연속성 보너스 계산"""
        if len(peak_hours) <= 1:
            return 0.0
        
        # 연속된 시간대 그룹 찾기
        groups = []
        current_group = [peak_hours[0]]
        
        for i in range(1, len(peak_hours)):
            if peak_hours[i] == peak_hours[i-1] + 1:
                current_group.append(peak_hours[i])
            else:
                groups.append(current_group)
                current_group = [peak_hours[i]]
        groups.append(current_group)
        
        # 가장 긴 연속 구간
        max_continuous = max(len(g) for g in groups)
        
        # 보너스 계산 (4시간 이상 연속이면 만점)
        return min(1.0, max_continuous / 4)
    
    def find_concentration_periods(self, daily_data: pd.DataFrame, 
                                   time_col: str) -> List[Dict]:
        """연속 집중 구간 찾기"""
        periods = []
        
        if len(daily_data) < 2:
            return periods
        
        # 시간순 정렬
        daily_data = daily_data.sort_values(time_col)
        
        current_period = None
        prev_time = None
        
        for _, row in daily_data.iterrows():
            curr_time = row[time_col]
            
            # 활동 가중치 확인
            weight = 1.0
            if 'Tag_Code' in row and pd.notna(row['Tag_Code']):
                weight = self.ACTIVITY_WEIGHTS.get(row['Tag_Code'], 0.5)
            
            # 고가중치 활동만 집중으로 판정
            if weight >= 0.7:
                if prev_time and (curr_time - prev_time).total_seconds() <= 600:  # 10분 이내
                    if not current_period:
                        current_period = {
                            'start': prev_time,
                            'end': curr_time,
                            'activities': 2,
                            'intensity': weight
                        }
                    else:
                        current_period['end'] = curr_time
                        current_period['activities'] += 1
                        current_period['intensity'] = \
                            (current_period['intensity'] + weight) / 2
                else:
                    if current_period and current_period['activities'] >= 5:
                        periods.append(current_period)
                    current_period = None
            
            prev_time = curr_time
        
        # 마지막 구간 추가
        if current_period and current_period['activities'] >= 5:
            periods.append(current_period)
        
        # 구간별 지속시간 계산
        for period in periods:
            duration = (period['end'] - period['start']).total_seconds() / 3600
            period['duration_hours'] = duration
        
        return periods
    
    def find_distraction_periods(self, daily_data: pd.DataFrame, 
                                 time_col: str) -> List[Dict]:
        """분산 구간 찾기 (긴 공백 시간)"""
        periods = []
        
        if len(daily_data) < 2:
            return periods
        
        # 시간순 정렬
        daily_data = daily_data.sort_values(time_col)
        
        prev_time = daily_data.iloc[0][time_col]
        
        for i in range(1, len(daily_data)):
            curr_time = daily_data.iloc[i][time_col]
            gap_minutes = (curr_time - prev_time).total_seconds() / 60
            
            # 30분 이상 공백
            if gap_minutes >= 30:
                periods.append({
                    'start': prev_time,
                    'end': curr_time,
                    'gap_minutes': gap_minutes,
                    'type': self.classify_gap(gap_minutes)
                })
            
            prev_time = curr_time
        
        return periods
    
    def classify_gap(self, gap_minutes: float) -> str:
        """공백 시간 분류"""
        if gap_minutes >= 60 and gap_minutes <= 90:
            return 'lunch_break'  # 점심시간
        elif gap_minutes >= 15 and gap_minutes < 30:
            return 'short_break'  # 짧은 휴식
        elif gap_minutes >= 30 and gap_minutes < 60:
            return 'medium_break'  # 중간 휴식
        else:
            return 'long_absence'  # 긴 부재
    
    def classify_work_pattern(self, hourly_density: Dict[int, float], 
                             job_type: str) -> str:
        """근무 패턴 분류"""
        # 활동이 있는 시간대
        active_hours = [h for h, d in hourly_density.items() if d > 0.1]
        
        if not active_hours:
            return 'no_pattern'
        
        min_hour = min(active_hours)
        max_hour = max(active_hours)
        
        # 패턴 분류
        if min_hour >= 7 and max_hour <= 19:
            return 'regular_day'  # 정규 주간
        elif min_hour >= 19 or max_hour <= 7:
            return 'night_shift'  # 야간 근무
        elif max_hour - min_hour > 12:
            return 'extended_hours'  # 장시간 근무
        elif len(active_hours) < 4:
            return 'minimal_activity'  # 최소 활동
        else:
            return 'irregular'  # 불규칙
    
    def get_pattern_description(self, pattern: str) -> str:
        """패턴 설명"""
        descriptions = {
            'regular_day': '정규 주간 근무 (07:00-19:00)',
            'night_shift': '야간 교대 근무',
            'extended_hours': '장시간 근무 (12시간 이상)',
            'minimal_activity': '최소 활동 (4시간 미만)',
            'irregular': '불규칙한 근무 패턴',
            'no_pattern': '패턴 감지 불가'
        }
        return descriptions.get(pattern, '알 수 없음')
    
    def get_focus_level(self, score: float) -> str:
        """집중도 수준"""
        if score >= 80:
            return '매우 높음'
        elif score >= 60:
            return '높음'
        elif score >= 40:
            return '보통'
        elif score >= 20:
            return '낮음'
        else:
            return '매우 낮음'