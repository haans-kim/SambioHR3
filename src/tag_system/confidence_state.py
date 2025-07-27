"""
신뢰도 기반 상태 표현 시스템
태그 기반 활동 분류의 신뢰도와 판단 근거를 추적
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import json


class EvidenceType(Enum):
    """증거 유형 정의"""
    RULE = "rule"              # 확정적 규칙
    PROBABILITY = "probability" # 확률적 추론
    CONTEXT = "context"        # 컨텍스트 보정
    

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


@dataclass
class Evidence:
    """상태 판단 근거"""
    type: EvidenceType
    description: str
    weight: float  # 0.0 ~ 1.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'type': self.type.value,
            'description': self.description,
            'weight': self.weight,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Evidence':
        """딕셔너리에서 생성"""
        return cls(
            type=EvidenceType(data['type']),
            description=data['description'],
            weight=data['weight'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            metadata=data.get('metadata', {})
        )


@dataclass
class StateWithConfidence:
    """신뢰도를 포함한 상태 정보"""
    state: ActivityState
    confidence: float  # 0.0 ~ 1.0
    evidence: List[Evidence] = field(default_factory=list)
    alternative_states: List[Tuple[ActivityState, float]] = field(default_factory=list)
    tag_sequence: List[str] = field(default_factory=list)  # 판단에 사용된 태그 시퀀스
    
    def __post_init__(self):
        """초기화 후 유효성 검사"""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0 and 1, got {self.confidence}")
        
        # 대안 상태들의 신뢰도도 검사
        for alt_state, alt_conf in self.alternative_states:
            if not 0.0 <= alt_conf <= 1.0:
                raise ValueError(f"Alternative confidence must be between 0 and 1, got {alt_conf}")
    
    @property
    def is_confident(self) -> bool:
        """높은 신뢰도 여부 (기본 임계값: 0.8)"""
        return self.confidence >= 0.8
    
    @property
    def is_uncertain(self) -> bool:
        """불확실한 상태 여부 (신뢰도 < 0.6)"""
        return self.confidence < 0.6
    
    @property
    def primary_evidence_type(self) -> Optional[EvidenceType]:
        """가장 영향력 있는 증거 유형"""
        if not self.evidence:
            return None
        return max(self.evidence, key=lambda e: e.weight).type
    
    def add_evidence(self, evidence: Evidence) -> None:
        """증거 추가"""
        self.evidence.append(evidence)
        # 신뢰도 재계산 (가중 평균)
        if self.evidence:
            total_weight = sum(e.weight for e in self.evidence)
            if total_weight > 0:
                weighted_confidence = sum(e.weight * self.confidence for e in self.evidence) / total_weight
                self.confidence = min(1.0, weighted_confidence)
    
    def get_evidence_by_type(self, evidence_type: EvidenceType) -> List[Evidence]:
        """특정 유형의 증거만 반환"""
        return [e for e in self.evidence if e.type == evidence_type]
    
    def merge_with(self, other: 'StateWithConfidence') -> 'StateWithConfidence':
        """다른 StateWithConfidence와 병합"""
        if self.state != other.state:
            # 다른 상태인 경우, 더 높은 신뢰도를 가진 것을 선택
            if other.confidence > self.confidence:
                return other
            return self
        
        # 같은 상태인 경우, 증거를 합치고 신뢰도를 평균
        merged_evidence = self.evidence + other.evidence
        merged_confidence = (self.confidence + other.confidence) / 2
        
        # 대안 상태들도 병합
        alt_states_dict = {}
        for state, conf in self.alternative_states + other.alternative_states:
            if state in alt_states_dict:
                alt_states_dict[state] = (alt_states_dict[state] + conf) / 2
            else:
                alt_states_dict[state] = conf
        
        merged_alternatives = sorted(alt_states_dict.items(), key=lambda x: x[1], reverse=True)
        
        return StateWithConfidence(
            state=self.state,
            confidence=merged_confidence,
            evidence=merged_evidence,
            alternative_states=merged_alternatives,
            tag_sequence=self.tag_sequence + other.tag_sequence
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (JSON 직렬화 가능)"""
        return {
            'state': self.state.value,
            'confidence': round(self.confidence, 3),
            'is_confident': self.is_confident,
            'is_uncertain': self.is_uncertain,
            'evidence': [e.to_dict() for e in self.evidence],
            'alternative_states': [
                {'state': s.value, 'confidence': round(c, 3)} 
                for s, c in self.alternative_states
            ],
            'tag_sequence': self.tag_sequence,
            'primary_evidence_type': self.primary_evidence_type.value if self.primary_evidence_type else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StateWithConfidence':
        """딕셔너리에서 생성"""
        return cls(
            state=ActivityState(data['state']),
            confidence=data['confidence'],
            evidence=[Evidence.from_dict(e) for e in data.get('evidence', [])],
            alternative_states=[
                (ActivityState(alt['state']), alt['confidence']) 
                for alt in data.get('alternative_states', [])
            ],
            tag_sequence=data.get('tag_sequence', [])
        )
    
    def to_json(self) -> str:
        """JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'StateWithConfidence':
        """JSON 문자열에서 생성"""
        return cls.from_dict(json.loads(json_str))
    
    def __str__(self) -> str:
        """문자열 표현"""
        alt_states_str = ", ".join([f"{s.value}({c:.2f})" for s, c in self.alternative_states[:2]])
        evidence_summary = f"{len(self.evidence)} evidence(s)"
        return (f"State: {self.state.value} (confidence: {self.confidence:.2f}) "
                f"[{evidence_summary}] "
                f"Alternatives: [{alt_states_str}]")
    
    def __repr__(self) -> str:
        """개발자용 표현"""
        return (f"StateWithConfidence(state={self.state.name}, "
                f"confidence={self.confidence:.3f}, "
                f"evidence_count={len(self.evidence)}, "
                f"alternatives={len(self.alternative_states)})")


class ConfidenceCalculator:
    """신뢰도 계산 유틸리티"""
    
    @staticmethod
    def calculate_weighted_confidence(evidences: List[Evidence]) -> float:
        """증거들의 가중 평균 신뢰도 계산"""
        if not evidences:
            return 0.0
        
        total_weight = sum(e.weight for e in evidences)
        if total_weight == 0:
            return 0.0
        
        # 각 증거 유형별 기본 신뢰도
        base_confidence = {
            EvidenceType.RULE: 0.95,
            EvidenceType.PROBABILITY: 0.75,
            EvidenceType.CONTEXT: 0.65
        }
        
        weighted_sum = sum(
            e.weight * base_confidence.get(e.type, 0.5) 
            for e in evidences
        )
        
        return min(1.0, weighted_sum / total_weight)
    
    @staticmethod
    def adjust_confidence_by_consistency(
        states: List[StateWithConfidence], 
        window_size: int = 5
    ) -> List[StateWithConfidence]:
        """
        연속된 상태들의 일관성을 기반으로 신뢰도 조정
        일관된 패턴이면 신뢰도 상승, 불규칙하면 하락
        """
        if len(states) < window_size:
            return states
        
        adjusted_states = []
        
        for i, current in enumerate(states):
            # 주변 상태들 확인
            start = max(0, i - window_size // 2)
            end = min(len(states), i + window_size // 2 + 1)
            window = states[start:end]
            
            # 같은 상태의 비율 계산
            same_state_count = sum(1 for s in window if s.state == current.state)
            consistency_ratio = same_state_count / len(window)
            
            # 신뢰도 조정 (일관성이 높으면 최대 10% 상승, 낮으면 최대 10% 하락)
            adjustment = (consistency_ratio - 0.5) * 0.2
            adjusted_confidence = max(0.0, min(1.0, current.confidence + adjustment))
            
            # 조정된 상태 생성
            adjusted = StateWithConfidence(
                state=current.state,
                confidence=adjusted_confidence,
                evidence=current.evidence + [
                    Evidence(
                        type=EvidenceType.CONTEXT,
                        description=f"일관성 조정 (ratio={consistency_ratio:.2f})",
                        weight=0.3,
                        metadata={'consistency_ratio': consistency_ratio}
                    )
                ],
                alternative_states=current.alternative_states,
                tag_sequence=current.tag_sequence
            )
            
            adjusted_states.append(adjusted)
        
        return adjusted_states


# 사용 예시를 위한 헬퍼 함수들
def create_rule_based_state(state: ActivityState, rule_description: str) -> StateWithConfidence:
    """규칙 기반 상태 생성 헬퍼"""
    return StateWithConfidence(
        state=state,
        confidence=0.95,
        evidence=[
            Evidence(
                type=EvidenceType.RULE,
                description=rule_description,
                weight=1.0
            )
        ]
    )


def create_probabilistic_state(
    state: ActivityState, 
    confidence: float,
    description: str,
    alternatives: List[Tuple[ActivityState, float]] = None
) -> StateWithConfidence:
    """확률 기반 상태 생성 헬퍼"""
    return StateWithConfidence(
        state=state,
        confidence=confidence,
        evidence=[
            Evidence(
                type=EvidenceType.PROBABILITY,
                description=description,
                weight=0.8
            )
        ],
        alternative_states=alternatives or []
    )