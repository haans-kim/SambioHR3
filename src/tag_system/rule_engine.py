"""
확정적 규칙 기반 분류 엔진
100% 확실한 상태를 즉시 확정하는 규칙 시스템
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum

from .confidence_state import (
    StateWithConfidence, Evidence, EvidenceType, 
    ActivityState, create_rule_based_state
)
from ..utils.time_normalizer import TimeNormalizer, MealType

logger = logging.getLogger(__name__)


class RulePriority(Enum):
    """규칙 우선순위"""
    CRITICAL = 1     # O 태그 같은 최우선 규칙
    HIGH = 2         # 식사, 출퇴근 등 명확한 규칙
    MEDIUM = 3       # 일반 패턴
    LOW = 4          # 기본 규칙


@dataclass
class RuleConfig:
    """규칙 설정"""
    # 식사 시간 설정
    meal_max_duration_minutes: int = 60  # M1 최대 식사 시간
    takeout_fixed_duration_minutes: int = 10  # M2 테이크아웃 고정 시간
    
    # 시간 임계값
    short_duration_threshold_minutes: int = 5  # 경유로 판단하는 짧은 체류
    long_duration_threshold_minutes: int = 120  # 장시간 체류
    
    # 신뢰도 설정
    critical_confidence: float = 0.98
    high_confidence: float = 0.95
    medium_confidence: float = 0.90


class DeterministicRuleEngine:
    """확정적 규칙 기반 분류 엔진"""
    
    def __init__(self, config: Optional[RuleConfig] = None):
        self.config = config or RuleConfig()
        self.time_normalizer = TimeNormalizer()
        self.rules = self._initialize_rules()
    
    def _initialize_rules(self) -> Dict[RulePriority, List]:
        """우선순위별 규칙 초기화"""
        return {
            RulePriority.CRITICAL: [
                self._check_o_tag_rule,
            ],
            RulePriority.HIGH: [
                self._check_meal_rule,
                self._check_entry_exit_rule,
            ],
            RulePriority.MEDIUM: [
                self._check_meeting_rule,
                self._check_education_rule,
                self._check_preparation_rule,
            ],
            RulePriority.LOW: [
                self._check_rest_rule,
                self._check_transit_rule,
            ]
        }
    
    def apply_rules(self, tag_data: Dict) -> Optional[StateWithConfidence]:
        """
        규칙을 적용하여 상태 분류
        
        Args:
            tag_data: {
                'tag': str,                    # 현재 태그 (G1, M1, O 등)
                'previous_tag': Optional[str], # 이전 태그
                'next_tag': Optional[str],     # 다음 태그
                'timestamp': datetime,         # 현재 시간
                'duration_minutes': float,     # 체류 시간 (분)
                'to_next_minutes': float,      # 다음 태그까지 시간 (분)
                'has_o_tag': bool,            # O 태그 존재 여부
                'is_entry_gate': bool,        # T2(입문) 여부
                'shift_type': str,            # 근무 유형
            }
        
        Returns:
            StateWithConfidence or None
        """
        # 우선순위 순으로 규칙 적용
        for priority in RulePriority:
            for rule_func in self.rules[priority]:
                result = rule_func(tag_data)
                if result:
                    logger.debug(f"규칙 적용: {rule_func.__name__} -> {result.state.value}")
                    return result
        
        return None
    
    def _check_o_tag_rule(self, tag_data: Dict) -> Optional[StateWithConfidence]:
        """O 태그 규칙 - 최우선"""
        if tag_data.get('has_o_tag') or tag_data.get('tag') == 'O':
            return StateWithConfidence(
                state=ActivityState.WORK_CONFIRMED,
                confidence=self.config.critical_confidence,
                evidence=[
                    Evidence(
                        type=EvidenceType.RULE,
                        description="O 태그 존재로 업무 확정",
                        weight=1.0,
                        metadata={'rule': 'o_tag', 'priority': 'critical'}
                    )
                ],
                tag_sequence=[tag_data.get('tag')]
            )
        
        # O → 다른 태그 전환
        if tag_data.get('previous_tag') == 'O':
            current_tag = tag_data.get('tag')
            
            # O → M1: 업무 후 식사
            if current_tag == 'M1':
                return None  # 식사 규칙에서 처리
            
            # O → T2/T3: 업무 후 퇴근
            elif current_tag in ['T2', 'T3']:
                return None  # 출퇴근 규칙에서 처리
            
            # O → G1/G2/G3: 업무 지속
            elif current_tag in ['G1', 'G2', 'G3']:
                return StateWithConfidence(
                    state=ActivityState.WORK,
                    confidence=self.config.high_confidence,
                    evidence=[
                        Evidence(
                            type=EvidenceType.RULE,
                            description="O 태그 후 업무 공간 이동",
                            weight=0.95,
                            metadata={'rule': 'o_to_work_area'}
                        )
                    ],
                    tag_sequence=['O', current_tag]
                )
        
        return None
    
    def _check_meal_rule(self, tag_data: Dict) -> Optional[StateWithConfidence]:
        """식사 규칙"""
        current_tag = tag_data.get('tag')
        timestamp = tag_data.get('timestamp')
        
        # M1: 현장 식사
        if current_tag == 'M1':
            # 식사 시간대 확인
            meal_type = self.time_normalizer.get_current_meal_type(timestamp)
            meal_name = self.time_normalizer.get_meal_name(meal_type)
            
            # 실제 식사 시간 계산 (다음 태그까지 또는 최대 60분)
            to_next_minutes = tag_data.get('to_next_minutes', self.config.meal_max_duration_minutes)
            actual_duration = min(to_next_minutes, self.config.meal_max_duration_minutes)
            
            return StateWithConfidence(
                state=ActivityState.MEAL,
                confidence=self.config.critical_confidence,
                evidence=[
                    Evidence(
                        type=EvidenceType.RULE,
                        description=f"M1 태그 - {meal_name} (실제 {actual_duration:.0f}분)",
                        weight=1.0,
                        metadata={
                            'rule': 'meal_m1',
                            'meal_type': meal_type.value if meal_type else 'unknown',
                            'duration_minutes': actual_duration,
                            'capped': to_next_minutes > self.config.meal_max_duration_minutes
                        }
                    )
                ],
                tag_sequence=[current_tag]
            )
        
        # M2: 테이크아웃
        elif current_tag == 'M2':
            return StateWithConfidence(
                state=ActivityState.TRANSIT,  # 테이크아웃은 경유로 분류
                confidence=self.config.critical_confidence,
                evidence=[
                    Evidence(
                        type=EvidenceType.RULE,
                        description=f"M2 태그 - 테이크아웃 구매 (고정 {self.config.takeout_fixed_duration_minutes}분)",
                        weight=1.0,
                        metadata={
                            'rule': 'meal_m2_takeout',
                            'duration_minutes': self.config.takeout_fixed_duration_minutes,
                            'fixed_duration': True
                        }
                    )
                ],
                tag_sequence=[current_tag]
            )
        
        # M2 → N2: 테이크아웃 후 휴게실에서 식사
        elif tag_data.get('previous_tag') == 'M2' and current_tag == 'N2':
            return StateWithConfidence(
                state=ActivityState.REST,  # 휴게실에서 식사
                confidence=self.config.high_confidence,
                evidence=[
                    Evidence(
                        type=EvidenceType.RULE,
                        description="테이크아웃 후 휴게실 식사",
                        weight=0.9,
                        metadata={'rule': 'takeout_to_rest'}
                    )
                ],
                tag_sequence=['M2', current_tag]
            )
        
        return None
    
    def _check_entry_exit_rule(self, tag_data: Dict) -> Optional[StateWithConfidence]:
        """출입 규칙"""
        current_tag = tag_data.get('tag')
        
        if current_tag not in ['T2', 'T3']:
            return None
        
        timestamp = tag_data.get('timestamp')
        shift_type = tag_data.get('shift_type')
        is_entry_gate = tag_data.get('is_entry_gate', current_tag == 'T2')
        
        # 출입 분류
        state_str = self.time_normalizer.classify_entry_exit(
            timestamp, shift_type, is_entry_gate
        )
        
        if state_str == "출입(IN)":
            state = ActivityState.ENTRY
            description = "출근 시간대 입문"
        elif state_str == "출입(OUT)":
            state = ActivityState.EXIT
            description = "퇴근 시간대 출문"
        else:
            state = ActivityState.TRANSIT
            description = "출입문 경유"
        
        confidence = self.config.high_confidence if state != ActivityState.TRANSIT else self.config.medium_confidence
        
        return StateWithConfidence(
            state=state,
            confidence=confidence,
            evidence=[
                Evidence(
                    type=EvidenceType.RULE,
                    description=f"{current_tag} - {description}",
                    weight=0.9,
                    metadata={
                        'rule': 'entry_exit',
                        'gate_type': current_tag,
                        'shift_type': shift_type
                    }
                )
            ],
            tag_sequence=[current_tag]
        )
    
    def _check_meeting_rule(self, tag_data: Dict) -> Optional[StateWithConfidence]:
        """회의 규칙"""
        current_tag = tag_data.get('tag')
        duration_minutes = tag_data.get('duration_minutes', 0)
        
        if current_tag == 'G3':
            # G3에서 장시간 체류 → 회의
            if duration_minutes >= 30:
                return StateWithConfidence(
                    state=ActivityState.MEETING,
                    confidence=self.config.high_confidence,
                    evidence=[
                        Evidence(
                            type=EvidenceType.RULE,
                            description=f"G3 태그 - 회의 공간 ({duration_minutes:.0f}분)",
                            weight=0.9,
                            metadata={'rule': 'meeting_g3', 'duration_minutes': duration_minutes}
                        )
                    ],
                    tag_sequence=[current_tag]
                )
            # 짧은 체류는 경유
            elif duration_minutes < self.config.short_duration_threshold_minutes:
                return StateWithConfidence(
                    state=ActivityState.TRANSIT,
                    confidence=self.config.medium_confidence,
                    evidence=[
                        Evidence(
                            type=EvidenceType.RULE,
                            description=f"G3 짧은 체류 ({duration_minutes:.0f}분)",
                            weight=0.7,
                            metadata={'rule': 'meeting_g3_short'}
                        )
                    ],
                    tag_sequence=[current_tag]
                )
        
        # 교대 시간 회의 (인수인계)
        timestamp = tag_data.get('timestamp')
        is_shift_change, direction = self.time_normalizer.is_shift_change_time(timestamp)
        
        if is_shift_change and current_tag in ['G1', 'G3']:
            return StateWithConfidence(
                state=ActivityState.MEETING,
                confidence=self.config.medium_confidence,
                evidence=[
                    Evidence(
                        type=EvidenceType.RULE,
                        description=f"교대 시간 인수인계 ({direction})",
                        weight=0.8,
                        metadata={
                            'rule': 'shift_change_meeting',
                            'direction': direction
                        }
                    )
                ],
                tag_sequence=[current_tag]
            )
        
        return None
    
    def _check_education_rule(self, tag_data: Dict) -> Optional[StateWithConfidence]:
        """교육 규칙"""
        current_tag = tag_data.get('tag')
        duration_minutes = tag_data.get('duration_minutes', 0)
        
        if current_tag == 'G4':
            # G4에서 장시간 체류 → 교육
            if duration_minutes >= 60:
                return StateWithConfidence(
                    state=ActivityState.EDUCATION,
                    confidence=self.config.high_confidence,
                    evidence=[
                        Evidence(
                            type=EvidenceType.RULE,
                            description=f"G4 태그 - 교육 공간 ({duration_minutes:.0f}분)",
                            weight=0.9,
                            metadata={'rule': 'education_g4', 'duration_minutes': duration_minutes}
                        )
                    ],
                    tag_sequence=[current_tag]
                )
        
        return None
    
    def _check_preparation_rule(self, tag_data: Dict) -> Optional[StateWithConfidence]:
        """준비 규칙"""
        current_tag = tag_data.get('tag')
        previous_tag = tag_data.get('previous_tag')
        next_tag = tag_data.get('next_tag')
        
        if current_tag == 'G2':
            # T2 → G2: 출근 후 준비
            if previous_tag == 'T2':
                return StateWithConfidence(
                    state=ActivityState.PREPARATION,
                    confidence=self.config.high_confidence,
                    evidence=[
                        Evidence(
                            type=EvidenceType.RULE,
                            description="출근 후 작업 준비",
                            weight=0.9,
                            metadata={'rule': 'entry_preparation'}
                        )
                    ],
                    tag_sequence=[previous_tag, current_tag]
                )
            
            # G2 → T3: 퇴근 전 정리
            elif next_tag == 'T3':
                return StateWithConfidence(
                    state=ActivityState.PREPARATION,
                    confidence=self.config.high_confidence,
                    evidence=[
                        Evidence(
                            type=EvidenceType.RULE,
                            description="퇴근 전 정리",
                            weight=0.9,
                            metadata={'rule': 'exit_preparation'}
                        )
                    ],
                    tag_sequence=[current_tag, next_tag]
                )
        
        return None
    
    def _check_rest_rule(self, tag_data: Dict) -> Optional[StateWithConfidence]:
        """휴게 규칙"""
        current_tag = tag_data.get('tag')
        duration_minutes = tag_data.get('duration_minutes', 0)
        
        if current_tag in ['N1', 'N2']:
            # 장시간 휴게
            if duration_minutes >= 30:
                return StateWithConfidence(
                    state=ActivityState.REST,
                    confidence=self.config.medium_confidence,
                    evidence=[
                        Evidence(
                            type=EvidenceType.RULE,
                            description=f"{current_tag} - 휴게 ({duration_minutes:.0f}분)",
                            weight=0.8,
                            metadata={'rule': f'rest_{current_tag.lower()}'}
                        )
                    ],
                    tag_sequence=[current_tag]
                )
        
        return None
    
    def _check_transit_rule(self, tag_data: Dict) -> Optional[StateWithConfidence]:
        """경유 규칙"""
        current_tag = tag_data.get('tag')
        duration_minutes = tag_data.get('duration_minutes', 0)
        
        # T1: 이동 경로
        if current_tag == 'T1':
            # 짧은 체류 → 경유
            if duration_minutes < self.config.short_duration_threshold_minutes:
                return StateWithConfidence(
                    state=ActivityState.TRANSIT,
                    confidence=self.config.medium_confidence,
                    evidence=[
                        Evidence(
                            type=EvidenceType.RULE,
                            description=f"T1 - 이동 경로 ({duration_minutes:.0f}분)",
                            weight=0.7,
                            metadata={'rule': 'transit_t1'}
                        )
                    ],
                    tag_sequence=[current_tag]
                )
        
        # 모든 태그에서 매우 짧은 체류
        if duration_minutes < 2:
            return StateWithConfidence(
                state=ActivityState.TRANSIT,
                confidence=self.config.medium_confidence,
                evidence=[
                    Evidence(
                        type=EvidenceType.RULE,
                        description=f"매우 짧은 체류 ({duration_minutes:.0f}분)",
                        weight=0.6,
                        metadata={'rule': 'very_short_stay'}
                    )
                ],
                tag_sequence=[current_tag]
            )
        
        return None


# 사용 편의를 위한 헬퍼 함수
def create_rule_engine(config: Optional[RuleConfig] = None) -> DeterministicRuleEngine:
    """규칙 엔진 생성"""
    return DeterministicRuleEngine(config)


def apply_deterministic_rules(tag_data: Dict, config: Optional[RuleConfig] = None) -> Optional[StateWithConfidence]:
    """확정적 규칙 적용"""
    engine = create_rule_engine(config)
    return engine.apply_rules(tag_data)