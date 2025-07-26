"""
태그 기반 신뢰지수 계산 시스템
태그 간 시간 간격과 패턴을 분석하여 작업/이동/비근무 확률을 계산
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Tuple, List


class ConfidenceCalculator:
    """태그 패턴 기반 신뢰지수 계산"""
    
    def __init__(self):
        # 시간 간격별 활동 유형 확률 정의
        self.time_gap_rules = {
            # (min_minutes, max_minutes): {'work': prob, 'movement': prob, 'non_work': prob}
            (0, 5): {'work': 0.05, 'movement': 0.95, 'non_work': 0.00},      # 5분 미만: 95% 이동
            (5, 30): {'work': 0.60, 'movement': 0.35, 'non_work': 0.05},     # 5-30분: 60% 작업
            (30, 60): {'work': 0.75, 'movement': 0.20, 'non_work': 0.05},    # 30-60분: 75% 작업
            (60, 120): {'work': 0.75, 'movement': 0.15, 'non_work': 0.10},   # 1-2시간: 75% 작업
            (120, float('inf')): {'work': 0.70, 'movement': 0.10, 'non_work': 0.20}  # 2시간 이상
        }
        
        # 구역 타입별 가중치
        self.area_weights = {
            'Y': 1.2,    # 근무구역: 작업 확률 20% 증가
            'N': 0.3,    # 비근무구역: 작업 확률 70% 감소
            'T': 0.5,    # 이동구간: 작업 확률 50% 감소
            'G': 1.0     # 일반구역: 기본값
        }
        
        # 특정 패턴에 대한 보정
        self.pattern_adjustments = {
            'meal_time': {'work': 0.05, 'movement': 0.05, 'non_work': 0.90},  # 식사시간대
            'gate_exit_entry': {'work': 0.10, 'movement': 0.10, 'non_work': 0.80},  # 출문-재입문
            'equipment_operation': {'work': 0.95, 'movement': 0.05, 'non_work': 0.00}  # 장비조작
        }
    
    def calculate_confidence(self, current_tag: pd.Series, next_tag: pd.Series = None, 
                           prev_tag: pd.Series = None) -> Dict[str, float]:
        """
        태그 간 관계를 분석하여 활동 유형별 신뢰지수 계산
        
        Returns:
            Dict[str, float]: 각 활동 유형별 확률 {'work': 0.75, 'movement': 0.15, 'non_work': 0.10}
        """
        base_confidence = {'work': 0.5, 'movement': 0.3, 'non_work': 0.2}
        
        # 1. 다음 태그까지의 시간 간격 기반 확률
        if next_tag is not None:
            time_gap = (next_tag['datetime'] - current_tag['datetime']).total_seconds() / 60
            
            for (min_gap, max_gap), probs in self.time_gap_rules.items():
                if min_gap <= time_gap < max_gap:
                    base_confidence = probs.copy()
                    break
        
        # 2. 구역 타입에 따른 가중치 적용
        if 'work_area_type' in current_tag:
            area_type = current_tag['work_area_type']
            weight = self.area_weights.get(area_type, 1.0)
            base_confidence['work'] *= weight
            base_confidence['non_work'] = 1 - base_confidence['work'] - base_confidence['movement']
        
        # 3. 특정 패턴 검사
        confidence = self._apply_pattern_adjustments(current_tag, next_tag, prev_tag, base_confidence)
        
        # 4. 정규화 (합이 1이 되도록)
        total = sum(confidence.values())
        if total > 0:
            confidence = {k: v/total for k, v in confidence.items()}
        
        return confidence
    
    def _apply_pattern_adjustments(self, current_tag: pd.Series, next_tag: pd.Series, 
                                  prev_tag: pd.Series, confidence: Dict[str, float]) -> Dict[str, float]:
        """특정 패턴에 대한 신뢰지수 조정"""
        
        # 1. 식사 시간대 체크
        if self._is_meal_time(current_tag['datetime']):
            # 식당이 아닌 곳에서 식사 시간대 = 비근무 가능성 높음
            if 'CAFETERIA' not in current_tag.get('DR_NM', ''):
                confidence = self.pattern_adjustments['meal_time'].copy()
        
        # 2. 출문-재입문 패턴
        if current_tag.get('tag_code') == 'T3' and next_tag is not None and next_tag.get('tag_code') == 'T2':
            time_gap = (next_tag['datetime'] - current_tag['datetime']).total_seconds() / 60
            if time_gap > 30:  # 30분 이상 외출
                confidence = self.pattern_adjustments['gate_exit_entry'].copy()
        
        # 3. 장비 조작
        if current_tag.get('activity_code') == 'EQUIPMENT_OPERATION' or current_tag.get('INOUT_GB') == 'O':
            confidence = self.pattern_adjustments['equipment_operation'].copy()
        
        # 4. 연속된 비근무구역 체류
        if current_tag.get('work_area_type') == 'N':
            if prev_tag is not None and prev_tag.get('work_area_type') == 'N':
                # 연속으로 비근무구역에 있으면 비근무 확률 증가
                confidence['non_work'] *= 1.5
                confidence['work'] *= 0.5
        
        return confidence
    
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
        
        total_work_minutes = 0.0
        total_movement_minutes = 0.0
        total_non_work_minutes = 0.0
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
            total_work_minutes += duration * confidence['work']
            total_movement_minutes += duration * confidence['movement']
            total_non_work_minutes += duration * confidence['non_work']
            
            # 작업 확률을 신뢰도로 사용
            confidence_scores.append(confidence['work'] * 100)
        
        # 전체 신뢰도 계산
        avg_confidence = np.mean(confidence_scores) if confidence_scores else 0
        
        # 시간을 hours로 변환
        work_hours = total_work_minutes / 60
        
        activity_breakdown = {
            'work': total_work_minutes / 60,
            'movement': total_movement_minutes / 60,
            'non_work': total_non_work_minutes / 60
        }
        
        return work_hours, avg_confidence, activity_breakdown