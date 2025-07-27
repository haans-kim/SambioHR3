"""
태그 기반 상태 분류 엔진
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, time, timedelta
import pandas as pd
import numpy as np
from enum import Enum

logger = logging.getLogger(__name__)

class ActivityState(Enum):
    """활동 상태 정의"""
    WORK = "업무"
    WORK_CONFIRMED = "업무(확실)"  # O 태그로 확정된 업무
    PREPARATION = "준비"
    MEETING = "회의"
    EDUCATION = "교육"
    REST = "휴게"
    MEAL = "식사"
    TRANSIT = "경유"
    ENTRY = "출입(IN)"
    EXIT = "출입(OUT)"
    NON_WORK = "비업무"

class TagStateClassifier:
    """태그 기반 상태 분류 엔진"""
    
    def __init__(self):
        # 시간대 정의
        self.meal_windows = {
            'breakfast': (time(6, 30), time(9, 0)),
            'lunch': (time(11, 20), time(13, 20)),
            'dinner': (time(17, 0), time(20, 0)),
            'midnight': [(time(23, 30), time(23, 59)), (time(0, 0), time(1, 0))]
        }
        
        # 교대 시간 정의
        self.shift_times = {
            'day': {'start': time(8, 0), 'end': time(20, 30)},
            'night': {'start': time(20, 0), 'end': time(8, 30)}
        }
        
        # 전환 규칙 정의
        self.transition_rules = self._initialize_transition_rules()
        
    def _initialize_transition_rules(self) -> Dict[Tuple[str, str], Dict]:
        """전환 규칙 초기화"""
        rules = {}
        
        # O 태그 관련 규칙 (가장 높은 우선순위)
        rules[('O', 'O')] = {'state': ActivityState.WORK_CONFIRMED, 'probability': 0.98}
        rules[('G1', 'O')] = {'state': ActivityState.WORK_CONFIRMED, 'probability': 0.98}
        rules[('O', 'G1')] = {'state': ActivityState.WORK, 'probability': 0.95}
        rules[('O', 'M1')] = {'state': ActivityState.MEAL, 'probability': 1.0}
        rules[('O', 'T2')] = {'state': ActivityState.EXIT, 'probability': 0.9}
        
        # M 태그 관련 규칙 (100% 확실)
        rules[('T1', 'M1')] = {'state': ActivityState.MEAL, 'probability': 1.0}
        rules[('T1', 'M2')] = {'state': ActivityState.TRANSIT, 'probability': 1.0}
        rules[('M1', 'T1')] = {'state': ActivityState.TRANSIT, 'probability': 1.0}
        rules[('M2', 'T1')] = {'state': ActivityState.TRANSIT, 'probability': 1.0}
        rules[('M2', 'N2')] = {'state': ActivityState.REST, 'probability': 0.8}
        
        # 출퇴근 패턴
        rules[('T2', 'G2')] = {'state': ActivityState.PREPARATION, 'probability': 0.9}
        rules[('T2', 'G1')] = {'state': ActivityState.WORK, 'probability': 0.8}
        rules[('G1', 'T3')] = {'state': ActivityState.EXIT, 'probability': 0.8}
        rules[('G2', 'T3')] = {'state': ActivityState.EXIT, 'probability': 0.9}
        
        # 회의/교육 패턴
        rules[('G1', 'G3')] = {'state': ActivityState.MEETING, 'probability': 0.9}
        rules[('G3', 'G3')] = {'state': ActivityState.MEETING, 'probability': 0.95}
        rules[('G1', 'G4')] = {'state': ActivityState.EDUCATION, 'probability': 0.9}
        rules[('G4', 'G4')] = {'state': ActivityState.EDUCATION, 'probability': 0.95}
        
        # 휴게 패턴
        rules[('G1', 'N1')] = {'state': ActivityState.REST, 'probability': 0.8}
        rules[('N1', 'N1')] = {'state': ActivityState.REST, 'probability': 0.9}
        rules[('G1', 'N2')] = {'state': ActivityState.REST, 'probability': 0.7}
        
        # 이동 패턴
        rules[('T1', 'T1')] = {'state': ActivityState.TRANSIT, 'probability': 0.7}
        rules[('G1', 'T1')] = {'state': ActivityState.TRANSIT, 'probability': 0.8}
        rules[('T1', 'G1')] = {'state': ActivityState.WORK, 'probability': 0.7}
        
        # 재입문 패턴 (점심 외출 등)
        rules[('T3', 'T2')] = {'state': ActivityState.ENTRY, 'probability': 0.9}
        
        return rules
    
    def classify_state(self, current_tag: str, previous_tag: Optional[str] = None,
                      timestamp: Optional[datetime] = None, 
                      duration_minutes: Optional[float] = None,
                      has_o_tag: bool = False) -> Tuple[str, float]:
        """단일 태그를 상태로 분류"""
        # O 태그가 있으면 업무 확정
        if has_o_tag or current_tag == 'O':
            return ActivityState.WORK_CONFIRMED.value, 0.98
        
        # 전환 규칙 확인
        if previous_tag:
            transition_key = (previous_tag, current_tag)
            if transition_key in self.transition_rules:
                rule = self.transition_rules[transition_key]
                state = rule['state'].value
                probability = rule['probability']
                
                # 시간대 조건 확인
                if timestamp:
                    probability = self._adjust_probability_by_time(
                        state, timestamp, probability
                    )
                
                return state, probability
        
        # 단일 태그 기반 분류
        state, probability = self._classify_single_tag(current_tag, timestamp, duration_minutes)
        
        return state, probability
    
    def _classify_single_tag(self, tag: str, timestamp: Optional[datetime] = None,
                           duration_minutes: Optional[float] = None) -> Tuple[str, float]:
        """단일 태그 기반 상태 분류"""
        # 태그별 기본 상태 매핑
        tag_state_map = {
            'G1': (ActivityState.WORK, 0.7),
            'G2': (ActivityState.PREPARATION, 0.8),
            'G3': (ActivityState.MEETING, 0.85),
            'G4': (ActivityState.EDUCATION, 0.85),
            'N1': (ActivityState.REST, 0.8),
            'N2': (ActivityState.REST, 0.7),
            'T1': (ActivityState.TRANSIT, 0.8),
            'T2': (ActivityState.ENTRY, 0.9),
            'T3': (ActivityState.EXIT, 0.9),
            'M1': (ActivityState.MEAL, 1.0),
            'M2': (ActivityState.TRANSIT, 0.9),
            'O': (ActivityState.WORK_CONFIRMED, 0.98)
        }
        
        if tag in tag_state_map:
            state, base_prob = tag_state_map[tag]
            
            # 시간 기반 조정
            if timestamp and state == ActivityState.WORK:
                base_prob = self._adjust_work_probability(timestamp, base_prob)
            
            # 지속 시간 기반 조정
            if duration_minutes:
                base_prob = self._adjust_probability_by_duration(
                    state, duration_minutes, base_prob
                )
            
            return state.value, base_prob
        
        # 알 수 없는 태그는 경유로 처리
        return ActivityState.TRANSIT.value, 0.5
    
    def _adjust_probability_by_time(self, state: str, timestamp: datetime, 
                                  base_probability: float) -> float:
        """시간대에 따른 확률 조정"""
        current_time = timestamp.time()
        
        # 식사 시간대 조정
        if state == ActivityState.MEAL.value:
            if self._is_in_meal_window(current_time):
                return min(base_probability * 1.2, 1.0)
            else:
                return base_probability * 0.5
        
        # 출퇴근 시간대 조정
        elif state in [ActivityState.ENTRY.value, ActivityState.EXIT.value]:
            if self._is_shift_change_time(current_time):
                return min(base_probability * 1.1, 1.0)
        
        # 심야 시간대 업무 확률 조정
        elif state == ActivityState.WORK.value:
            if time(1, 0) <= current_time <= time(6, 0):
                # 심야 시간대는 야간 근무자만 업무
                return base_probability * 0.8
        
        return base_probability
    
    def _adjust_work_probability(self, timestamp: datetime, base_prob: float) -> float:
        """업무 확률을 시간대에 따라 조정"""
        current_time = timestamp.time()
        
        # 주간 근무 시간
        if time(8, 0) <= current_time <= time(20, 0):
            return min(base_prob * 1.1, 0.9)
        # 야간 근무 시간
        elif time(20, 0) <= current_time or current_time <= time(8, 0):
            return base_prob
        
        return base_prob * 0.7
    
    def _adjust_probability_by_duration(self, state: ActivityState, 
                                      duration_minutes: float, 
                                      base_prob: float) -> float:
        """지속 시간에 따른 확률 조정"""
        if state == ActivityState.TRANSIT:
            if duration_minutes < 5:
                return min(base_prob * 1.2, 1.0)
            elif duration_minutes > 30:
                return base_prob * 0.5
        
        elif state == ActivityState.REST:
            if 10 <= duration_minutes <= 30:
                return min(base_prob * 1.1, 1.0)
            elif duration_minutes > 120:
                return base_prob * 0.8
        
        elif state == ActivityState.MEAL:
            if 20 <= duration_minutes <= 60:
                return min(base_prob * 1.1, 1.0)
            elif duration_minutes < 10 or duration_minutes > 90:
                return base_prob * 0.7
        
        elif state == ActivityState.WORK:
            if 30 <= duration_minutes <= 180:  # 30분 ~ 3시간
                return min(base_prob * 1.2, 0.85) # 확률을 85%까지 올림
            elif duration_minutes > 180: # 3시간 이상
                return min(base_prob * 1.1, 0.75) # 장시간은 신뢰도 약간 감소
            elif duration_minutes < 10: # 10분 미만
                return base_prob * 0.8 # 짧은 시간은 업무 아닐 가능성

        return base_prob
    
    def _is_in_meal_window(self, current_time: time) -> bool:
        """현재 시간이 식사 시간대인지 확인"""
        for meal, window in self.meal_windows.items():
            if meal == 'midnight':
                # 자정을 넘는 경우 처리
                for start, end in window:
                    if start <= current_time or current_time <= end:
                        return True
            else:
                start, end = window
                if start <= current_time <= end:
                    return True
        return False
    
    def _is_shift_change_time(self, current_time: time) -> bool:
        """교대 시간대인지 확인"""
        # 주간조 출퇴근 시간 (07:30-08:30, 20:00-21:00)
        if (time(7, 30) <= current_time <= time(8, 30) or
            time(20, 0) <= current_time <= time(21, 0)):
            return True
        
        # 야간조 출퇴근 시간 (19:30-20:30, 08:00-09:00)  
        if (time(19, 30) <= current_time <= time(20, 30) or
            time(8, 0) <= current_time <= time(9, 0)):
            return True
        
        return False
    
    def classify_sequence(self, tag_sequence: List[Dict]) -> List[Dict]:
        """태그 시퀀스를 상태 시퀀스로 분류"""
        classified_sequence = []
        
        for i, tag_data in enumerate(tag_sequence):
            # 이전 태그 정보
            previous_tag = None
            if i > 0:
                previous_tag = tag_sequence[i-1].get('tag_code')
            
            # 현재 태그 정보
            current_tag = tag_data.get('tag_code')
            timestamp = tag_data.get('timestamp')
            has_o_tag = tag_data.get('has_o_tag', False)
            
            # 지속 시간 계산
            duration_minutes = None
            if i > 0 and timestamp and tag_sequence[i-1].get('timestamp'):
                duration = timestamp - tag_sequence[i-1]['timestamp']
                duration_minutes = duration.total_seconds() / 60
            
            # 상태 분류
            state, confidence = self.classify_state(
                current_tag, previous_tag, timestamp, 
                duration_minutes, has_o_tag
            )
            
            # 결과 저장
            result = {
                'timestamp': timestamp,
                'tag_code': current_tag,
                'state': state,
                'confidence': confidence,
                'duration_minutes': duration_minutes,
                'has_o_tag': has_o_tag
            }
            
            classified_sequence.append(result)
        
        # 후처리: 이상 패턴 감지
        self._detect_anomalies(classified_sequence)
        
        return classified_sequence
    
    def _detect_anomalies(self, sequence: List[Dict]):
        """이상 패턴 감지 및 표시"""
        for i in range(len(sequence)):
            current = sequence[i]
            
            # 꼬리물기 패턴 감지
            if i > 0 and current['tag_code'] in ['T1', 'T2']:
                prev = sequence[i-1]
                if (prev['tag_code'] == current['tag_code'] and 
                    current.get('duration_minutes', 0) > 30):
                    current['anomaly'] = 'tailgating'
                    current['anomaly_confidence'] = 0.8
            
            # 장시간 비업무 패턴
            duration = current.get('duration_minutes', 0)
            if duration and duration > 120 and current['state'] == ActivityState.REST.value:
                current['anomaly'] = 'long_rest'
                current['anomaly_confidence'] = 0.7
            
            # O 태그 없는 장시간 업무
            if (duration and duration > 180 and 
                current['state'] == ActivityState.WORK.value and
                not current.get('has_o_tag')):
                current['anomaly'] = 'unconfirmed_work'
                current['anomaly_confidence'] = 0.6