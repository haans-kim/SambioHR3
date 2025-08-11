"""
룰 기반 Viterbi 알고리즘 구현
조건부 전이 확률을 사용하는 개선된 버전
"""

import numpy as np
import logging
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

from .viterbi import ViterbiAlgorithm

class RuleBasedViterbiAlgorithm(ViterbiAlgorithm):
    """룰 기반 Viterbi 알고리즘"""
    
    def __init__(self, hmm_model):
        super().__init__(hmm_model)
        self.logger = logging.getLogger(__name__)
        
    def _viterbi_algorithm(self, encoded_sequence: List[int], 
                          observation_sequence: List[Dict[str, Any]] = None) -> Tuple[List[int], float, List[List[float]]]:
        """
        룰 기반 Viterbi 알고리즘 실행
        
        Args:
            encoded_sequence: 인코딩된 관측 시퀀스
            observation_sequence: 원본 관측 시퀀스 (컨텍스트 정보 포함)
            
        Returns:
            Tuple: (상태 시퀀스, 로그 확률, 경로 확률들)
        """
        T = len(encoded_sequence)
        N = self.hmm_model.n_states
        
        # 로그 확률 테이블 초기화
        log_delta = np.full((T, N), -np.inf)
        psi = np.zeros((T, N), dtype=int)
        
        # 초기화 (t=0)
        for i in range(N):
            initial_prob = self.hmm_model.initial_probabilities[i]
            emission_prob = self._get_emission_probability(i, encoded_sequence[0])
            log_delta[0, i] = np.log(initial_prob + 1e-10) + np.log(emission_prob + 1e-10)
        
        # 순환 단계 (t=1 to T-1)
        for t in range(1, T):
            # 현재 시점의 컨텍스트 추출
            context = self._extract_context(t, observation_sequence) if observation_sequence else {}
            
            for j in range(N):
                transition_scores = []
                
                for i in range(N):
                    # 룰 기반 전이 확률 계산
                    from_state = self.hmm_model.index_to_state[i]
                    to_state = self.hmm_model.index_to_state[j]
                    
                    # 조건부 전이 확률 사용
                    if context:
                        transition_prob = self.hmm_model.get_transition_probability_with_conditions(
                            from_state, to_state, context
                        )
                    else:
                        # 컨텍스트가 없으면 기본 확률 사용
                        transition_prob = self.hmm_model.transition_matrix[i, j]
                    
                    score = log_delta[t-1, i] + np.log(transition_prob + 1e-10)
                    transition_scores.append(score)
                
                # 최적 이전 상태 선택
                best_prev_state = np.argmax(transition_scores)
                psi[t, j] = best_prev_state
                
                # 현재 상태의 로그 확률 계산
                emission_prob = self._get_emission_probability(j, encoded_sequence[t])
                log_delta[t, j] = transition_scores[best_prev_state] + np.log(emission_prob + 1e-10)
        
        # 종료 단계: 최적 경로 추적
        best_final_state = np.argmax(log_delta[T-1, :])
        best_log_probability = log_delta[T-1, best_final_state]
        
        # 역추적으로 최적 경로 구성
        optimal_path = [0] * T
        optimal_path[T-1] = best_final_state
        
        for t in range(T-2, -1, -1):
            optimal_path[t] = psi[t+1, optimal_path[t+1]]
        
        # 경로 확률들 계산
        path_probabilities = []
        for t in range(T):
            state_probs = np.exp(log_delta[t, :] - np.max(log_delta[t, :]))
            state_probs = state_probs / np.sum(state_probs)
            path_probabilities.append(state_probs.tolist())
        
        return optimal_path, best_log_probability, path_probabilities
    
    def _extract_context(self, t: int, observation_sequence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        현재 시점의 컨텍스트 정보 추출
        
        Args:
            t: 현재 시점
            observation_sequence: 관측 시퀀스
            
        Returns:
            Dict: 컨텍스트 정보
        """
        if not observation_sequence or t >= len(observation_sequence):
            return {}
        
        obs = observation_sequence[t]
        context = {}
        
        # 시간 정보
        if 'timestamp' in obs:
            timestamp = obs['timestamp']
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            context['current_time'] = timestamp
        
        # 위치 정보
        if '태그위치' in obs:
            context['location'] = obs['태그위치']
        elif 'DR_NO' in obs:
            context['location'] = obs['DR_NO']
        
        # 교대 타입
        if 'shift_type' in obs:
            context['shift_type'] = obs['shift_type']
        
        # 체류 시간 계산 (이전 관측과의 시간 차이)
        if t > 0 and 'timestamp' in observation_sequence[t-1] and 'timestamp' in obs:
            prev_time = observation_sequence[t-1]['timestamp']
            curr_time = obs['timestamp']
            
            if isinstance(prev_time, str):
                prev_time = datetime.fromisoformat(prev_time)
            if isinstance(curr_time, str):
                curr_time = datetime.fromisoformat(curr_time)
            
            duration_minutes = (curr_time - prev_time).total_seconds() / 60
            context['duration_minutes'] = duration_minutes
        
        # 태그 코드
        if 'tag_code' in obs:
            context['tag_code'] = obs['tag_code']
        
        return context
    
    def predict(self, observation_sequence: List[Dict[str, Any]], 
                use_cache: bool = True) -> Dict[str, Any]:
        """
        룰 기반 예측 (오버라이드)
        
        Args:
            observation_sequence: 관측 시퀀스
            use_cache: 캐시 사용 여부
            
        Returns:
            Dict: 예측 결과
        """
        if not observation_sequence:
            return {'states': [], 'log_probability': float('-inf'), 'confidence': 0.0}
        
        # 캐시 키 생성
        cache_key = self._generate_cache_key(observation_sequence)
        if use_cache and cache_key in self.prediction_cache:
            # Cached prediction returned - removed debug logging
            return self.prediction_cache[cache_key]
        
        # 관측 시퀀스 인코딩
        encoded_sequence = self._encode_observation_sequence(observation_sequence)
        
        # 룰 기반 Viterbi 알고리즘 실행
        state_sequence, log_probability, path_probabilities = self._viterbi_algorithm(
            encoded_sequence, observation_sequence
        )
        
        # 상태 시퀀스를 문자열로 변환
        state_names = [self.hmm_model.index_to_state[state] for state in state_sequence]
        
        # 신뢰도 계산
        confidence = self._calculate_confidence(path_probabilities, log_probability)
        
        # 상태별 확률 계산
        state_probabilities = self._calculate_state_probabilities(
            encoded_sequence, state_sequence, path_probabilities
        )
        
        # 적용된 룰 추적
        applied_rules = self._track_applied_rules(state_sequence, observation_sequence)
        
        # 예측 결과 구성
        prediction_result = {
            'states': state_names,
            'state_indices': state_sequence,
            'log_probability': log_probability,
            'confidence': confidence,
            'state_probabilities': state_probabilities,
            'sequence_length': len(observation_sequence),
            'prediction_timestamp': datetime.now().isoformat(),
            'applied_rules': applied_rules  # 추가: 적용된 룰 정보
        }
        
        # 캐시 저장
        if use_cache:
            self.prediction_cache[cache_key] = prediction_result
        
        self.logger.info(f"룰 기반 Viterbi 예측 완료: {len(state_names)}개 상태, "
                        f"로그 확률 = {log_probability:.6f}, 신뢰도 = {confidence:.3f}, "
                        f"적용된 룰 = {len(applied_rules)}개")
        
        return prediction_result
    
    def _track_applied_rules(self, state_sequence: List[int], 
                           observation_sequence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        적용된 룰 추적
        
        Args:
            state_sequence: 예측된 상태 시퀀스
            observation_sequence: 관측 시퀀스
            
        Returns:
            List[Dict]: 적용된 룰 정보
        """
        applied_rules = []
        
        for t in range(1, len(state_sequence)):
            from_state = self.hmm_model.index_to_state[state_sequence[t-1]]
            to_state = self.hmm_model.index_to_state[state_sequence[t]]
            
            context = self._extract_context(t, observation_sequence)
            
            # 적용된 룰 찾기
            if hasattr(self.hmm_model, 'rule_manager'):
                applicable_rules = self.hmm_model.rule_manager.get_applicable_rules(
                    from_state, context
                )
                
                for rule in applicable_rules:
                    if rule.to_state == to_state:
                        applied_rules.append({
                            'time': t,
                            'rule_id': rule.id,
                            'from_state': from_state,
                            'to_state': to_state,
                            'confidence': rule.confidence,
                            'conditions': len(rule.conditions)
                        })
                        break
        
        return applied_rules