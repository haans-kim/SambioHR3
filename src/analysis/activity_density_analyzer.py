"""
활동 밀도 기반 실근무 분석 모듈
실제 업무 활동(O태그, Knox 데이터)의 빈도를 기반으로 근무/비근무 판별
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class ActivityDensityAnalyzer:
    """활동 밀도 기반 근무 분석기"""
    
    def __init__(self):
        # 활동 밀도 임계값 (시간당 활동 횟수)
        self.DENSITY_THRESHOLDS = {
            'high': 3.0,      # 시간당 3회 이상 - 확실한 근무
            'medium': 1.0,    # 시간당 1-3회 - 근무 가능성
            'low': 0.5,       # 시간당 0.5-1회 - 의심
            'idle': 0.0       # 활동 없음 - 비근무
        }
        
        # 신뢰도 조정 계수
        self.CONFIDENCE_ADJUSTMENTS = {
            'high': 1.0,      # 신뢰도 유지
            'medium': 0.8,    # 20% 감소
            'low': 0.5,       # 50% 감소
            'idle': 0.2       # 80% 감소
        }
        
        # 무활동 임계값 (분)
        self.IDLE_THRESHOLD_MINUTES = 30
        
        # 꼬리물기 의심 시간 (시간)
        self.TAILGATING_THRESHOLD_HOURS = 2
    
    def calculate_activity_density(self, data: pd.DataFrame, 
                                  window_minutes: int = 30) -> pd.Series:
        """
        시간 윈도우 기반 활동 밀도 계산
        
        Args:
            data: 태그 데이터
            window_minutes: 윈도우 크기 (기본 30분)
            
        Returns:
            활동 밀도 Series (시간당 활동 횟수)
        """
        activity_density = []
        
        for i in range(len(data)):
            row = data.iloc[i]
            window_start = row['timestamp'] - timedelta(minutes=window_minutes/2)
            window_end = row['timestamp'] + timedelta(minutes=window_minutes/2)
            
            # 윈도우 내 실제 활동 카운트
            actual_activities = data[
                (data['timestamp'] >= window_start) & 
                (data['timestamp'] <= window_end) &
                (
                    (data['INOUT_GB'] == 'O') |  # 장비 조작
                    (data['source'].isin(['Knox_Approval', 'Knox_Mail', 'EAM', 'LAMS', 'MES'])) |  # 시스템 활동
                    (data['Tag_Code'] == 'G3')  # 회의
                )
            ]
            
            # 시간당 활동 수로 변환
            density = len(actual_activities) / (window_minutes / 60)
            activity_density.append(density)
        
        return pd.Series(activity_density, index=data.index)
    
    def classify_density_level(self, density: float) -> str:
        """활동 밀도 레벨 분류"""
        if density >= self.DENSITY_THRESHOLDS['high']:
            return 'high'
        elif density >= self.DENSITY_THRESHOLDS['medium']:
            return 'medium'
        elif density >= self.DENSITY_THRESHOLDS['low']:
            return 'low'
        else:
            return 'idle'
    
    def detect_idle_periods(self, data: pd.DataFrame) -> List[Dict]:
        """
        무활동 구간 감지
        
        Returns:
            무활동 구간 리스트
        """
        idle_periods = []
        last_activity_time = None
        last_activity_idx = None
        
        for i, row in data.iterrows():
            # 실제 활동인지 확인
            is_real_activity = (
                row.get('INOUT_GB') == 'O' or  # 장비 조작
                row.get('source') in ['Knox_Approval', 'Knox_Mail', 'EAM', 'LAMS', 'MES'] or
                row.get('Tag_Code') == 'G3'  # 회의
            )
            
            if is_real_activity:
                if last_activity_time is not None:
                    gap_minutes = (row['timestamp'] - last_activity_time).total_seconds() / 60
                    
                    if gap_minutes > self.IDLE_THRESHOLD_MINUTES:
                        # 무활동 구간 동안의 위치 파악
                        idle_data = data.loc[last_activity_idx:i]
                        if len(idle_data) > 2:  # 첫/끝 제외하고 중간 데이터가 있으면
                            idle_data = idle_data.iloc[1:-1]  # 첫/끝 제외
                            
                            # 가장 빈번한 위치
                            if not idle_data.empty and 'DR_NM' in idle_data.columns:
                                location_counts = idle_data['DR_NM'].value_counts()
                                main_location = location_counts.index[0] if len(location_counts) > 0 else 'Unknown'
                            else:
                                main_location = 'Unknown'
                            
                            idle_periods.append({
                                'start': last_activity_time,
                                'end': row['timestamp'],
                                'duration_minutes': gap_minutes,
                                'location': main_location,
                                'start_idx': last_activity_idx,
                                'end_idx': i
                            })
                
                last_activity_time = row['timestamp']
                last_activity_idx = i
        
        return idle_periods
    
    def detect_tailgating_patterns(self, data: pd.DataFrame) -> List[Dict]:
        """
        꼬리물기 패턴 감지
        
        Returns:
            꼬리물기 의심 구간 리스트
        """
        tailgating_suspects = []
        
        for i in range(len(data) - 1):
            curr = data.iloc[i]
            
            # T2(입문) 태그 찾기
            if curr.get('Tag_Code') == 'T2':
                # 이후 2시간 내 활동 확인
                time_limit = curr['timestamp'] + timedelta(hours=self.TAILGATING_THRESHOLD_HOURS)
                future_data = data[(data['timestamp'] > curr['timestamp']) & 
                                  (data['timestamp'] <= time_limit)]
                
                if not future_data.empty:
                    # 첫 번째 활동까지의 시간
                    first_activity = future_data[
                        (future_data['INOUT_GB'] == 'O') |
                        (future_data['source'].isin(['Knox_Approval', 'Knox_Mail', 'EAM', 'LAMS', 'MES']))
                    ]
                    
                    if first_activity.empty:
                        # 2시간 동안 활동 없음 - 꼬리물기 의심
                        next_tag = future_data.iloc[0] if len(future_data) > 0 else None
                        
                        if next_tag is not None:
                            gap_hours = (next_tag['timestamp'] - curr['timestamp']).total_seconds() / 3600
                            
                            if gap_hours >= 2:
                                confidence = 0.9 if next_tag.get('Tag_Code') == 'G1' else 0.5
                                
                                tailgating_suspects.append({
                                    'start': curr['timestamp'],
                                    'end': next_tag['timestamp'],
                                    'duration_hours': gap_hours,
                                    'entry_location': curr.get('DR_NM', 'Unknown'),
                                    'next_location': next_tag.get('DR_NM', 'Unknown'),
                                    'confidence': confidence
                                })
        
        return tailgating_suspects
    
    def adjust_confidence_by_density(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        활동 밀도에 따른 신뢰도 조정
        
        Args:
            data: 활동 분류된 데이터
            
        Returns:
            신뢰도 조정된 데이터
        """
        # 활동 밀도 계산
        data['activity_density'] = self.calculate_activity_density(data)
        
        # 밀도 레벨 분류
        data['density_level'] = data['activity_density'].apply(self.classify_density_level)
        
        # 신뢰도 조정
        for level, adjustment in self.CONFIDENCE_ADJUSTMENTS.items():
            mask = data['density_level'] == level
            if 'confidence' in data.columns:
                data.loc[mask, 'confidence'] = data.loc[mask, 'confidence'] * adjustment
            else:
                data.loc[mask, 'confidence'] = 80 * adjustment  # 기본 신뢰도 80
        
        return data
    
    def reclassify_idle_periods(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        무활동 구간 재분류
        
        Args:
            data: 활동 분류된 데이터
            
        Returns:
            재분류된 데이터
        """
        # 무활동 구간 감지
        idle_periods = self.detect_idle_periods(data)
        
        for period in idle_periods:
            # 해당 구간을 IDLE로 재분류
            if 'start_idx' in period and 'end_idx' in period:
                idle_mask = (data.index >= period['start_idx']) & (data.index < period['end_idx'])
                
                # 30분-1시간: 짧은 휴식
                if period['duration_minutes'] <= 60:
                    data.loc[idle_mask, 'activity_code'] = 'SHORT_REST'
                    data.loc[idle_mask, 'confidence'] = 70
                # 1시간 이상: 긴 휴식/비근무
                else:
                    data.loc[idle_mask, 'activity_code'] = 'LONG_REST'
                    data.loc[idle_mask, 'confidence'] = 30
                
                logger.info(f"무활동 구간 감지: {period['duration_minutes']:.1f}분 at {period['location']}")
        
        return data
    
    def apply_comprehensive_analysis(self, data: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """
        종합적인 활동 밀도 분석 적용
        
        Args:
            data: 원본 활동 데이터
            
        Returns:
            (분석된 데이터, 실근무 마스크)
        """
        # 1. 활동 밀도 기반 신뢰도 조정
        data = self.adjust_confidence_by_density(data)
        
        # 2. 무활동 구간 재분류
        data = self.reclassify_idle_periods(data)
        
        # 3. 꼬리물기 패턴 감지
        tailgating = self.detect_tailgating_patterns(data)
        for suspect in tailgating:
            mask = (data['timestamp'] >= suspect['start']) & \
                   (data['timestamp'] <= suspect['end'])
            data.loc[mask, 'activity_code'] = 'TAILGATING_SUSPECT'
            data.loc[mask, 'confidence'] = 100 * (1 - suspect['confidence'])
            
            logger.warning(f"꼬리물기 의심: {suspect['duration_hours']:.1f}시간 at {suspect['entry_location']}")
        
        # 4. 실근무 마스크 생성
        actual_work_mask = (
            # 근무 관련 활동
            (data['activity_code'].isin([
                'WORK', 'EQUIPMENT_OPERATION', 'G3_MEETING', 
                'KNOX_APPROVAL', 'KNOX_MAIL', 'EAM_WORK', 'LAMS_WORK', 'MES_WORK'
            ])) &
            # 신뢰도 50% 이상
            (data['confidence'] >= 50) &
            # 활동 밀도 시간당 0.5회 이상
            (data['activity_density'] >= 0.5)
        )
        
        # 통계 로깅
        total_records = len(data)
        actual_work_records = actual_work_mask.sum()
        work_ratio = actual_work_records / total_records * 100 if total_records > 0 else 0
        
        logger.info(f"활동 밀도 분석 완료: 전체 {total_records}건 중 실근무 {actual_work_records}건 ({work_ratio:.1f}%)")
        
        return data, actual_work_mask