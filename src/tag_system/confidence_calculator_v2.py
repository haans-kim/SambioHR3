"""
태그 기반 신뢰지수 계산 시스템 V2
실제 전이 확률 데이터를 기반으로 한 정교한 계산
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Tuple, List, Optional
import json
import os
import logging


class ConfidenceCalculatorV2:
    """태그 전이 확률 데이터 기반 신뢰지수 계산"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 전이 확률 데이터 로드
        data_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'data', 'tag_transition_probabilities.json'
        )
        
        try:
            with open(data_path, 'r', encoding='utf-8') as f:
                self.transition_data = json.load(f)
                self.logger.info(f"전이 확률 데이터 로드 완료: {data_path}")
        except Exception as e:
            self.logger.error(f"전이 확률 데이터 로드 실패: {e}")
            # 기본값 설정
            self.transition_data = self._get_default_data()
        
        # 태그 코드 매핑 (현재 시스템의 태그를 G/N/T 체계로 변환)
        self.tag_mapping = {
            # G1: 주업무 공간
            'WORK_AREA': 'G1',
            'OFFICE': 'G1',
            'LAB': 'G1',
            'PRODUCTION': 'G1',
            
            # G2: 준비 공간
            'PREPARATION': 'G2',
            'LOCKER': 'G2',
            
            # G3: 회의 공간
            'MEETING_ROOM': 'G3',
            'CONFERENCE': 'G3',
            
            # G4: 교육 공간
            'TRAINING': 'G4',
            'EDUCATION': 'G4',
            
            # N1: 식당
            'CAFETERIA': 'N1',
            'RESTAURANT': 'N1',
            
            # N2: 휴게 공간
            'REST_AREA': 'N2',
            'LOUNGE': 'N2',
            
            # N3: 개인 공간
            'RESTROOM': 'N3',
            'TOILET': 'N3',
            
            # T1: 이동 공간
            'CORRIDOR': 'T1',
            'HALLWAY': 'T1',
            'ELEVATOR': 'T1',
            
            # T2/T3: 출입
            'GATE_IN': 'T2',
            'GATE_OUT': 'T3'
        }
    
    def _get_default_data(self) -> Dict:
        """기본 전이 확률 데이터"""
        return {
            'transition_probabilities': {
                'G1→G1': {
                    'under_5min': {'work': 0.95, 'movement': 0.03, 'rest': 0.02},
                    '5_to_30min': {'work': 0.95, 'movement': 0.03, 'rest': 0.02},
                    '30min_to_2hr': {'work': 0.90, 'rest': 0.07, 'movement': 0.03},
                    'over_2hr': {'work': 0.85, 'rest': 0.10, 'non_work': 0.05}
                }
            },
            'time_intervals': {
                'under_5min': {'min': 0, 'max': 5},
                '5_to_30min': {'min': 5, 'max': 30},
                '30min_to_2hr': {'min': 30, 'max': 120},
                'over_2hr': {'min': 120, 'max': float('inf')}
            }
        }
    
    def _map_tag_to_category(self, tag_info: pd.Series) -> str:
        """현재 시스템의 태그를 G/N/T 카테고리로 매핑"""
        # DR_NM에서 키워드를 찾아 매핑
        dr_nm = str(tag_info.get('DR_NM', '')).upper()
        
        # 직접 매핑 시도
        for keyword, category in self.tag_mapping.items():
            if keyword in dr_nm:
                return category
        
        # work_area_type 기반 매핑
        area_type = tag_info.get('work_area_type', 'Y')
        if area_type == 'Y':
            return 'G1'  # 근무구역
        elif area_type == 'N':
            return 'N2'  # 비근무구역 (휴게)
        elif area_type == 'T':
            return 'T1'  # 이동구간
        
        # tag_code 기반 매핑
        tag_code = tag_info.get('tag_code', '')
        if tag_code == 'T2':
            return 'T2'
        elif tag_code == 'T3':
            return 'T3'
        
        # 기본값
        return 'G1'
    
    def _get_time_interval_key(self, minutes: float) -> str:
        """시간 간격을 키로 변환"""
        intervals = self.transition_data.get('time_intervals', {})
        
        for key, interval in intervals.items():
            if interval['min'] <= minutes < interval['max']:
                return key
        
        return 'over_2hr'  # 기본값
    
    def calculate_confidence(self, current_tag: pd.Series, next_tag: pd.Series = None, 
                           prev_tag: pd.Series = None) -> Dict[str, float]:
        """
        태그 간 관계를 분석하여 활동 유형별 신뢰지수 계산
        
        Returns:
            Dict[str, float]: 각 활동 유형별 확률
        """
        # 현재 태그를 카테고리로 변환
        current_category = self._map_tag_to_category(current_tag)
        
        # 기본 확률 설정
        default_probs = {
            'work': 0.33,
            'movement': 0.33,
            'non_work': 0.34,
            'rest': 0.0,
            'meeting': 0.0,
            'training': 0.0,
            'preparation': 0.0
        }
        
        if next_tag is not None:
            # 다음 태그 카테고리
            next_category = self._map_tag_to_category(next_tag)
            
            # 시간 간격 계산
            time_gap = (next_tag['datetime'] - current_tag['datetime']).total_seconds() / 60
            time_interval_key = self._get_time_interval_key(time_gap)
            
            # 전이 확률 조회
            transition_key = f"{current_category}→{next_category}"
            transition_probs = self.transition_data.get('transition_probabilities', {})
            
            if transition_key in transition_probs:
                if time_interval_key in transition_probs[transition_key]:
                    probs = transition_probs[transition_key][time_interval_key].copy()
                    
                    # 누락된 확률 보충
                    for state in default_probs:
                        if state not in probs:
                            probs[state] = 0.0
                    
                    return self._normalize_probabilities(probs)
        
        # 특수 케이스 처리
        probs = self._apply_special_cases(current_tag, next_tag, prev_tag, default_probs)
        
        return self._normalize_probabilities(probs)
    
    def _apply_special_cases(self, current_tag: pd.Series, next_tag: pd.Series, 
                           prev_tag: pd.Series, base_probs: Dict[str, float]) -> Dict[str, float]:
        """특수 케이스에 대한 확률 조정"""
        probs = base_probs.copy()
        
        # 1. 장비 조작 (O 태그)
        if current_tag.get('INOUT_GB') == 'O' or current_tag.get('activity_code') == 'EQUIPMENT_OPERATION':
            probs['work'] = 0.95
            probs['movement'] = 0.03
            probs['non_work'] = 0.02
            probs['rest'] = 0.0
        
        # 2. 식사 시간대 + 식당 위치
        elif self._is_meal_time(current_tag['datetime']) and 'CAFETERIA' in str(current_tag.get('DR_NM', '')).upper():
            probs['work'] = 0.05
            probs['rest'] = 0.90  # 식사는 휴게로 분류
            probs['movement'] = 0.05
            probs['non_work'] = 0.0
        
        # 3. 명확한 출퇴근
        elif current_tag.get('tag_code') == 'T2' and prev_tag is None:
            probs['movement'] = 0.95  # 출근
            probs['work'] = 0.05
        elif current_tag.get('tag_code') == 'T3' and next_tag is None:
            probs['movement'] = 0.95  # 퇴근
            probs['work'] = 0.05
        
        return probs
    
    def _normalize_probabilities(self, probs: Dict[str, float]) -> Dict[str, float]:
        """확률 정규화 (합이 1이 되도록)"""
        total = sum(probs.values())
        if total > 0:
            return {k: v/total for k, v in probs.items()}
        return probs
    
    def _is_meal_time(self, dt: datetime) -> bool:
        """식사 시간대 여부 확인"""
        hour = dt.hour
        minute = dt.minute
        time_in_minutes = hour * 60 + minute
        
        # 조식: 06:30-09:00
        if 390 <= time_in_minutes <= 540:
            return True
        # 중식: 11:20-13:20
        elif 680 <= time_in_minutes <= 800:
            return True
        # 석식: 17:00-20:00
        elif 1020 <= time_in_minutes <= 1200:
            return True
        # 야식: 23:30-01:00
        elif time_in_minutes >= 1410 or time_in_minutes <= 60:
            return True
        
        return False
    
    def calculate_work_time(self, tags_df: pd.DataFrame) -> Tuple[float, float, Dict[str, float]]:
        """
        전체 태그 데이터에서 신뢰지수 기반 근무시간 계산
        
        Returns:
            Tuple[float, float, Dict[str, float]]: (추정 근무시간, 전체 신뢰도, 활동별 시간)
        """
        if tags_df.empty:
            return 0.0, 0.0, {}
        
        tags_df = tags_df.sort_values('datetime').reset_index(drop=True)
        
        activity_minutes = {
            'work': 0.0,
            'movement': 0.0,
            'non_work': 0.0,
            'rest': 0.0,
            'meeting': 0.0,
            'training': 0.0,
            'preparation': 0.0
        }
        
        confidence_scores = []
        
        for i in range(len(tags_df)):
            current_tag = tags_df.iloc[i]
            next_tag = tags_df.iloc[i+1] if i < len(tags_df) - 1 else None
            prev_tag = tags_df.iloc[i-1] if i > 0 else None
            
            # 신뢰지수 계산
            confidence = self.calculate_confidence(current_tag, next_tag, prev_tag)
            
            # 지속 시간
            duration = current_tag.get('duration_minutes', 5)
            
            # 활동별 시간 누적 (확률 기반)
            for activity, prob in confidence.items():
                if activity in activity_minutes:
                    activity_minutes[activity] += duration * prob
            
            # 작업 확률을 신뢰도로 사용
            confidence_scores.append(confidence.get('work', 0) * 100)
        
        # 실제 업무시간 계산 (work + meeting + training + preparation)
        actual_work_minutes = (
            activity_minutes['work'] + 
            activity_minutes['meeting'] + 
            activity_minutes['training'] + 
            activity_minutes['preparation']
        )
        
        # 전체 신뢰도 계산 (0-100 범위로 제한)
        avg_confidence = np.mean(confidence_scores) if confidence_scores else 0
        avg_confidence = min(avg_confidence, 100.0)
        
        # 시간을 hours로 변환
        work_hours = actual_work_minutes / 60
        
        # 총 체류시간 계산
        total_minutes = sum(tags_df['duration_minutes']) if 'duration_minutes' in tags_df.columns else len(tags_df) * 5
        total_hours = total_minutes / 60
        
        # 업무시간이 체류시간을 초과하지 않도록 제한
        if work_hours > total_hours:
            work_hours = total_hours * 0.8  # 체류시간의 80%로 제한
        
        activity_breakdown = {k: v/60 for k, v in activity_minutes.items()}
        
        return work_hours, avg_confidence, activity_breakdown