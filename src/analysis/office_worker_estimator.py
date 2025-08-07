"""
사무직 근무시간 추정 특화 모듈
태그 데이터가 적은 사무직의 특성을 고려한 확률적 추정
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class OfficeWorkerEstimator:
    """사무직 근무시간 확률적 추정"""
    
    def __init__(self):
        # 사무직 근무 패턴 가정
        self.OFFICE_PATTERNS = {
            'standard_start': 9,     # 표준 출근 시간 (9시)
            'standard_end': 18,       # 표준 퇴근 시간 (18시)
            'lunch_start': 12,        # 점심 시작
            'lunch_end': 13,          # 점심 종료
            'min_work_hours': 4,      # 최소 근무시간
            'max_work_hours': 12,     # 최대 근무시간
            'standard_work_hours': 8  # 표준 근무시간
        }
        
        # 꼬리물기 패턴 감지 임계값 (사무직 특성 고려하여 대폭 완화)
        self.TAILGATING_THRESHOLDS = {
            'entry_to_activity': 240,    # 입문 후 첫 활동까지 시간 (4시간으로 완화)
            'last_activity_to_exit': 240, # 마지막 활동 후 퇴문까지 시간 (4시간으로 완화)
            'min_activities': 1,          # 최소 활동 수 (1개로 완화)
            'lunch_gap': 90               # 점심시간 최대 간격 (분)
        }
    
    def estimate_office_work_time(self, daily_data: pd.DataFrame, 
                                  employee_info: Dict = None) -> Dict:
        """
        사무직 근무시간 확률적 추정
        
        Returns:
            추정 결과 딕셔너리
        """
        result = {
            'estimated_hours': 0.0,
            'confidence': 0.0,
            'tailgating_probability': 0.0,
            'estimation_method': 'unknown',
            'work_segments': [],
            'suspicious_periods': []
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
        
        # 1. 출입 태그 찾기
        entry_exit = self.find_entry_exit_tags(daily_data, time_col)
        
        # 2. 실제 활동 찾기 (회의, 결재, 시스템 사용)
        real_activities = self.find_real_activities(daily_data, time_col)
        
        # 3. 꼬리물기 패턴 감지
        tailgating_prob = self.detect_tailgating_pattern(
            entry_exit, real_activities, daily_data, time_col
        )
        result['tailgating_probability'] = tailgating_prob
        
        # 4. 근무시간 추정
        if tailgating_prob > 0.7:
            # 꼬리물기 의심: 최소 근무시간만 인정
            result['estimated_hours'] = self.estimate_minimal_work(real_activities, time_col)
            result['confidence'] = 30.0
            result['estimation_method'] = 'tailgating_suspected'
            result['suspicious_periods'] = self.identify_suspicious_periods(
                entry_exit, real_activities, time_col
            )
        elif len(real_activities) < 3:
            # 활동이 너무 적음: 확률적 추정
            result['estimated_hours'] = self.probabilistic_estimation(
                entry_exit, real_activities, time_col
            )
            result['confidence'] = 50.0
            result['estimation_method'] = 'probabilistic'
        else:
            # 정상적인 활동: 활동 기반 추정
            result['estimated_hours'] = self.activity_based_estimation(
                entry_exit, real_activities, time_col
            )
            result['confidence'] = 70.0
            result['estimation_method'] = 'activity_based'
        
        # 5. 근무 구간 식별
        result['work_segments'] = self.identify_work_segments(
            entry_exit, real_activities, time_col
        )
        
        return result
    
    def find_entry_exit_tags(self, data: pd.DataFrame, time_col: str) -> Dict:
        """출입 태그 찾기"""
        entry_exit = {
            'first_entry': None,
            'last_exit': None,
            'entries': [],
            'exits': []
        }
        
        # T2 태그 (입문)
        if 'Tag_Code' in data.columns:
            entry_tags = data[data['Tag_Code'] == 'T2']
            if not entry_tags.empty:
                entry_exit['first_entry'] = entry_tags.iloc[0][time_col]
                entry_exit['entries'] = entry_tags[time_col].tolist()
        
        # T1 태그 (퇴문) 또는 COMMUTE_OUT
        if 'Tag_Code' in data.columns:
            exit_tags = data[data['Tag_Code'] == 'T1']
            if not exit_tags.empty:
                entry_exit['last_exit'] = exit_tags.iloc[-1][time_col]
                entry_exit['exits'] = exit_tags[time_col].tolist()
        
        if 'activity_code' in data.columns:
            commute_out = data[data['activity_code'] == 'COMMUTE_OUT']
            if not commute_out.empty and entry_exit['last_exit'] is None:
                entry_exit['last_exit'] = commute_out.iloc[-1][time_col]
        
        return entry_exit
    
    def find_real_activities(self, data: pd.DataFrame, time_col: str) -> pd.DataFrame:
        """실제 업무 활동 찾기"""
        activities = pd.DataFrame()
        
        # Knox 데이터 (회의, 결재)
        if 'source' in data.columns:
            knox_data = data[data['source'].isin(['Knox_Approval', 'Knox_Mail'])]
            activities = pd.concat([activities, knox_data])
        
        # G3 태그 (회의)
        if 'Tag_Code' in data.columns:
            meeting_data = data[data['Tag_Code'] == 'G3']
            activities = pd.concat([activities, meeting_data])
        
        # 시스템 사용 로그
        if 'source' in data.columns:
            system_data = data[data['source'].isin(['EAM', 'LAMS', 'MES'])]
            activities = pd.concat([activities, system_data])
        
        # 중복 제거 및 시간순 정렬
        if not activities.empty:
            activities = activities.drop_duplicates().sort_values(time_col)
        
        return activities
    
    def detect_tailgating_pattern(self, entry_exit: Dict, activities: pd.DataFrame,
                                  data: pd.DataFrame, time_col: str) -> float:
        """꼬리물기 패턴 감지"""
        probability = 0.0
        factors = []
        
        # 1. 입문 후 첫 활동까지 시간
        if entry_exit['first_entry'] and not activities.empty:
            first_activity = activities.iloc[0][time_col]
            gap_minutes = (first_activity - entry_exit['first_entry']).total_seconds() / 60
            
            if gap_minutes > self.TAILGATING_THRESHOLDS['entry_to_activity']:
                factors.append(('long_entry_gap', 0.3))
                logger.warning(f"입문 후 {gap_minutes:.0f}분간 활동 없음 - 꼬리물기 의심")
        
        # 2. 마지막 활동 후 퇴문까지 시간
        if entry_exit['last_exit'] and not activities.empty:
            last_activity = activities.iloc[-1][time_col]
            gap_minutes = (entry_exit['last_exit'] - last_activity).total_seconds() / 60
            
            if gap_minutes > self.TAILGATING_THRESHOLDS['last_activity_to_exit']:
                factors.append(('long_exit_gap', 0.3))
                logger.warning(f"마지막 활동 후 {gap_minutes:.0f}분간 활동 없음 - 꼬리물기 의심")
        
        # 3. 전체 활동 수
        if len(activities) < self.TAILGATING_THRESHOLDS['min_activities']:
            factors.append(('few_activities', 0.2))
            logger.warning(f"활동 수 {len(activities)}개 - 너무 적음")
        
        # 4. 점심시간 패턴
        if not activities.empty and len(activities) > 1:
            # 11:30 ~ 13:30 사이 활동 확인
            lunch_start = activities.iloc[0][time_col].replace(hour=11, minute=30)
            lunch_end = activities.iloc[0][time_col].replace(hour=13, minute=30)
            
            lunch_activities = activities[
                (activities[time_col] >= lunch_start) & 
                (activities[time_col] <= lunch_end)
            ]
            
            if lunch_activities.empty:
                # 점심시간에 활동이 없으면 정상
                pass
            else:
                # 점심시간에 활동이 있으면 의심
                factors.append(('lunch_activity', 0.2))
        
        # 확률 계산
        for factor, weight in factors:
            probability += weight
        
        return min(probability, 1.0)
    
    def estimate_minimal_work(self, activities: pd.DataFrame, time_col: str) -> float:
        """최소 근무시간 추정 (꼬리물기 의심 시)"""
        if activities.empty:
            return 0.0
        
        # 실제 활동 시간만 계산
        work_minutes = 0
        
        for i in range(len(activities)):
            # 각 활동당 30분 인정
            work_minutes += 30
        
        return work_minutes / 60
    
    def probabilistic_estimation(self, entry_exit: Dict, activities: pd.DataFrame,
                                time_col: str) -> float:
        """확률적 근무시간 추정"""
        # 기본값: 표준 근무시간의 90% (사무직 표준 근무 가정)
        base_hours = self.OFFICE_PATTERNS['standard_work_hours'] * 0.90
        
        # 조정 요인
        adjustments = 0.0
        
        # 출입 시간 기반 조정
        if entry_exit['first_entry'] and entry_exit['last_exit']:
            total_hours = (entry_exit['last_exit'] - entry_exit['first_entry']).total_seconds() / 3600
            
            # 전체 체류시간이 표준 근무시간과 유사하면 신뢰도 증가
            if 7 <= total_hours <= 10:
                adjustments += 1.0
            elif total_hours < 4:
                adjustments -= 2.0
            elif total_hours > 12:
                adjustments -= 1.0
        
        # 활동 수 기반 조정
        activity_count = len(activities)
        if activity_count >= 5:
            adjustments += 1.0
        elif activity_count >= 3:
            adjustments += 0.5
        elif activity_count == 0:
            adjustments -= 3.0
        
        # 최종 추정
        estimated = base_hours + adjustments
        return max(self.OFFICE_PATTERNS['min_work_hours'], 
                  min(self.OFFICE_PATTERNS['max_work_hours'], estimated))
    
    def activity_based_estimation(self, entry_exit: Dict, activities: pd.DataFrame,
                                 time_col: str) -> float:
        """활동 기반 근무시간 추정"""
        if activities.empty:
            return 0.0
        
        # 첫 활동부터 마지막 활동까지
        first_activity = activities.iloc[0][time_col]
        last_activity = activities.iloc[-1][time_col]
        
        # 기본 근무시간
        work_hours = (last_activity - first_activity).total_seconds() / 3600
        
        # 점심시간 제외
        lunch_start = first_activity.replace(hour=12, minute=0)
        lunch_end = first_activity.replace(hour=13, minute=0)
        
        if first_activity <= lunch_start and last_activity >= lunch_end:
            work_hours -= 1.0  # 점심시간 1시간 제외
        
        # 긴 공백 시간 제외
        for i in range(len(activities) - 1):
            gap = (activities.iloc[i+1][time_col] - activities.iloc[i][time_col]).total_seconds() / 60
            if gap > 60:  # 1시간 이상 공백
                work_hours -= (gap - 30) / 60  # 30분 초과분 제외
        
        return max(0, min(self.OFFICE_PATTERNS['max_work_hours'], work_hours))
    
    def identify_suspicious_periods(self, entry_exit: Dict, activities: pd.DataFrame,
                                   time_col: str) -> List[Dict]:
        """의심스러운 구간 식별"""
        suspicious = []
        
        # 입문 후 활동 없는 구간
        if entry_exit['first_entry'] and not activities.empty:
            first_activity = activities.iloc[0][time_col]
            gap = (first_activity - entry_exit['first_entry']).total_seconds() / 60
            
            if gap > 60:
                suspicious.append({
                    'type': 'entry_gap',
                    'start': entry_exit['first_entry'],
                    'end': first_activity,
                    'duration_minutes': gap,
                    'description': f"입문 후 {gap:.0f}분간 활동 없음"
                })
        
        # 마지막 활동 후 퇴문까지
        if entry_exit['last_exit'] and not activities.empty:
            last_activity = activities.iloc[-1][time_col]
            gap = (entry_exit['last_exit'] - last_activity).total_seconds() / 60
            
            if gap > 60:
                suspicious.append({
                    'type': 'exit_gap',
                    'start': last_activity,
                    'end': entry_exit['last_exit'],
                    'duration_minutes': gap,
                    'description': f"마지막 활동 후 {gap:.0f}분간 활동 없음"
                })
        
        return suspicious
    
    def identify_work_segments(self, entry_exit: Dict, activities: pd.DataFrame,
                              time_col: str) -> List[Dict]:
        """근무 구간 식별"""
        segments = []
        
        if activities.empty:
            return segments
        
        current_segment = None
        
        for i, row in activities.iterrows():
            if current_segment is None:
                # 새 구간 시작
                current_segment = {
                    'start': row[time_col],
                    'end': row[time_col],
                    'activities': 1
                }
            else:
                # 이전 활동과의 간격 확인
                gap = (row[time_col] - current_segment['end']).total_seconds() / 60
                
                if gap > 60:  # 1시간 이상 간격이면 새 구간
                    segments.append(current_segment)
                    current_segment = {
                        'start': row[time_col],
                        'end': row[time_col],
                        'activities': 1
                    }
                else:
                    # 같은 구간 계속
                    current_segment['end'] = row[time_col]
                    current_segment['activities'] += 1
        
        # 마지막 구간 추가
        if current_segment:
            segments.append(current_segment)
        
        # 구간별 근무시간 계산
        for segment in segments:
            duration = (segment['end'] - segment['start']).total_seconds() / 3600
            segment['duration_hours'] = duration
        
        return segments