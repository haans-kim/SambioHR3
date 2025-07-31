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
        # tag_code가 있으면 우선 사용 (가장 정확한 매핑)
        tag_code = tag_info.get('tag_code', '') or tag_info.get('Tag_Code', '')
        if tag_code:
            # G1-G4, N1-N2, T1-T3, M1-M2, O 태그 직접 반환
            if tag_code in ['G1', 'G2', 'G3', 'G4', 'N1', 'N2', 'T1', 'T2', 'T3', 'M1', 'M2', 'O']:
                return tag_code
        
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
        
        # tag_code 가져오기
        tag_code = current_tag.get('tag_code', '') or current_tag.get('Tag_Code', '')
        
        # 1. T2 태그 (출입 IN) - 항상 출근
        if tag_code == 'T2':
            probs['movement'] = 0.95  # 출근
            probs['work'] = 0.05
            probs['non_work'] = 0.0
            probs['rest'] = 0.0
        
        # 2. T3 태그 (출입 OUT) - 항상 퇴근
        elif tag_code == 'T3':
            probs['movement'] = 0.95  # 퇴근
            probs['work'] = 0.05
            probs['non_work'] = 0.0
            probs['rest'] = 0.0
        
        # 3. O 태그 (실제 업무 수행 로그)
        elif tag_code == 'O' or current_tag.get('INOUT_GB') == 'O' or current_tag.get('activity_code') == 'EQUIPMENT_OPERATION':
            probs['work'] = 0.98
            probs['movement'] = 0.02
            probs['non_work'] = 0.0
            probs['rest'] = 0.0
        
        # 4. G1 태그 (주업무공간)
        elif tag_code == 'G1':
            probs['work'] = 0.85
            probs['movement'] = 0.10
            probs['rest'] = 0.05
            probs['non_work'] = 0.0
        
        # 5. M1 태그 (식사)
        elif tag_code == 'M1':
            probs['work'] = 0.0
            probs['rest'] = 1.0  # 식사는 휴게로 분류
            probs['movement'] = 0.0
            probs['non_work'] = 0.0
        
        # 6. 식사 시간대 + 식당 위치 (태그코드가 없는 경우)
        elif not tag_code and self._is_meal_time(current_tag['datetime']) and 'CAFETERIA' in str(current_tag.get('DR_NM', '')).upper():
            probs['work'] = 0.05
            probs['rest'] = 0.90  # 식사는 휴게로 분류
            probs['movement'] = 0.05
            probs['non_work'] = 0.0
        
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
        
        # 점심시간 및 제외 구간 찾기
        lunch_blocks = []  # [(start_idx, end_idx)]
        takeout_blocks = []  # [(start_idx, end_idx)]
        
        # 연속된 작업 구간을 찾기 위한 변수
        work_blocks = []  # [(start_idx, end_idx, activity_type)]
        current_block_start = None
        current_activity = None
        
        # 작업 관련 활동 코드 (대문자와 소문자 모두 포함)
        work_activities = [
            'work', 'meeting', 'training', 'preparation',  # 소문자 (신뢰지수 계산 결과)
            'WORK', 'MEETING', 'TRAINING', 'PREPARATION',  # 대문자 (태그 기반 규칙)
            'FOCUSED_WORK', 'EQUIPMENT_OPERATION',  # 추가 작업 활동
            'G3_MEETING',  # Knox PIMS 회의
            '업무', '회의', '교육', '준비',  # 한글 상태명
            '업무(확실)'  # O 태그로 확정된 업무
        ]
        
        # 각 태그의 주요 활동 결정 및 연속 블록 찾기
        for i in range(len(tags_df)):
            current_tag = tags_df.iloc[i]
            next_tag = tags_df.iloc[i+1] if i < len(tags_df) - 1 else None
            prev_tag = tags_df.iloc[i-1] if i > 0 else None
            
            # 점심시간 체크 (11:00-14:00 사이의 식당)
            is_lunch_time = False
            hour = current_tag['datetime'].hour
            if 11 <= hour < 14 and 'CAFETERIA' in str(current_tag.get('DR_NM', '')).upper():
                is_lunch_time = True
                
                # 점심시간 블록 추가
                if not lunch_blocks or i > lunch_blocks[-1][1] + 1:
                    lunch_blocks.append((i, i))
                else:
                    lunch_blocks[-1] = (lunch_blocks[-1][0], i)
            
            # TAKEOUT 체크
            is_takeout = 'TAKEOUT' in str(current_tag.get('DR_NM', '')).upper()
            if is_takeout:
                if not takeout_blocks or i > takeout_blocks[-1][1] + 1:
                    takeout_blocks.append((i, i))
                else:
                    takeout_blocks[-1] = (takeout_blocks[-1][0], i)
            
            # 점심시간이나 TAKEOUT이 아닌 경우에만 작업 활동 체크
            if not is_lunch_time and not is_takeout:
                # activity_code 또는 state 필드 확인
                activity = None
                if 'activity_code' in current_tag and current_tag['activity_code']:
                    activity = current_tag['activity_code']
                elif 'state' in current_tag and current_tag['state']:
                    activity = current_tag['state']
                
                if activity:
                    # 이미 분류된 활동이 있으면 그것을 사용
                    is_work_activity = activity in work_activities
                    # 디버깅용 로그
                    if i < 5:  # 처음 5개만 로그
                        self.logger.debug(f"태그 {i}: activity={activity}, is_work={is_work_activity}")
                else:
                    # activity가 없으면 신뢰지수 계산
                    confidence = self.calculate_confidence(current_tag, next_tag, prev_tag)
                    
                    # 가장 높은 확률의 활동 선택
                    main_activity = max(confidence.items(), key=lambda x: x[1])[0]
                    activity = main_activity  # activity 변수에 할당
                    
                    # 작업 관련 활동인지 확인
                    is_work_activity = main_activity in work_activities
                
                # 활동 유형 결정
                if is_work_activity:
                    # G3_MEETING은 meeting으로 분류
                    if activity == 'G3_MEETING':
                        activity_type = 'meeting'
                    elif activity in ['MEETING', '회의']:
                        activity_type = 'meeting'
                    elif activity in ['TRAINING', '교육']:
                        activity_type = 'training'
                    elif activity in ['PREPARATION', '준비']:
                        activity_type = 'preparation'
                    else:
                        activity_type = 'work'
                else:
                    activity_type = None
                
                # 블록 처리
                if current_block_start is None:
                    # 새 블록 시작
                    if is_work_activity:
                        current_block_start = i
                        current_activity = activity_type
                else:
                    # 현재 블록 진행 중
                    if not is_work_activity or current_activity != activity_type:
                        # 작업 블록 종료 (활동 종료 또는 활동 유형 변경)
                        work_blocks.append((current_block_start, i-1, current_activity))
                        current_block_start = None if not is_work_activity else i
                        current_activity = None if not is_work_activity else activity_type
            else:
                # 점심시간이나 TAKEOUT인 경우 현재 작업 블록 종료
                if current_block_start is not None:
                    work_blocks.append((current_block_start, i-1, current_activity))
                    current_block_start = None
                    current_activity = None
        
        # 마지막 블록 처리
        if current_block_start is not None:
            work_blocks.append((current_block_start, len(tags_df)-1, current_activity))
        
        # 작업 시간 계산
        total_work_minutes = 0.0
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
        
        # 작업 블록의 시간 계산
        self.logger.info(f"총 작업 블록 수: {len(work_blocks)}")
        for block_idx, (start_idx, end_idx, activity_type) in enumerate(work_blocks):
            # 블록의 시작과 끝 시간
            start_time = tags_df.iloc[start_idx]['datetime']
            if end_idx < len(tags_df) - 1:
                # 다음 태그의 시간까지를 블록의 끝으로 설정
                end_time = tags_df.iloc[end_idx + 1]['datetime']
            else:
                # 마지막 태그인 경우, duration_minutes를 사용하거나 기본값 5분 추가
                last_duration = tags_df.iloc[end_idx].get('duration_minutes', 5)
                end_time = tags_df.iloc[end_idx]['datetime'] + timedelta(minutes=last_duration)
            
            # 블록의 총 시간 (분 단위)
            block_minutes = (end_time - start_time).total_seconds() / 60
            total_work_minutes += block_minutes
            
            # 첫 몇 개 블록만 로그
            if block_idx < 3:
                self.logger.info(f"작업 블록 {block_idx}: {start_time} ~ {end_time} ({block_minutes:.1f}분, {activity_type})")
            
            # activity_type에 따라 적절한 카테고리에 시간 추가
            if activity_type in activity_minutes:
                activity_minutes[activity_type] += block_minutes
            else:
                activity_minutes['work'] += block_minutes
            
            # 블록 내 태그들의 신뢰도 수집
            for idx in range(start_idx, end_idx + 1):
                tag = tags_df.iloc[idx]
                next_tag = tags_df.iloc[idx+1] if idx < len(tags_df) - 1 else None
                prev_tag = tags_df.iloc[idx-1] if idx > 0 else None
                confidence = self.calculate_confidence(tag, next_tag, prev_tag)
                confidence_scores.append(confidence.get('work', 0) * 100)
        
        # 점심시간 계산 (1시간 고정 차감)
        lunch_minutes = 0
        if lunch_blocks:
            # 점심시간은 블록 수와 관계없이 최대 1시간(60분)만 차감
            lunch_minutes = min(60, len(lunch_blocks) * 5)  # 태그당 5분으로 가정
        
        # TAKEOUT 시간 계산 (30분 고정 차감)
        takeout_minutes = 0
        if takeout_blocks:
            # TAKEOUT은 30분 고정 차감
            takeout_minutes = 30
        
        # 작업시간에서 점심시간 및 TAKEOUT 시간 차감
        total_work_minutes = max(0, total_work_minutes - lunch_minutes - takeout_minutes)
        
        # 비작업 시간의 활동 분류 (참고용)
        for i in range(len(tags_df)):
            # 작업 블록에 포함되지 않은 태그들에 대해서만 처리
            in_work_block = any(start <= i <= end for start, end, _ in work_blocks)
            in_lunch_block = any(start <= i <= end for start, end in lunch_blocks)
            in_takeout_block = any(start <= i <= end for start, end in takeout_blocks)
            
            if not in_work_block and not in_lunch_block and not in_takeout_block:
                current_tag = tags_df.iloc[i]
                next_tag = tags_df.iloc[i+1] if i < len(tags_df) - 1 else None
                prev_tag = tags_df.iloc[i-1] if i > 0 else None
                
                confidence = self.calculate_confidence(current_tag, next_tag, prev_tag)
                duration = current_tag.get('duration_minutes', 5)
                
                # 주요 활동 결정
                main_activity = max(confidence.items(), key=lambda x: x[1])[0]
                if main_activity in activity_minutes and main_activity not in work_activities:
                    activity_minutes[main_activity] += duration
            elif in_lunch_block or in_takeout_block:
                # 점심시간이나 TAKEOUT은 rest로 분류
                activity_minutes['rest'] += current_tag.get('duration_minutes', 5)
        
        # 전체 신뢰도 계산 (0-100 범위로 제한)
        avg_confidence = np.mean(confidence_scores) if confidence_scores else 0
        avg_confidence = min(avg_confidence, 100.0)
        
        # 시간을 hours로 변환
        work_hours = total_work_minutes / 60
        
        # 총 체류시간 계산
        if len(tags_df) > 1:
            first_time = tags_df.iloc[0]['datetime']
            last_time = tags_df.iloc[-1]['datetime']
            last_duration = tags_df.iloc[-1].get('duration_minutes', 5)
            total_minutes = (last_time - first_time).total_seconds() / 60 + last_duration
        else:
            total_minutes = tags_df.iloc[0].get('duration_minutes', 5) if len(tags_df) > 0 else 0
        
        total_hours = total_minutes / 60
        
        # 식사시간 계산 (lunch_minutes + takeout_minutes는 이미 work_minutes에서 차감됨)
        meal_hours = (lunch_minutes + takeout_minutes) / 60
        
        # 업무시간이 (체류시간 - 식사시간)을 초과하지 않도록 제한
        max_work_hours = total_hours - meal_hours
        if work_hours > max_work_hours:
            work_hours = max(0, max_work_hours)
        
        activity_breakdown = {k: v/60 for k, v in activity_minutes.items()}
        
        # 결과 로그
        self.logger.info(f"작업시간 계산 완료: {work_hours:.2f}시간 (신뢰도: {avg_confidence:.2f})")
        self.logger.info(f"활동별 시간: {activity_breakdown}")
        
        return work_hours, avg_confidence, activity_breakdown