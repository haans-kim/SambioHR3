"""
Viterbi 예측 알고리즘 구현
최적 상태 시퀀스 추정을 위한 동적 계획법 알고리즘
"""

import numpy as np
import logging
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

class ViterbiAlgorithm:
    """Viterbi 예측 알고리즘 클래스"""
    
    def __init__(self, hmm_model):
        """
        Args:
            hmm_model: HMM 모델 인스턴스
        """
        self.hmm_model = hmm_model
        self.logger = logging.getLogger(__name__)
        
        # 예측 결과 저장
        self.prediction_cache = {}
        
    def predict(self, observation_sequence: List[Dict[str, Any]], 
                use_cache: bool = True) -> Dict[str, Any]:
        """
        관측 시퀀스로부터 최적 상태 시퀀스 예측
        
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
            self.logger.debug(f"캐시된 예측 결과 반환: {cache_key}")
            return self.prediction_cache[cache_key]
        
        # 관측 시퀀스 인코딩
        encoded_sequence = self._encode_observation_sequence(observation_sequence)
        
        # Viterbi 알고리즘 실행
        state_sequence, log_probability, path_probabilities = self._viterbi_algorithm(encoded_sequence, observation_sequence)
        
        # 상태 시퀀스를 문자열로 변환
        state_names = [self.hmm_model.index_to_state[state] for state in state_sequence]
        
        # 신뢰도 계산
        confidence = self._calculate_confidence(path_probabilities, log_probability)
        
        # 상태별 확률 계산
        state_probabilities = self._calculate_state_probabilities(
            encoded_sequence, state_sequence, path_probabilities
        )
        
        # 예측 결과 구성
        prediction_result = {
            'states': state_names,
            'state_indices': state_sequence,
            'log_probability': log_probability,
            'confidence': confidence,
            'state_probabilities': state_probabilities,
            'sequence_length': len(observation_sequence),
            'prediction_timestamp': datetime.now().isoformat()
        }
        
        # 캐시 저장
        if use_cache:
            self.prediction_cache[cache_key] = prediction_result
        
        self.logger.info(f"Viterbi 예측 완료: {len(state_names)}개 상태, "
                        f"로그 확률 = {log_probability:.6f}, 신뢰도 = {confidence:.3f}")
        
        return prediction_result
    
    def predict_with_timeline(self, observation_sequence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        타임라인과 함께 상태 시퀀스 예측
        
        Args:
            observation_sequence: 관측 시퀀스 (타임스탬프 포함)
            
        Returns:
            Dict: 타임라인 예측 결과
        """
        prediction_result = self.predict(observation_sequence)
        
        # 타임라인 정보 추가
        timeline = []
        for i, obs in enumerate(observation_sequence):
            timeline_entry = {
                'timestamp': obs.get('timestamp', None),
                'observation': obs,
                'predicted_state': prediction_result['states'][i] if i < len(prediction_result['states']) else None,
                'state_probability': prediction_result['state_probabilities'][i] if i < len(prediction_result['state_probabilities']) else None,
                'confidence': prediction_result['confidence']
            }
            timeline.append(timeline_entry)
        
        return {
            'timeline': timeline,
            'summary': {
                'total_observations': len(observation_sequence),
                'overall_confidence': prediction_result['confidence'],
                'log_probability': prediction_result['log_probability'],
                'state_distribution': self._calculate_state_distribution(prediction_result['states'])
            }
        }
    
    def _encode_observation_sequence(self, observation_sequence: List[Dict[str, Any]]) -> List[int]:
        """관측 시퀀스를 정수로 인코딩"""
        encoded_sequence = []
        
        for obs in observation_sequence:
            # 태그 위치 특성을 기본으로 사용
            tag_location = obs.get('태그위치', obs.get('DR_NO', 'unknown'))
            
            # 간단한 해싱 방법으로 인코딩 (실제로는 더 정교한 매핑 필요)
            encoded_obs = abs(hash(str(tag_location))) % 50  # 최대 50개 관측값
            encoded_sequence.append(encoded_obs)
        
        return encoded_sequence
    
    def _viterbi_algorithm(self, encoded_sequence: List[int], observation_sequence: List[Dict[str, Any]] = None) -> Tuple[List[int], float, List[List[float]]]:
        """
        Viterbi 알고리즘 실행
        
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
            for j in range(N):
                # 이전 상태에서 현재 상태로의 전이 확률 계산
                transition_scores = []
                for i in range(N):
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
        # 마지막 시점에서 최적 상태 선택
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
    
    def _get_emission_probability(self, state: int, observation: int) -> float:
        """방출 확률 계산"""
        feature = '태그위치'
        if feature in self.hmm_model.emission_matrix:
            emission_matrix = self.hmm_model.emission_matrix[feature]
            if observation < emission_matrix.shape[1]:
                return emission_matrix[state, observation]
        return 1e-10  # 매우 작은 값으로 언더플로우 방지
    
    def _calculate_confidence(self, path_probabilities: List[List[float]], 
                            log_probability: float) -> float:
        """예측 신뢰도 계산"""
        if not path_probabilities:
            return 0.0
        
        # 각 시점에서 최대 상태 확률의 평균
        max_probs = [max(probs) for probs in path_probabilities]
        avg_max_prob = np.mean(max_probs)
        
        # 로그 확률 정규화 (0-1 범위)
        normalized_log_prob = 1.0 / (1.0 + np.exp(-log_probability / len(path_probabilities)))
        
        # 가중 평균으로 신뢰도 계산
        confidence = 0.7 * avg_max_prob + 0.3 * normalized_log_prob
        
        return min(1.0, max(0.0, confidence))
    
    def _calculate_state_probabilities(self, encoded_sequence: List[int], 
                                     state_sequence: List[int], 
                                     path_probabilities: List[List[float]]) -> List[float]:
        """상태별 확률 계산"""
        state_probs = []
        
        for t, state in enumerate(state_sequence):
            if t < len(path_probabilities):
                prob = path_probabilities[t][state]
                state_probs.append(prob)
            else:
                state_probs.append(0.0)
        
        return state_probs
    
    def _calculate_state_distribution(self, states: List[str]) -> Dict[str, float]:
        """상태 분포 계산"""
        if not states:
            return {}
        
        state_counts = {}
        for state in states:
            state_counts[state] = state_counts.get(state, 0) + 1
        
        total = len(states)
        return {state: count / total for state, count in state_counts.items()}
    
    def _generate_cache_key(self, observation_sequence: List[Dict[str, Any]]) -> str:
        """캐시 키 생성"""
        # 관측 시퀀스의 해시값을 캐시 키로 사용
        key_data = []
        for obs in observation_sequence:
            key_data.append(str(obs.get('태그위치', obs.get('DR_NO', 'unknown'))))
        
        return str(hash(tuple(key_data)))
    
    def batch_predict(self, observation_sequences: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        여러 관측 시퀀스에 대한 배치 예측
        
        Args:
            observation_sequences: 관측 시퀀스들의 리스트
            
        Returns:
            List[Dict]: 예측 결과들
        """
        batch_results = []
        
        self.logger.info(f"배치 예측 시작: {len(observation_sequences)}개 시퀀스")
        
        for i, seq in enumerate(observation_sequences):
            try:
                result = self.predict(seq)
                result['sequence_id'] = i
                batch_results.append(result)
                
                if (i + 1) % 100 == 0:
                    self.logger.info(f"배치 예측 진행: {i + 1}/{len(observation_sequences)} 완료")
                    
            except Exception as e:
                self.logger.error(f"시퀀스 {i} 예측 실패: {e}")
                batch_results.append({
                    'sequence_id': i,
                    'error': str(e),
                    'states': [],
                    'log_probability': float('-inf'),
                    'confidence': 0.0
                })
        
        self.logger.info(f"배치 예측 완료: {len(batch_results)}개 결과")
        return batch_results
    
    def get_prediction_stats(self) -> Dict[str, Any]:
        """예측 통계 반환"""
        return {
            'cache_size': len(self.prediction_cache),
            'model_states': self.hmm_model.n_states,
            'model_features': len(self.hmm_model.observation_features)
        }
    
    def clear_cache(self):
        """예측 캐시 초기화"""
        self.prediction_cache.clear()
        self.logger.info("예측 캐시 초기화 완료")
    
    def analyze_prediction_quality(self, observation_sequence: List[Dict[str, Any]], 
                                 true_states: List[str] = None) -> Dict[str, Any]:
        """
        예측 품질 분석
        
        Args:
            observation_sequence: 관측 시퀀스
            true_states: 실제 상태 (있는 경우)
            
        Returns:
            Dict: 품질 분석 결과
        """
        prediction_result = self.predict(observation_sequence)
        
        analysis = {
            'sequence_length': len(observation_sequence),
            'predicted_states': prediction_result['states'],
            'confidence': prediction_result['confidence'],
            'state_distribution': self._calculate_state_distribution(prediction_result['states']),
            'prediction_quality': {
                'high_confidence_ratio': sum(1 for p in prediction_result['state_probabilities'] if p > 0.8) / len(prediction_result['state_probabilities']),
                'low_confidence_ratio': sum(1 for p in prediction_result['state_probabilities'] if p < 0.5) / len(prediction_result['state_probabilities']),
                'avg_state_probability': np.mean(prediction_result['state_probabilities'])
            }
        }
        
        # 실제 상태가 있는 경우 정확도 계산
        if true_states and len(true_states) == len(prediction_result['states']):
            correct_predictions = sum(1 for pred, true in zip(prediction_result['states'], true_states) if pred == true)
            analysis['accuracy'] = correct_predictions / len(true_states)
            analysis['true_states'] = true_states
        
        return analysis