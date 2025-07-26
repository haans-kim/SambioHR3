"""
기존 시스템과 새로운 태그 시스템을 연결하는 어댑터
"""

import logging
from typing import Dict, List, Optional
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime
from .tag_mapper import TagMapper
from .state_classifier import TagStateClassifier
from .o_tag_processor import OTagProcessor

logger = logging.getLogger(__name__)

class TagSystemAdapter:
    """태그 시스템 어댑터 - 기존 HMM 시스템을 대체"""
    
    def __init__(self, db_path: str = None):
        if db_path:
            self.engine = create_engine(f'sqlite:///{db_path}')
        else:
            self.engine = None
            
        self.tag_mapper = TagMapper()
        self.state_classifier = TagStateClassifier()
        self.o_tag_processor = OTagProcessor()
        
        # 기존 태그 매핑 로드
        self._load_existing_mappings()
    
    def _load_existing_mappings(self):
        """기존 location_tag_mapping 테이블에서 매핑 로드"""
        if not self.engine:
            return
            
        try:
            query = text("""
                SELECT location_code, tag_code, mapping_rule
                FROM location_tag_mapping
                WHERE is_active = 1
            """)
            
            with self.engine.connect() as conn:
                result = conn.execute(query)
                
                # 캐시에 로드
                for row in result:
                    cache_key = f"{row.location_code}_"
                    self.tag_mapper.location_cache[cache_key] = row.tag_code
                    
            logger.info(f"{len(self.tag_mapper.location_cache)}개 기존 매핑 로드됨")
            
        except Exception as e:
            logger.error(f"기존 매핑 로드 중 오류: {e}")
    
    def process_tag_data(self, employee_id: str, date: datetime) -> Dict:
        """특정 직원의 하루 태그 데이터 처리"""
        # 태그 데이터 로드
        tag_sequence = self._load_tag_sequence(employee_id, date)
        
        if not tag_sequence:
            logger.warning(f"{employee_id}의 {date.date()} 태그 데이터 없음")
            return {
                'employee_id': employee_id,
                'date': date,
                'tag_count': 0,
                'states': [],
                'work_time_minutes': 0
            }
        
        # O 태그 추출 및 병합
        o_tags = self._extract_o_tags(employee_id, date)
        if o_tags:
            tag_sequence = self.o_tag_processor.merge_o_tags_with_tag_sequence(
                tag_sequence, o_tags
            )
        
        # 상태 분류
        classified_sequence = self.state_classifier.classify_sequence(tag_sequence)
        
        # 업무 시간 계산
        work_periods = self.o_tag_processor.identify_work_periods_with_o_tags(
            classified_sequence
        )
        work_time = self.o_tag_processor.calculate_actual_work_time(work_periods)
        
        # 통계 생성
        state_stats = self._calculate_state_statistics(classified_sequence)
        
        return {
            'employee_id': employee_id,
            'date': date,
            'tag_count': len(tag_sequence),
            'states': classified_sequence,
            'work_time_minutes': work_time['confirmed_work_minutes'],
            'total_work_minutes': work_time['total_work_minutes'],
            'work_confidence': work_time['work_confidence'],
            'state_statistics': state_stats,
            'anomalies': self._extract_anomalies(classified_sequence)
        }
    
    def _load_tag_sequence(self, employee_id: str, date: datetime) -> List[Dict]:
        """데이터베이스에서 태그 시퀀스 로드"""
        if not self.engine:
            return []
            
        query = text("""
            SELECT 
                출입시각 as timestamp,
                DR_NO as location_code,
                DR_NM as location_name,
                INOUT_GB as inout_type
            FROM tag_data
            WHERE 사번 = :employee_id
            AND DATE(ENTE_DT) = DATE(:date)
            ORDER BY 출입시각
        """)
        
        with self.engine.connect() as conn:
            result = conn.execute(query, {
                'employee_id': employee_id,
                'date': date
            })
            
            tag_sequence = []
            for row in result:
                # 위치를 태그로 매핑
                tag_code = self.tag_mapper.map_location_to_tag(
                    row.location_code, 
                    row.location_name
                )
                
                tag_sequence.append({
                    'timestamp': pd.to_datetime(row.timestamp),
                    'location_code': row.location_code,
                    'location_name': row.location_name,
                    'tag_code': tag_code,
                    'inout_type': row.inout_type
                })
            
            return tag_sequence
    
    def _extract_o_tags(self, employee_id: str, date: datetime) -> List[Dict]:
        """O 태그 추출 (ABC 데이터 등)"""
        if not self.engine:
            return []
            
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=self.engine)
        session = Session()
        
        try:
            self.o_tag_processor.session = session
            o_tags = self.o_tag_processor.extract_o_tags_from_abc_data(
                employee_id, date
            )
            return o_tags
        finally:
            session.close()
    
    def _calculate_state_statistics(self, classified_sequence: List[Dict]) -> Dict:
        """상태별 통계 계산"""
        state_durations = {}
        state_counts = {}
        
        for i, item in enumerate(classified_sequence):
            state = item['state']
            duration = item.get('duration_minutes', 0)
            
            # 카운트
            state_counts[state] = state_counts.get(state, 0) + 1
            
            # 지속시간
            if duration > 0:
                state_durations[state] = state_durations.get(state, 0) + duration
        
        # 백분율 계산
        total_duration = sum(state_durations.values())
        state_percentages = {}
        
        if total_duration > 0:
            for state, duration in state_durations.items():
                state_percentages[state] = (duration / total_duration) * 100
        
        return {
            'counts': state_counts,
            'durations': state_durations,
            'percentages': state_percentages
        }
    
    def _extract_anomalies(self, classified_sequence: List[Dict]) -> List[Dict]:
        """이상 패턴 추출"""
        anomalies = []
        
        for item in classified_sequence:
            if 'anomaly' in item:
                anomalies.append({
                    'timestamp': item['timestamp'],
                    'type': item['anomaly'],
                    'confidence': item.get('anomaly_confidence', 0),
                    'tag_code': item['tag_code'],
                    'state': item['state']
                })
        
        return anomalies
    
    def get_hmm_compatible_output(self, result: Dict) -> List[str]:
        """기존 HMM 시스템과 호환되는 출력 생성"""
        # HMM 상태명으로 변환
        state_mapping = {
            '업무': 'WORK',
            '업무(확실)': 'FOCUSED_WORK',
            '준비': 'WORK_PREPARATION', 
            '회의': 'MEETING',
            '교육': 'MEETING',  # HMM에는 교육이 없으므로 회의로 매핑
            '휴게': 'REST',
            '식사': 'LUNCH',  # 시간대에 따라 BREAKFAST, DINNER 등으로 세분화 필요
            '경유': 'MOVEMENT',
            '출입(IN)': 'CLOCK_IN',
            '출입(OUT)': 'CLOCK_OUT',
            '비업무': 'NON_WORK'
        }
        
        hmm_states = []
        for item in result.get('states', []):
            state = item['state']
            hmm_state = state_mapping.get(state, 'MOVEMENT')
            
            # 식사 시간대 구분
            if state == '식사' and 'timestamp' in item:
                hour = item['timestamp'].hour
                if 6 <= hour < 9:
                    hmm_state = 'BREAKFAST'
                elif 11 <= hour < 14:
                    hmm_state = 'LUNCH'
                elif 17 <= hour < 20:
                    hmm_state = 'DINNER'
                elif hour >= 23 or hour < 2:
                    hmm_state = 'MIDNIGHT_MEAL'
            
            hmm_states.append(hmm_state)
        
        return hmm_states