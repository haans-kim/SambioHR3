"""
HMM 규칙 에디터 구현
전이/방출 규칙 수정 및 검증 인터페이스
"""

import numpy as np
import json
import logging
from typing import Dict, List, Tuple, Optional, Any, Union
from datetime import datetime
from pathlib import Path

from .hmm_model import ActivityState, ObservationFeature

class HMMRuleEditor:
    """HMM 규칙 편집기 클래스"""
    
    def __init__(self, hmm_model):
        """
        Args:
            hmm_model: HMM 모델 인스턴스
        """
        self.hmm_model = hmm_model
        self.logger = logging.getLogger(__name__)
        
        # 규칙 변경 히스토리
        self.change_history = []
        
        # 백업 데이터
        self.backup_data = None
        
    def create_backup(self):
        """현재 모델 상태 백업"""
        self.backup_data = {
            'transition_matrix': self.hmm_model.transition_matrix.copy() if self.hmm_model.transition_matrix is not None else None,
            'emission_matrix': {k: v.copy() for k, v in self.hmm_model.emission_matrix.items()} if self.hmm_model.emission_matrix else None,
            'initial_probabilities': self.hmm_model.initial_probabilities.copy() if self.hmm_model.initial_probabilities is not None else None,
            'timestamp': datetime.now().isoformat()
        }
        self.logger.info("모델 상태 백업 완료")
    
    def restore_backup(self):
        """백업으로부터 모델 상태 복원"""
        if self.backup_data is None:
            raise ValueError("백업 데이터가 없습니다.")
        
        self.hmm_model.transition_matrix = self.backup_data['transition_matrix']
        self.hmm_model.emission_matrix = self.backup_data['emission_matrix']
        self.hmm_model.initial_probabilities = self.backup_data['initial_probabilities']
        
        self.logger.info("모델 상태 복원 완료")
    
    def edit_transition_probability(self, from_state: str, to_state: str, 
                                  probability: float, normalize: bool = True) -> Dict[str, Any]:
        """
        전이 확률 수정
        
        Args:
            from_state: 출발 상태
            to_state: 도착 상태
            probability: 새로운 확률값
            normalize: 행 정규화 여부
            
        Returns:
            Dict: 수정 결과
        """
        if from_state not in self.hmm_model.state_to_index:
            raise ValueError(f"잘못된 출발 상태: {from_state}")
        
        if to_state not in self.hmm_model.state_to_index:
            raise ValueError(f"잘못된 도착 상태: {to_state}")
        
        if not 0 <= probability <= 1:
            raise ValueError(f"확률값이 범위를 벗어남: {probability}")
        
        # 백업 생성
        if self.backup_data is None:
            self.create_backup()
        
        # 인덱스 변환
        from_idx = self.hmm_model.state_to_index[from_state]
        to_idx = self.hmm_model.state_to_index[to_state]
        
        # 이전 값 저장
        old_probability = self.hmm_model.transition_matrix[from_idx, to_idx]
        
        # 새 값 설정
        self.hmm_model.transition_matrix[from_idx, to_idx] = probability
        
        # 행 정규화
        if normalize:
            row_sum = np.sum(self.hmm_model.transition_matrix[from_idx, :])
            if row_sum > 0:
                self.hmm_model.transition_matrix[from_idx, :] /= row_sum
        
        # 변경 히스토리 기록
        change_record = {
            'timestamp': datetime.now().isoformat(),
            'action': 'edit_transition_probability',
            'from_state': from_state,
            'to_state': to_state,
            'old_probability': old_probability,
            'new_probability': probability,
            'normalized': normalize
        }
        self.change_history.append(change_record)
        
        self.logger.info(f"전이 확률 수정: {from_state} -> {to_state}: {old_probability:.4f} -> {probability:.4f}")
        
        return {
            'success': True,
            'change': change_record,
            'current_row': self.hmm_model.transition_matrix[from_idx, :].tolist()
        }
    
    def edit_emission_probability(self, state: str, feature: str, 
                                observation: Union[str, int], probability: float,
                                normalize: bool = True) -> Dict[str, Any]:
        """
        방출 확률 수정
        
        Args:
            state: 상태
            feature: 관측 특성
            observation: 관측값
            probability: 새로운 확률값
            normalize: 행 정규화 여부
            
        Returns:
            Dict: 수정 결과
        """
        if state not in self.hmm_model.state_to_index:
            raise ValueError(f"잘못된 상태: {state}")
        
        if feature not in self.hmm_model.emission_matrix:
            raise ValueError(f"잘못된 관측 특성: {feature}")
        
        if not 0 <= probability <= 1:
            raise ValueError(f"확률값이 범위를 벗어남: {probability}")
        
        # 백업 생성
        if self.backup_data is None:
            self.create_backup()
        
        # 인덱스 변환
        state_idx = self.hmm_model.state_to_index[state]
        
        # 관측값 인덱스 처리
        if isinstance(observation, str):
            # 문자열 관측값의 경우 해싱 사용
            obs_idx = abs(hash(observation)) % self.hmm_model.emission_matrix[feature].shape[1]
        else:
            obs_idx = int(observation)
        
        if obs_idx >= self.hmm_model.emission_matrix[feature].shape[1]:
            raise ValueError(f"관측값 인덱스가 범위를 벗어남: {obs_idx}")
        
        # 이전 값 저장
        old_probability = self.hmm_model.emission_matrix[feature][state_idx, obs_idx]
        
        # 새 값 설정
        self.hmm_model.emission_matrix[feature][state_idx, obs_idx] = probability
        
        # 행 정규화
        if normalize:
            row_sum = np.sum(self.hmm_model.emission_matrix[feature][state_idx, :])
            if row_sum > 0:
                self.hmm_model.emission_matrix[feature][state_idx, :] /= row_sum
        
        # 변경 히스토리 기록
        change_record = {
            'timestamp': datetime.now().isoformat(),
            'action': 'edit_emission_probability',
            'state': state,
            'feature': feature,
            'observation': observation,
            'observation_index': obs_idx,
            'old_probability': old_probability,
            'new_probability': probability,
            'normalized': normalize
        }
        self.change_history.append(change_record)
        
        self.logger.info(f"방출 확률 수정: {state}({feature}={observation}): {old_probability:.4f} -> {probability:.4f}")
        
        return {
            'success': True,
            'change': change_record,
            'current_row': self.hmm_model.emission_matrix[feature][state_idx, :].tolist()
        }
    
    def edit_initial_probability(self, state: str, probability: float,
                               normalize: bool = True) -> Dict[str, Any]:
        """
        초기 상태 확률 수정
        
        Args:
            state: 상태
            probability: 새로운 확률값
            normalize: 전체 정규화 여부
            
        Returns:
            Dict: 수정 결과
        """
        if state not in self.hmm_model.state_to_index:
            raise ValueError(f"잘못된 상태: {state}")
        
        if not 0 <= probability <= 1:
            raise ValueError(f"확률값이 범위를 벗어남: {probability}")
        
        # 백업 생성
        if self.backup_data is None:
            self.create_backup()
        
        # 인덱스 변환
        state_idx = self.hmm_model.state_to_index[state]
        
        # 이전 값 저장
        old_probability = self.hmm_model.initial_probabilities[state_idx]
        
        # 새 값 설정
        self.hmm_model.initial_probabilities[state_idx] = probability
        
        # 전체 정규화
        if normalize:
            total_sum = np.sum(self.hmm_model.initial_probabilities)
            if total_sum > 0:
                self.hmm_model.initial_probabilities /= total_sum
        
        # 변경 히스토리 기록
        change_record = {
            'timestamp': datetime.now().isoformat(),
            'action': 'edit_initial_probability',
            'state': state,
            'old_probability': old_probability,
            'new_probability': probability,
            'normalized': normalize
        }
        self.change_history.append(change_record)
        
        self.logger.info(f"초기 확률 수정: {state}: {old_probability:.4f} -> {probability:.4f}")
        
        return {
            'success': True,
            'change': change_record,
            'current_probabilities': self.hmm_model.initial_probabilities.tolist()
        }
    
    def batch_edit_transition_matrix(self, transition_rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        전이 행렬 배치 수정
        
        Args:
            transition_rules: 전이 규칙 리스트
            
        Returns:
            Dict: 배치 수정 결과
        """
        if self.backup_data is None:
            self.create_backup()
        
        results = []
        errors = []
        
        for rule in transition_rules:
            try:
                result = self.edit_transition_probability(
                    rule['from_state'],
                    rule['to_state'],
                    rule['probability'],
                    normalize=False  # 배치 완료 후 한 번에 정규화
                )
                results.append(result)
            except Exception as e:
                error = {
                    'rule': rule,
                    'error': str(e)
                }
                errors.append(error)
                self.logger.error(f"전이 규칙 적용 실패: {rule}, 오류: {e}")
        
        # 전체 행렬 정규화
        for i in range(self.hmm_model.n_states):
            row_sum = np.sum(self.hmm_model.transition_matrix[i, :])
            if row_sum > 0:
                self.hmm_model.transition_matrix[i, :] /= row_sum
        
        return {
            'success': len(errors) == 0,
            'processed_rules': len(results),
            'errors': errors,
            'results': results
        }
    
    def create_meal_time_rules(self) -> Dict[str, Any]:
        """
        식사시간 관련 규칙 생성 (2교대 근무 반영)
        
        Returns:
            Dict: 생성된 규칙들
        """
        meal_states = [
            ActivityState.BREAKFAST.value,
            ActivityState.LUNCH.value,
            ActivityState.DINNER.value,
            ActivityState.MIDNIGHT_MEAL.value
        ]
        
        rules = []
        
        # 식사 상태 간 전이 규칙
        for meal_state in meal_states:
            # 식사 후 근무로 복귀 확률 높임
            rules.append({
                'from_state': meal_state,
                'to_state': ActivityState.WORK.value,
                'probability': 0.6
            })
            
            # 식사 후 이동 확률
            rules.append({
                'from_state': meal_state,
                'to_state': ActivityState.MOVEMENT.value,
                'probability': 0.3
            })
        
        # CAFETERIA 위치에서 식사 상태 높은 확률
        for meal_state in meal_states:
            if meal_state == ActivityState.MIDNIGHT_MEAL.value:
                # 야식은 야간 교대에서만
                continue
            
            # 여기서는 방출 확률 규칙 생성 (실제 구현에서는 더 정교하게)
            
        return {
            'meal_transition_rules': rules,
            'description': '식사시간 관련 전이 규칙 (2교대 근무 반영)'
        }
    
    def create_shift_work_rules(self) -> Dict[str, Any]:
        """
        교대근무 관련 규칙 생성
        
        Returns:
            Dict: 생성된 규칙들
        """
        rules = []
        
        # 출근 -> 근무 전이 확률 높임
        rules.append({
            'from_state': ActivityState.CLOCK_IN.value,
            'to_state': ActivityState.WORK.value,
            'probability': 0.5
        })
        
        # 퇴근 전 활동 패턴
        rules.append({
            'from_state': ActivityState.WORK.value,
            'to_state': ActivityState.CLOCK_OUT.value,
            'probability': 0.1
        })
        
        # 야식 후 퇴근 (야간 교대)
        rules.append({
            'from_state': ActivityState.MIDNIGHT_MEAL.value,
            'to_state': ActivityState.CLOCK_OUT.value,
            'probability': 0.2
        })
        
        return {
            'shift_transition_rules': rules,
            'description': '교대근무 관련 전이 규칙'
        }
    
    def validate_rules(self) -> Dict[str, Any]:
        """
        현재 규칙 검증
        
        Returns:
            Dict: 검증 결과
        """
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'statistics': {}
        }
        
        # 전이 확률 행렬 검증
        if self.hmm_model.transition_matrix is not None:
            for i in range(self.hmm_model.n_states):
                row_sum = np.sum(self.hmm_model.transition_matrix[i, :])
                if not np.isclose(row_sum, 1.0, rtol=1e-3):
                    validation_result['errors'].append(
                        f"전이 확률 행렬 {i}행의 합이 1이 아닙니다: {row_sum:.6f}"
                    )
                
                # 0에 가까운 확률들 경고
                near_zero_count = np.sum(self.hmm_model.transition_matrix[i, :] < 1e-6)
                if near_zero_count > self.hmm_model.n_states * 0.5:
                    validation_result['warnings'].append(
                        f"전이 확률 행렬 {i}행에 매우 낮은 확률이 많습니다: {near_zero_count}개"
                    )
        
        # 초기 확률 검증
        if self.hmm_model.initial_probabilities is not None:
            prob_sum = np.sum(self.hmm_model.initial_probabilities)
            if not np.isclose(prob_sum, 1.0, rtol=1e-3):
                validation_result['errors'].append(
                    f"초기 확률의 합이 1이 아닙니다: {prob_sum:.6f}"
                )
        
        # 방출 확률 검증
        if self.hmm_model.emission_matrix:
            for feature, matrix in self.hmm_model.emission_matrix.items():
                for i in range(self.hmm_model.n_states):
                    row_sum = np.sum(matrix[i, :])
                    if not np.isclose(row_sum, 1.0, rtol=1e-3):
                        validation_result['errors'].append(
                            f"방출 확률 행렬 {feature} {i}행의 합이 1이 아닙니다: {row_sum:.6f}"
                        )
        
        # 통계 정보
        validation_result['statistics'] = {
            'total_states': self.hmm_model.n_states,
            'observation_features': len(self.hmm_model.observation_features),
            'change_history_count': len(self.change_history),
            'has_backup': self.backup_data is not None
        }
        
        validation_result['is_valid'] = len(validation_result['errors']) == 0
        
        return validation_result
    
    def get_change_history(self) -> List[Dict[str, Any]]:
        """변경 히스토리 반환"""
        return self.change_history.copy()
    
    def export_rules(self, filepath: str):
        """
        규칙을 파일로 내보내기
        
        Args:
            filepath: 저장할 파일 경로
        """
        export_data = {
            'model_name': self.hmm_model.model_name,
            'export_timestamp': datetime.now().isoformat(),
            'states': self.hmm_model.states,
            'transition_matrix': self.hmm_model.transition_matrix.tolist() if self.hmm_model.transition_matrix is not None else None,
            'initial_probabilities': self.hmm_model.initial_probabilities.tolist() if self.hmm_model.initial_probabilities is not None else None,
            'emission_matrices': {
                feature: matrix.tolist() 
                for feature, matrix in self.hmm_model.emission_matrix.items()
            } if self.hmm_model.emission_matrix else None,
            'change_history': self.change_history,
            'validation_result': self.validate_rules()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"규칙 내보내기 완료: {filepath}")
    
    def import_rules(self, filepath: str):
        """
        파일로부터 규칙 가져오기
        
        Args:
            filepath: 가져올 파일 경로
        """
        if not Path(filepath).exists():
            raise FileNotFoundError(f"파일이 존재하지 않습니다: {filepath}")
        
        # 현재 상태 백업
        self.create_backup()
        
        with open(filepath, 'r', encoding='utf-8') as f:
            import_data = json.load(f)
        
        # 규칙 적용
        if import_data.get('transition_matrix'):
            self.hmm_model.transition_matrix = np.array(import_data['transition_matrix'])
        
        if import_data.get('initial_probabilities'):
            self.hmm_model.initial_probabilities = np.array(import_data['initial_probabilities'])
        
        if import_data.get('emission_matrices'):
            self.hmm_model.emission_matrix = {
                feature: np.array(matrix)
                for feature, matrix in import_data['emission_matrices'].items()
            }
        
        # 변경 히스토리 추가
        import_record = {
            'timestamp': datetime.now().isoformat(),
            'action': 'import_rules',
            'source_file': filepath,
            'imported_model': import_data.get('model_name', 'unknown')
        }
        self.change_history.append(import_record)
        
        self.logger.info(f"규칙 가져오기 완료: {filepath}")
    
    def reset_to_defaults(self):
        """기본 설정으로 재설정"""
        self.create_backup()
        
        # 도메인 지식 기반으로 재초기화
        self.hmm_model.initialize_parameters("domain_knowledge")
        
        # 변경 히스토리 추가
        reset_record = {
            'timestamp': datetime.now().isoformat(),
            'action': 'reset_to_defaults',
            'initialization_method': 'domain_knowledge'
        }
        self.change_history.append(reset_record)
        
        self.logger.info("기본 설정으로 재설정 완료")