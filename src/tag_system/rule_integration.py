"""
규칙 엔진 통합 모듈
기존 시스템과 새로운 확정적 규칙 엔진을 통합
"""

import logging
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from pathlib import Path

from .rule_engine import DeterministicRuleEngine, RuleConfig
from .rule_loader import RuleLoader, load_rule_config
from .confidence_state import StateWithConfidence, ActivityState
from ..utils.time_normalizer import TimeNormalizer, ShiftType

logger = logging.getLogger(__name__)


class RuleIntegration:
    """규칙 엔진 통합 클래스"""
    
    def __init__(self, config_path: Optional[Path] = None, use_json_config: bool = True):
        """
        Args:
            config_path: 설정 파일 경로
            use_json_config: JSON 설정 파일 사용 여부
        """
        if use_json_config:
            config = load_rule_config(config_path)
        else:
            config = RuleConfig()
        
        self.rule_engine = DeterministicRuleEngine(config)
        self.time_normalizer = TimeNormalizer()
        self.use_json_config = use_json_config
        
        logger.info(f"규칙 엔진 통합 초기화 (JSON 설정: {use_json_config})")
    
    def classify_tag_sequence(
        self, 
        tags: List[Dict],
        employee_info: Optional[Dict] = None
    ) -> List[StateWithConfidence]:
        """
        태그 시퀀스를 상태 시퀀스로 분류
        
        Args:
            tags: 태그 리스트 [{
                'tag': str,
                'timestamp': datetime,
                'location': str,
                'has_o_tag': bool (optional)
            }, ...]
            employee_info: 직원 정보 (근무 유형 등)
        
        Returns:
            StateWithConfidence 리스트
        """
        if not tags:
            return []
        
        results = []
        
        # 근무 유형 결정
        shift_type = self._determine_shift_type(tags[0]['timestamp'], employee_info)
        
        for i, tag_info in enumerate(tags):
            # 태그 데이터 준비
            tag_data = self._prepare_tag_data(
                tag_info, 
                i, 
                tags, 
                shift_type
            )
            
            # 확정적 규칙 적용
            state = self.rule_engine.apply_rules(tag_data)
            
            # 규칙에 매칭되지 않으면 None
            if state is None:
                logger.debug(f"규칙 매칭 없음: {tag_data['tag']} at {tag_data['timestamp']}")
                # 확률적 추론이나 기본값 처리는 상위 레벨에서
                results.append(None)
            else:
                results.append(state)
        
        return results
    
    def _prepare_tag_data(
        self, 
        tag_info: Dict,
        index: int,
        all_tags: List[Dict],
        shift_type: ShiftType
    ) -> Dict:
        """태그 데이터를 규칙 엔진용으로 준비"""
        tag_data = {
            'tag': tag_info['tag'],
            'timestamp': tag_info['timestamp'],
            'shift_type': shift_type,
            'has_o_tag': tag_info.get('has_o_tag', tag_info['tag'] == 'O')
        }
        
        # 이전/다음 태그
        if index > 0:
            tag_data['previous_tag'] = all_tags[index - 1]['tag']
        
        if index < len(all_tags) - 1:
            tag_data['next_tag'] = all_tags[index + 1]['tag']
            
            # 다음 태그까지 시간 계산
            next_time = all_tags[index + 1]['timestamp']
            duration = self.time_normalizer.calculate_time_difference(
                tag_info['timestamp'], 
                next_time
            )
            tag_data['to_next_minutes'] = duration.total_seconds() / 60
        
        # 체류 시간 (이전 태그부터 현재까지)
        if index > 0:
            prev_time = all_tags[index - 1]['timestamp']
            duration = self.time_normalizer.calculate_time_difference(
                prev_time,
                tag_info['timestamp']
            )
            tag_data['duration_minutes'] = duration.total_seconds() / 60
        else:
            tag_data['duration_minutes'] = 0
        
        # 출입문 구분
        tag_data['is_entry_gate'] = tag_info['tag'] == 'T2'
        
        return tag_data
    
    def _determine_shift_type(
        self, 
        first_timestamp: datetime,
        employee_info: Optional[Dict]
    ) -> ShiftType:
        """근무 유형 결정"""
        if employee_info and 'shift_type' in employee_info:
            shift_str = employee_info['shift_type']
            try:
                return ShiftType(shift_str)
            except ValueError:
                pass
        
        # 첫 태그 시간으로 자동 감지
        return self.time_normalizer.detect_shift_type(first_timestamp)
    
    def get_meal_duration(self, tag: str, to_next_minutes: Optional[float] = None) -> float:
        """식사 시간 계산"""
        config = self.rule_engine.config
        
        if tag == 'M1':
            # 현장 식사: 다음 태그까지 또는 최대 시간
            if to_next_minutes is not None:
                return min(to_next_minutes, config.meal_max_duration_minutes)
            return config.meal_max_duration_minutes
        
        elif tag == 'M2':
            # 테이크아웃: 고정 시간
            return config.takeout_fixed_duration_minutes
        
        return 0
    
    def update_config(self, **kwargs) -> bool:
        """설정 업데이트"""
        try:
            # 현재 설정 복사
            current_config = self.rule_engine.config
            
            # 업데이트
            for key, value in kwargs.items():
                if hasattr(current_config, key):
                    setattr(current_config, key, value)
                else:
                    logger.warning(f"알 수 없는 설정: {key}")
            
            # JSON 파일에 저장 (사용 중인 경우)
            if self.use_json_config:
                loader = RuleLoader()
                return loader.save_config(current_config)
            
            return True
            
        except Exception as e:
            logger.error(f"설정 업데이트 오류: {e}")
            return False
    
    def get_confidence_threshold(self, priority: str = 'medium') -> float:
        """우선순위별 신뢰도 임계값 반환"""
        config = self.rule_engine.config
        
        thresholds = {
            'critical': config.critical_confidence,
            'high': config.high_confidence,
            'medium': config.medium_confidence,
            'low': 0.5  # 낮은 우선순위 기본값
        }
        
        return thresholds.get(priority.lower(), config.medium_confidence)
    
    def validate_sequence(self, states: List[StateWithConfidence]) -> Dict[str, any]:
        """상태 시퀀스 검증"""
        validation_result = {
            'valid': True,
            'issues': [],
            'statistics': {
                'total_states': len(states),
                'confirmed_states': 0,
                'uncertain_states': 0,
                'null_states': 0
            }
        }
        
        for i, state in enumerate(states):
            if state is None:
                validation_result['statistics']['null_states'] += 1
                continue
            
            # 통계
            if state.is_confident:
                validation_result['statistics']['confirmed_states'] += 1
            elif state.is_uncertain:
                validation_result['statistics']['uncertain_states'] += 1
            
            # 검증 규칙
            # 1. 출근 후 즉시 퇴근 불가
            if i > 0 and states[i-1] and state:
                if (states[i-1].state == ActivityState.ENTRY and 
                    state.state == ActivityState.EXIT):
                    validation_result['issues'].append(
                        f"인덱스 {i}: 출근 직후 퇴근"
                    )
                    validation_result['valid'] = False
            
            # 2. 업무 확정 후 갑작스런 비업무
            if i > 0 and states[i-1] and state:
                if (states[i-1].state == ActivityState.WORK_CONFIRMED and 
                    state.state == ActivityState.NON_WORK and
                    state.confidence < 0.8):
                    validation_result['issues'].append(
                        f"인덱스 {i}: 업무 확정 후 불확실한 비업무"
                    )
        
        return validation_result


# 싱글톤 인스턴스
_integration_instance = None


def get_rule_integration(
    config_path: Optional[Path] = None,
    use_json_config: bool = True,
    force_new: bool = False
) -> RuleIntegration:
    """규칙 통합 인스턴스 반환"""
    global _integration_instance
    
    if force_new or _integration_instance is None:
        _integration_instance = RuleIntegration(config_path, use_json_config)
    
    return _integration_instance


def apply_rules_to_tags(
    tags: List[Dict],
    employee_info: Optional[Dict] = None,
    config_path: Optional[Path] = None
) -> List[StateWithConfidence]:
    """태그에 규칙 적용 (간편 함수)"""
    integration = get_rule_integration(config_path)
    return integration.classify_tag_sequence(tags, employee_info)