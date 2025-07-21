"""
조건부 전이 엔진
룰 기반으로 상태 전이를 예측하고 신뢰도를 계산
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime
import logging
from pathlib import Path

from .rule_manager import RuleManager, TransitionRule
from ..hmm import HMMModel

class ConditionalTransitionEngine:
    """조건부 전이 엔진"""
    
    def __init__(self, rule_manager: Optional[RuleManager] = None):
        self.rule_manager = rule_manager or RuleManager()
        self.logger = logging.getLogger(__name__)
        self.hmm_model = HMMModel()
        
        # 캐시
        self.prediction_cache = {}
        
    def predict_next_states(self, 
                           current_state: str, 
                           context: Dict[str, Any],
                           top_k: int = 5) -> List[Dict[str, Any]]:
        """
        다음 상태 예측
        
        Args:
            current_state: 현재 상태
            context: 상황 정보
            top_k: 상위 k개 예측 반환
            
        Returns:
            예측 결과 리스트 [{state, probability, confidence, rule_id}, ...]
        """
        # 적용 가능한 룰 찾기
        applicable_rules = self.rule_manager.get_applicable_rules(current_state, context)
        
        # 룰 기반 예측
        rule_predictions = self._apply_rules(applicable_rules, context)
        
        # HMM 기반 예측 (폴백)
        hmm_predictions = self._get_hmm_predictions(current_state)
        
        # 예측 통합
        combined_predictions = self._combine_predictions(
            rule_predictions, hmm_predictions, context
        )
        
        # 상위 k개 반환
        combined_predictions.sort(key=lambda x: x['probability'], reverse=True)
        return combined_predictions[:top_k]
    
    def _apply_rules(self, rules: List[TransitionRule], 
                    context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """룰 적용하여 예측 생성"""
        predictions = []
        
        for rule in rules:
            # 조건별 가중치 계산
            condition_weight = self._calculate_condition_weight(rule.conditions, context)
            
            # 최종 확률 = 기본 확률 * 조건 가중치
            adjusted_probability = rule.base_probability * condition_weight
            
            prediction = {
                'state': rule.to_state,
                'probability': adjusted_probability,
                'confidence': rule.confidence,
                'rule_id': rule.id,
                'source': 'rule'
            }
            
            predictions.append(prediction)
        
        return predictions
    
    def _calculate_condition_weight(self, conditions: List[Dict[str, Any]], 
                                  context: Dict[str, Any]) -> float:
        """
        조건 가중치 계산
        모든 조건이 만족되면 1.0, 일부만 만족하면 비례하여 감소
        """
        if not conditions:
            return 1.0
        
        satisfied_count = 0
        total_weight = 0
        
        for condition in conditions:
            weight = self._evaluate_condition_strength(condition, context)
            total_weight += weight
            satisfied_count += 1
        
        if satisfied_count == 0:
            return 0.0
        
        return total_weight / satisfied_count
    
    def _evaluate_condition_strength(self, condition: Dict[str, Any], 
                                   context: Dict[str, Any]) -> float:
        """
        개별 조건의 강도 평가 (0.0 ~ 1.0)
        """
        cond_type = condition.get('type')
        
        if cond_type == 'time':
            return self._evaluate_time_condition(condition, context)
        elif cond_type == 'location':
            return self._evaluate_location_condition(condition, context)
        elif cond_type == 'duration':
            return self._evaluate_duration_condition(condition, context)
        elif cond_type == 'tag_code':
            return self._evaluate_tag_condition(condition, context)
        else:
            return 0.5  # 알 수 없는 조건은 중간값
    
    def _evaluate_time_condition(self, condition: Dict[str, Any], 
                               context: Dict[str, Any]) -> float:
        """시간 조건 평가"""
        if 'current_time' not in context:
            return 0.0
        
        current_time = pd.to_datetime(context['current_time'])
        start_time = pd.to_datetime(condition['start'], format='%H:%M')
        end_time = pd.to_datetime(condition['end'], format='%H:%M')
        
        # 현재 시간을 같은 날짜로 정규화
        base_date = current_time.date()
        current_normalized = pd.Timestamp.combine(base_date, current_time.time())
        start_normalized = pd.Timestamp.combine(base_date, start_time.time())
        end_normalized = pd.Timestamp.combine(base_date, end_time.time())
        
        # 자정을 넘는 경우 처리
        if end_normalized < start_normalized:
            end_normalized += pd.Timedelta(days=1)
            if current_normalized < start_normalized:
                current_normalized += pd.Timedelta(days=1)
        
        # 시간 범위 내에 있는지 확인
        if start_normalized <= current_normalized <= end_normalized:
            # 중간 지점에 가까울수록 높은 가중치
            total_duration = (end_normalized - start_normalized).total_seconds()
            elapsed = (current_normalized - start_normalized).total_seconds()
            
            # 가우시안 형태의 가중치 (중간이 1.0)
            center = total_duration / 2
            sigma = total_duration / 4
            weight = np.exp(-((elapsed - center) ** 2) / (2 * sigma ** 2))
            
            return max(0.7, weight)  # 최소 0.7
        else:
            # 시간 범위 밖이면 거리에 따라 감소
            if current_normalized < start_normalized:
                distance = (start_normalized - current_normalized).total_seconds() / 3600
            else:
                distance = (current_normalized - end_normalized).total_seconds() / 3600
            
            # 1시간당 0.1씩 감소
            return max(0.0, 0.5 - distance * 0.1)
    
    def _evaluate_location_condition(self, condition: Dict[str, Any], 
                                   context: Dict[str, Any]) -> float:
        """위치 조건 평가"""
        if 'location' not in context:
            return 0.0
        
        pattern = condition['pattern'].upper()
        location = context['location'].upper()
        
        if pattern in location:
            return 1.0  # 정확히 일치
        elif any(word in location for word in pattern.split()):
            return 0.7  # 부분 일치
        else:
            return 0.0
    
    def _evaluate_duration_condition(self, condition: Dict[str, Any], 
                                   context: Dict[str, Any]) -> float:
        """체류시간 조건 평가"""
        if 'duration_minutes' not in context:
            return 0.0
        
        min_duration = condition['min_duration']
        actual_duration = context['duration_minutes']
        
        if actual_duration >= min_duration:
            # 조건 충족, 초과할수록 가중치 증가 (최대 1.0)
            excess_ratio = (actual_duration - min_duration) / min_duration
            return min(1.0, 0.7 + excess_ratio * 0.3)
        else:
            # 미충족, 근접할수록 높은 가중치
            ratio = actual_duration / min_duration
            return ratio * 0.5
    
    def _evaluate_tag_condition(self, condition: Dict[str, Any], 
                              context: Dict[str, Any]) -> float:
        """태그 조건 평가"""
        if 'tag_code' not in context:
            return 0.0
        
        return 1.0 if context['tag_code'] == condition['code'] else 0.0
    
    def _get_hmm_predictions(self, current_state: str) -> List[Dict[str, Any]]:
        """HMM 기반 예측 (폴백)"""
        predictions = []
        
        if self.hmm_model.transition_matrix is None:
            return predictions
        
        try:
            current_idx = self.hmm_model.state_to_index[current_state]
            transition_probs = self.hmm_model.transition_matrix[current_idx]
            
            for next_idx, prob in enumerate(transition_probs):
                if prob > 0.01:  # 최소 확률 임계값
                    next_state = self.hmm_model.index_to_state[next_idx]
                    predictions.append({
                        'state': next_state,
                        'probability': prob,
                        'confidence': 70,  # HMM 기본 신뢰도
                        'rule_id': None,
                        'source': 'hmm'
                    })
        except Exception as e:
            self.logger.warning(f"HMM 예측 실패: {e}")
        
        return predictions
    
    def _combine_predictions(self, 
                           rule_predictions: List[Dict[str, Any]],
                           hmm_predictions: List[Dict[str, Any]],
                           context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """룰 기반과 HMM 예측 통합"""
        combined = {}
        
        # 룰 기반 예측 추가 (우선순위 높음)
        for pred in rule_predictions:
            state = pred['state']
            if state not in combined or pred['confidence'] > combined[state]['confidence']:
                combined[state] = pred
        
        # HMM 예측 추가 (룰이 없는 경우만)
        for pred in hmm_predictions:
            state = pred['state']
            if state not in combined:
                combined[state] = pred
        
        # 확률 정규화
        predictions = list(combined.values())
        total_prob = sum(p['probability'] for p in predictions)
        
        if total_prob > 0:
            for pred in predictions:
                pred['probability'] /= total_prob
        
        return predictions
    
    def apply_transition(self, 
                        from_state: str, 
                        to_state: str,
                        context: Dict[str, Any]) -> Dict[str, Any]:
        """
        실제 전이 적용 및 기록
        
        Returns:
            전이 정보 (확률, 신뢰도, 적용된 룰 등)
        """
        # 예측 가져오기
        predictions = self.predict_next_states(from_state, context)
        
        # 실제 전이와 매칭
        transition_info = {
            'from_state': from_state,
            'to_state': to_state,
            'timestamp': datetime.now().isoformat(),
            'context': context
        }
        
        # 예측에서 찾기
        for pred in predictions:
            if pred['state'] == to_state:
                transition_info.update({
                    'probability': pred['probability'],
                    'confidence': pred['confidence'],
                    'rule_id': pred.get('rule_id'),
                    'source': pred['source']
                })
                break
        else:
            # 예측에 없는 경우
            transition_info.update({
                'probability': 0.01,
                'confidence': 50,
                'rule_id': None,
                'source': 'unexpected'
            })
        
        # 기록 (향후 학습에 사용)
        self._record_transition(transition_info)
        
        return transition_info
    
    def _record_transition(self, transition_info: Dict[str, Any]):
        """전이 기록 (향후 학습용)"""
        # TODO: 데이터베이스나 파일에 저장
        self.logger.info(f"전이 기록: {transition_info['from_state']} → {transition_info['to_state']}")
    
    def update_hmm_from_rules(self):
        """룰 기반으로 HMM 파라미터 업데이트"""
        rules = self.rule_manager.load_all_rules()
        active_rules = [r for r in rules if r.is_active]
        
        if not active_rules:
            return
        
        # 전이 행렬 초기화
        n_states = self.hmm_model.n_states
        transition_matrix = np.full((n_states, n_states), 0.01)  # 최소값
        
        # 룰 기반 확률 설정
        for rule in active_rules:
            try:
                from_idx = self.hmm_model.state_to_index[rule.from_state]
                to_idx = self.hmm_model.state_to_index[rule.to_state]
                
                # 신뢰도를 가중치로 사용
                weight = rule.confidence / 100.0
                transition_matrix[from_idx, to_idx] = (
                    rule.base_probability * weight + 
                    transition_matrix[from_idx, to_idx] * (1 - weight)
                )
            except KeyError:
                self.logger.warning(f"알 수 없는 상태: {rule.from_state} or {rule.to_state}")
        
        # 행 정규화
        for i in range(n_states):
            row_sum = transition_matrix[i].sum()
            if row_sum > 0:
                transition_matrix[i] /= row_sum
        
        self.hmm_model.transition_matrix = transition_matrix
        self.logger.info("HMM 파라미터 업데이트 완료")
    
    def get_transition_graph(self) -> Dict[str, Any]:
        """전이 그래프 데이터 생성 (시각화용)"""
        rules = self.rule_manager.load_all_rules()
        active_rules = [r for r in rules if r.is_active]
        
        nodes = set()
        edges = []
        
        for rule in active_rules:
            nodes.add(rule.from_state)
            nodes.add(rule.to_state)
            
            edges.append({
                'source': rule.from_state,
                'target': rule.to_state,
                'probability': rule.base_probability,
                'confidence': rule.confidence,
                'conditions': len(rule.conditions),
                'rule_id': rule.id
            })
        
        return {
            'nodes': [{'id': node, 'label': node} for node in nodes],
            'edges': edges
        }