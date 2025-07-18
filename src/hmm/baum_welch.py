"""
Baum-Welch 학습 알고리즘 구현
HMM 모델 파라미터 최적화를 위한 EM 알고리즘
"""

import numpy as np
import logging
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
import json

class BaumWelchAlgorithm:
    """Baum-Welch 학습 알고리즘 클래스"""
    
    def __init__(self, hmm_model, max_iterations: int = 100, convergence_threshold: float = 1e-6):
        """
        Args:
            hmm_model: HMM 모델 인스턴스
            max_iterations: 최대 반복 횟수
            convergence_threshold: 수렴 임계값
        """
        self.hmm_model = hmm_model
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold
        self.logger = logging.getLogger(__name__)
        
        # 학습 통계
        self.training_history = []
        self.current_iteration = 0
        
    def fit(self, observation_sequences: List[List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        관측 시퀀스들을 이용한 HMM 파라미터 학습
        
        Args:
            observation_sequences: 관측 시퀀스 리스트
            
        Returns:
            Dict: 학습 결과 및 통계
        """
        if not observation_sequences:
            raise ValueError("관측 시퀀스가 비어있습니다.")
        
        self.logger.info(f"Baum-Welch 학습 시작: {len(observation_sequences)}개 시퀀스")
        
        # 관측값 인코딩
        encoded_sequences = self._encode_observation_sequences(observation_sequences)
        
        # 초기 로그 우도 계산
        prev_log_likelihood = self._compute_total_log_likelihood(encoded_sequences)
        self.logger.info(f"초기 로그 우도: {prev_log_likelihood:.6f}")
        
        # EM 알고리즘 반복
        for iteration in range(self.max_iterations):
            self.current_iteration = iteration + 1
            
            # E-step: Forward-Backward 알고리즘
            gamma_list, xi_list = self._expectation_step(encoded_sequences)
            
            # M-step: 파라미터 업데이트
            self._maximization_step(encoded_sequences, gamma_list, xi_list)
            
            # 수렴 검사
            current_log_likelihood = self._compute_total_log_likelihood(encoded_sequences)
            likelihood_change = abs(current_log_likelihood - prev_log_likelihood)
            
            # 학습 통계 저장
            training_stats = {
                'iteration': self.current_iteration,
                'log_likelihood': current_log_likelihood,
                'likelihood_change': likelihood_change,
                'timestamp': datetime.now().isoformat()
            }
            self.training_history.append(training_stats)
            
            self.logger.info(f"반복 {self.current_iteration}: 로그 우도 = {current_log_likelihood:.6f}, "
                           f"변화량 = {likelihood_change:.8f}")
            
            # 수렴 체크
            if likelihood_change < self.convergence_threshold:
                self.logger.info(f"수렴 완료: 반복 {self.current_iteration}회")
                break
                
            prev_log_likelihood = current_log_likelihood
        
        # 학습 완료 통계
        final_stats = {
            'converged': likelihood_change < self.convergence_threshold,
            'total_iterations': self.current_iteration,
            'final_log_likelihood': prev_log_likelihood,
            'training_sequences': len(observation_sequences),
            'training_history': self.training_history
        }
        
        self.logger.info(f"Baum-Welch 학습 완료: {self.current_iteration}회 반복, "
                        f"최종 로그 우도 = {prev_log_likelihood:.6f}")
        
        return final_stats
    
    def _encode_observation_sequences(self, observation_sequences: List[List[Dict[str, Any]]]) -> List[List[int]]:
        """관측 시퀀스를 정수로 인코딩"""
        encoded_sequences = []
        
        # 각 특성별로 관측값 매핑 생성
        self.observation_mappings = {}
        for feature in self.hmm_model.observation_features:
            self.observation_mappings[feature] = {}
            obs_index = 0
            
            # 모든 시퀀스에서 해당 특성의 고유값 수집
            unique_values = set()
            for seq in observation_sequences:
                for obs in seq:
                    if feature in obs:
                        unique_values.add(obs[feature])
            
            # 고유값을 정수로 매핑
            for value in sorted(unique_values):
                self.observation_mappings[feature][value] = obs_index
                obs_index += 1
        
        # 시퀀스 인코딩 (현재는 TAG_LOCATION 특성만 사용)
        for seq in observation_sequences:
            encoded_seq = []
            for obs in seq:
                # 태그 위치 특성을 기본으로 사용
                tag_location = obs.get('태그위치', 'unknown')
                if tag_location in self.observation_mappings['태그위치']:
                    encoded_seq.append(self.observation_mappings['태그위치'][tag_location])
                else:
                    encoded_seq.append(0)  # 기본값
            encoded_sequences.append(encoded_seq)
        
        return encoded_sequences
    
    def _expectation_step(self, encoded_sequences: List[List[int]]) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        """E-step: Forward-Backward 알고리즘으로 상태 확률 계산"""
        gamma_list = []
        xi_list = []
        
        for seq in encoded_sequences:
            if len(seq) == 0:
                continue
                
            # Forward-Backward 알고리즘 실행
            alpha, beta, log_likelihood = self._forward_backward(seq)
            
            # Gamma 계산 (상태 확률)
            gamma = self._compute_gamma(alpha, beta)
            gamma_list.append(gamma)
            
            # Xi 계산 (상태 전이 확률)
            xi = self._compute_xi(seq, alpha, beta)
            xi_list.append(xi)
        
        return gamma_list, xi_list
    
    def _forward_backward(self, sequence: List[int]) -> Tuple[np.ndarray, np.ndarray, float]:
        """Forward-Backward 알고리즘"""
        T = len(sequence)
        N = self.hmm_model.n_states
        
        # Forward 알고리즘
        alpha = np.zeros((T, N))
        scaling_factors = np.zeros(T)
        
        # 초기화
        for i in range(N):
            alpha[0, i] = self.hmm_model.initial_probabilities[i] * self._get_emission_probability(i, sequence[0])
        
        # 정규화
        scaling_factors[0] = np.sum(alpha[0, :])
        if scaling_factors[0] > 0:
            alpha[0, :] /= scaling_factors[0]
        
        # Forward 단계
        for t in range(1, T):
            for j in range(N):
                alpha[t, j] = self._get_emission_probability(j, sequence[t]) * \
                             np.sum(alpha[t-1, :] * self.hmm_model.transition_matrix[:, j])
            
            # 정규화
            scaling_factors[t] = np.sum(alpha[t, :])
            if scaling_factors[t] > 0:
                alpha[t, :] /= scaling_factors[t]
        
        # Backward 알고리즘
        beta = np.zeros((T, N))
        beta[T-1, :] = 1.0
        
        for t in range(T-2, -1, -1):
            for i in range(N):
                beta[t, i] = np.sum(
                    self.hmm_model.transition_matrix[i, :] * 
                    beta[t+1, :] * 
                    [self._get_emission_probability(j, sequence[t+1]) for j in range(N)]
                )
            
            # 정규화
            if scaling_factors[t+1] > 0:
                beta[t, :] /= scaling_factors[t+1]
        
        # 로그 우도 계산
        log_likelihood = np.sum(np.log(scaling_factors + 1e-10))
        
        return alpha, beta, log_likelihood
    
    def _compute_gamma(self, alpha: np.ndarray, beta: np.ndarray) -> np.ndarray:
        """Gamma 계산 (상태 확률)"""
        gamma = alpha * beta
        
        # 정규화
        for t in range(gamma.shape[0]):
            total = np.sum(gamma[t, :])
            if total > 0:
                gamma[t, :] /= total
        
        return gamma
    
    def _compute_xi(self, sequence: List[int], alpha: np.ndarray, beta: np.ndarray) -> np.ndarray:
        """Xi 계산 (상태 전이 확률)"""
        T = len(sequence)
        N = self.hmm_model.n_states
        xi = np.zeros((T-1, N, N))
        
        for t in range(T-1):
            denominator = 0
            for i in range(N):
                for j in range(N):
                    xi[t, i, j] = alpha[t, i] * self.hmm_model.transition_matrix[i, j] * \
                                 self._get_emission_probability(j, sequence[t+1]) * beta[t+1, j]
                    denominator += xi[t, i, j]
            
            # 정규화
            if denominator > 0:
                xi[t, :, :] /= denominator
        
        return xi
    
    def _maximization_step(self, encoded_sequences: List[List[int]], 
                          gamma_list: List[np.ndarray], xi_list: List[np.ndarray]):
        """M-step: 파라미터 업데이트"""
        N = self.hmm_model.n_states
        
        # 초기 상태 확률 업데이트
        initial_count = np.zeros(N)
        for gamma in gamma_list:
            if len(gamma) > 0:
                initial_count += gamma[0, :]
        
        self.hmm_model.initial_probabilities = initial_count / len(gamma_list)
        
        # 전이 확률 행렬 업데이트
        transition_count = np.zeros((N, N))
        transition_denominator = np.zeros(N)
        
        for xi, gamma in zip(xi_list, gamma_list):
            if len(xi) > 0:
                transition_count += np.sum(xi, axis=0)
                transition_denominator += np.sum(gamma[:-1, :], axis=0)
        
        for i in range(N):
            if transition_denominator[i] > 0:
                self.hmm_model.transition_matrix[i, :] = transition_count[i, :] / transition_denominator[i]
        
        # 방출 확률 업데이트 (TAG_LOCATION 특성만)
        feature = '태그위치'
        if feature in self.hmm_model.emission_matrix:
            n_observations = self.hmm_model.emission_matrix[feature].shape[1]
            emission_count = np.zeros((N, n_observations))
            emission_denominator = np.zeros(N)
            
            for seq, gamma in zip(encoded_sequences, gamma_list):
                for t, obs in enumerate(seq):
                    if t < len(gamma) and obs < n_observations:
                        emission_count[:, obs] += gamma[t, :]
                        emission_denominator += gamma[t, :]
            
            for i in range(N):
                if emission_denominator[i] > 0:
                    self.hmm_model.emission_matrix[feature][i, :] = emission_count[i, :] / emission_denominator[i]
    
    def _get_emission_probability(self, state: int, observation: int) -> float:
        """방출 확률 계산"""
        feature = '태그위치'
        if feature in self.hmm_model.emission_matrix:
            emission_matrix = self.hmm_model.emission_matrix[feature]
            if observation < emission_matrix.shape[1]:
                return emission_matrix[state, observation]
        return 1e-10  # 매우 작은 값으로 언더플로우 방지
    
    def _compute_total_log_likelihood(self, encoded_sequences: List[List[int]]) -> float:
        """전체 로그 우도 계산"""
        total_log_likelihood = 0
        
        for seq in encoded_sequences:
            if len(seq) > 0:
                _, _, log_likelihood = self._forward_backward(seq)
                total_log_likelihood += log_likelihood
        
        return total_log_likelihood
    
    def get_training_stats(self) -> Dict[str, Any]:
        """학습 통계 반환"""
        return {
            'total_iterations': self.current_iteration,
            'convergence_threshold': self.convergence_threshold,
            'training_history': self.training_history
        }
    
    def save_training_log(self, filepath: str):
        """학습 로그 저장"""
        training_log = {
            'algorithm': 'Baum-Welch',
            'max_iterations': self.max_iterations,
            'convergence_threshold': self.convergence_threshold,
            'training_stats': self.get_training_stats(),
            'observation_mappings': self.observation_mappings,
            'completed_at': datetime.now().isoformat()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(training_log, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"학습 로그 저장 완료: {filepath}")