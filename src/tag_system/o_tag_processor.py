"""
O 태그 특별 처리 모듈
실제 업무 수행 로그(ABC 활동 데이터, 장비 조작 로그 등)를 O 태그로 변환하고 처리
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

class OTagProcessor:
    """O 태그 처리 클래스"""
    
    def __init__(self, session: Session = None):
        self.session = session
        self.o_tag_sources = {
            'abc_activity': 'abc_activity_data',
            'equipment_log': 'equipment_operation_log',
            'system_access': 'system_access_log',
            'pc_login': 'pc_login_log'
        }
    
    def extract_o_tags_from_abc_data(self, employee_id: str, date: datetime) -> List[Dict]:
        """ABC 활동 데이터에서 O 태그 추출"""
        if not self.session:
            logger.error("데이터베이스 세션이 없습니다.")
            return []
        
        try:
            # ABC 활동 데이터 조회
            query = text("""
                SELECT 
                    employee_id,
                    work_date,
                    sequence,
                    activity_classification,
                    activity_code_1,
                    activity_code_2,
                    activity_code_3,
                    duration_minutes,
                    activity_major,
                    activity_medium,
                    activity_minor
                FROM abc_activity_data
                WHERE employee_id = :employee_id
                AND DATE(work_date) = DATE(:date)
                ORDER BY sequence
            """)
            
            result = self.session.execute(query, {
                'employee_id': employee_id,
                'date': date
            })
            
            o_tags = []
            current_time = datetime.combine(date.date(), datetime.min.time())
            
            for row in result:
                # O 태그 생성
                o_tag = {
                    'employee_id': row.employee_id,
                    'timestamp': current_time,
                    'tag_code': 'O',
                    'source': 'abc_activity',
                    'activity_type': row.activity_classification,
                    'activity_detail': {
                        'major': row.activity_major,
                        'medium': row.activity_medium,
                        'minor': row.activity_minor,
                        'codes': [row.activity_code_1, row.activity_code_2, row.activity_code_3]
                    },
                    'duration_minutes': row.duration_minutes,
                    'confidence': 1.0  # ABC 데이터는 100% 신뢰
                }
                
                o_tags.append(o_tag)
                
                # 다음 활동 시작 시간 계산
                current_time += timedelta(minutes=row.duration_minutes)
            
            logger.info(f"{employee_id}의 {date.date()}에 대해 {len(o_tags)}개 O 태그 추출")
            return o_tags
            
        except Exception as e:
            logger.error(f"ABC 데이터에서 O 태그 추출 중 오류: {e}")
            return []
    
    def merge_o_tags_with_tag_sequence(self, tag_sequence: List[Dict], 
                                     o_tags: List[Dict]) -> List[Dict]:
        """O 태그를 기존 태그 시퀀스에 병합"""
        if not o_tags:
            return tag_sequence
        
        # 타임스탬프로 정렬
        all_tags = tag_sequence + o_tags
        all_tags.sort(key=lambda x: x['timestamp'])
        
        # O 태그 영향 범위 계산 및 병합
        merged_sequence = []
        o_tag_active = False
        o_tag_end_time = None
        
        for tag in all_tags:
            if tag.get('tag_code') == 'O':
                # O 태그 시작
                o_tag_active = True
                o_tag_end_time = tag['timestamp'] + timedelta(minutes=tag.get('duration_minutes', 0))
                tag['is_o_tag'] = True
                merged_sequence.append(tag)
            else:
                # 일반 태그
                if o_tag_active and tag['timestamp'] <= o_tag_end_time:
                    # O 태그 영향 범위 내의 태그
                    tag['has_o_tag'] = True
                    tag['o_tag_confidence'] = self._calculate_o_tag_influence(
                        tag['timestamp'], o_tag_end_time
                    )
                else:
                    # O 태그 영향 범위 밖
                    tag['has_o_tag'] = False
                    o_tag_active = False
                
                merged_sequence.append(tag)
        
        return merged_sequence
    
    def _calculate_o_tag_influence(self, tag_time: datetime, o_tag_end: datetime) -> float:
        """O 태그의 영향력 계산 (시간이 지날수록 감소)"""
        if tag_time >= o_tag_end:
            return 0.0
        
        # 남은 시간 비율로 영향력 계산
        total_duration = (o_tag_end - tag_time).total_seconds()
        if total_duration <= 0:
            return 0.0
        
        # 최대 30분까지 영향
        max_influence_seconds = 30 * 60
        influence = min(total_duration / max_influence_seconds, 1.0)
        
        return influence
    
    def identify_work_periods_with_o_tags(self, tag_sequence: List[Dict]) -> List[Dict]:
        """O 태그를 기반으로 실제 업무 구간 식별"""
        work_periods = []
        current_period = None
        
        for i, tag in enumerate(tag_sequence):
            if tag.get('tag_code') == 'O' or tag.get('has_o_tag'):
                if not current_period:
                    # 새로운 업무 구간 시작
                    current_period = {
                        'start_time': tag['timestamp'],
                        'start_index': i,
                        'tags': [tag],
                        'o_tag_count': 1 if tag.get('tag_code') == 'O' else 0,
                        'confidence': tag.get('o_tag_confidence', 1.0)
                    }
                else:
                    # 기존 업무 구간 연장
                    current_period['tags'].append(tag)
                    if tag.get('tag_code') == 'O':
                        current_period['o_tag_count'] += 1
                    
                    # 신뢰도 업데이트 (최대값)
                    current_period['confidence'] = max(
                        current_period['confidence'],
                        tag.get('o_tag_confidence', 0)
                    )
            else:
                # 업무 구간 종료
                if current_period:
                    current_period['end_time'] = tag['timestamp']
                    current_period['end_index'] = i - 1
                    current_period['duration_minutes'] = (
                        current_period['end_time'] - current_period['start_time']
                    ).total_seconds() / 60
                    
                    work_periods.append(current_period)
                    current_period = None
        
        # 마지막 구간 처리
        if current_period and len(tag_sequence) > 0:
            current_period['end_time'] = tag_sequence[-1]['timestamp']
            current_period['end_index'] = len(tag_sequence) - 1
            current_period['duration_minutes'] = (
                current_period['end_time'] - current_period['start_time']
            ).total_seconds() / 60
            work_periods.append(current_period)
        
        return work_periods
    
    def calculate_actual_work_time(self, work_periods: List[Dict]) -> Dict:
        """O 태그 기반 실제 근무시간 계산"""
        if not work_periods:
            return {
                'total_work_minutes': 0,
                'confirmed_work_minutes': 0,
                'unconfirmed_work_minutes': 0,
                'work_confidence': 0.0
            }
        
        total_minutes = 0
        confirmed_minutes = 0
        
        for period in work_periods:
            duration = period['duration_minutes']
            confidence = period['confidence']
            
            total_minutes += duration
            
            # O 태그가 있거나 신뢰도가 높은 경우 확정 근무시간
            if period['o_tag_count'] > 0 or confidence >= 0.8:
                confirmed_minutes += duration
        
        unconfirmed_minutes = total_minutes - confirmed_minutes
        work_confidence = confirmed_minutes / total_minutes if total_minutes > 0 else 0
        
        return {
            'total_work_minutes': total_minutes,
            'confirmed_work_minutes': confirmed_minutes,
            'unconfirmed_work_minutes': unconfirmed_minutes,
            'work_confidence': work_confidence,
            'work_periods': len(work_periods)
        }
    
    def detect_work_gaps(self, work_periods: List[Dict], threshold_minutes: int = 30) -> List[Dict]:
        """업무 구간 사이의 공백 감지"""
        gaps = []
        
        for i in range(1, len(work_periods)):
            prev_period = work_periods[i-1]
            curr_period = work_periods[i]
            
            gap_start = prev_period['end_time']
            gap_end = curr_period['start_time']
            gap_duration = (gap_end - gap_start).total_seconds() / 60
            
            if gap_duration >= threshold_minutes:
                gap = {
                    'start_time': gap_start,
                    'end_time': gap_end,
                    'duration_minutes': gap_duration,
                    'type': self._classify_gap_type(gap_duration)
                }
                gaps.append(gap)
        
        return gaps
    
    def _classify_gap_type(self, duration_minutes: float) -> str:
        """공백 시간 유형 분류"""
        if duration_minutes < 30:
            return 'short_break'
        elif duration_minutes < 60:
            return 'meal_break'
        elif duration_minutes < 120:
            return 'long_break'
        else:
            return 'extended_absence'
    
    def generate_o_tag_statistics(self, tag_sequence: List[Dict]) -> Dict:
        """O 태그 통계 생성"""
        total_tags = len(tag_sequence)
        o_tags = [t for t in tag_sequence if t.get('tag_code') == 'O']
        influenced_tags = [t for t in tag_sequence if t.get('has_o_tag')]
        
        stats = {
            'total_tags': total_tags,
            'o_tag_count': len(o_tags),
            'o_tag_percentage': (len(o_tags) / total_tags * 100) if total_tags > 0 else 0,
            'influenced_tag_count': len(influenced_tags),
            'influenced_percentage': (len(influenced_tags) / total_tags * 100) if total_tags > 0 else 0,
            'o_tag_sources': {}
        }
        
        # 소스별 O 태그 수 계산
        for o_tag in o_tags:
            source = o_tag.get('source', 'unknown')
            stats['o_tag_sources'][source] = stats['o_tag_sources'].get(source, 0) + 1
        
        return stats