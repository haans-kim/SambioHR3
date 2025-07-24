"""
HMM 기반 활동 분류기
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging
from datetime import datetime

from ...hmm import HMMModel, ViterbiAlgorithm

class HMMActivityClassifier:
    """HMM을 사용한 활동 분류기"""
    
    def __init__(self, model_path: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.hmm_model = HMMModel()
        self.viterbi = ViterbiAlgorithm(self.hmm_model)
        
        # 모델 파라미터 로드
        if model_path and Path(model_path).exists():
            self.hmm_model.load_parameters(model_path)
            self.logger.info(f"HMM 모델 로드: {model_path}")
        else:
            # 기본 파라미터 초기화
            self._initialize_default_parameters()
            self.logger.info("HMM 기본 파라미터 사용")
    
    def classify(self, daily_data: pd.DataFrame, tag_location_master: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        HMM을 사용하여 활동 분류
        
        Args:
            daily_data: 일일 태그 데이터
            tag_location_master: 태깅지점 마스터 데이터
            
        Returns:
            분류된 데이터
        """
        try:
            # 관측 시퀀스 준비
            observation_sequence = self._prepare_observation_sequence(daily_data, tag_location_master)
            
            # HMM 예측
            prediction_result = self.viterbi.predict_with_timeline(observation_sequence)
            
            # 예측 결과 적용
            daily_data = self._apply_predictions(daily_data, prediction_result)
            
            return daily_data
            
        except Exception as e:
            self.logger.error(f"HMM 분류 실패: {e}")
            # 실패 시 기본값 반환
            daily_data['activity_code'] = 'WORK'
            daily_data['confidence'] = 80
            return daily_data
    
    def _initialize_default_parameters(self):
        """기본 HMM 파라미터 초기화"""
        # 상태 전이 확률 초기화
        n_states = self.hmm_model.n_states
        
        # 초기 확률 (출근으로 시작할 확률이 높음)
        initial_probs = np.zeros(n_states)
        initial_probs[self.hmm_model.state_to_index.get('출근', 0)] = 0.8
        initial_probs[self.hmm_model.state_to_index.get('근무', 1)] = 0.2
        self.hmm_model.initial_probabilities = initial_probs
        
        # 전이 확률 행렬 (간단한 예시)
        transition_matrix = np.full((n_states, n_states), 0.05)  # 기본값
        
        # 일반적인 전이 패턴 설정
        transitions = {
            '출근': {'근무': 0.7, '작업준비': 0.2, '이동': 0.1},
            '근무': {'근무': 0.6, '이동': 0.15, '휴식': 0.1, '중식': 0.1, '퇴근': 0.05},
            '조식': {'근무': 0.7, '이동': 0.3},
            '중식': {'근무': 0.7, '휴식': 0.2, '이동': 0.1},
            '석식': {'근무': 0.5, '휴식': 0.3, '퇴근': 0.2},
            '휴식': {'근무': 0.6, '이동': 0.3, '휴식': 0.1},
            '이동': {'근무': 0.5, '회의': 0.2, '휴식': 0.15, '이동': 0.15},
            '회의': {'근무': 0.6, '회의': 0.3, '이동': 0.1},
            '퇴근': {'퇴근': 1.0}  # 퇴근 후에는 상태 변화 없음
        }
        
        for from_state, to_states in transitions.items():
            from_idx = self.hmm_model.state_to_index.get(from_state)
            if from_idx is not None:
                for to_state, prob in to_states.items():
                    to_idx = self.hmm_model.state_to_index.get(to_state)
                    if to_idx is not None:
                        transition_matrix[from_idx][to_idx] = prob
        
        # 행 정규화
        transition_matrix = transition_matrix / transition_matrix.sum(axis=1, keepdims=True)
        self.hmm_model.transition_matrix = transition_matrix
        
        # 관측 확률은 initialize_parameters 메서드 사용
        self.hmm_model.initialize_parameters()
    
    def _prepare_observation_sequence(self, daily_data: pd.DataFrame, 
                                    tag_location_master: Optional[pd.DataFrame]) -> List[Dict[str, Any]]:
        """관측 시퀀스 준비"""
        observations = []
        
        for idx, row in daily_data.iterrows():
            obs = {
                'timestamp': row['datetime'],
                'tag_location': row.get('DR_NM', ''),
                'tag_code': row.get('tag_code', 'G1'),
                'work_area_type': row.get('work_area_type', 'Y'),
                'time_of_day': row['datetime'].hour,
                'day_of_week': row['datetime'].weekday(),
            }
            
            # 시간대별 특징 - 실제 식사 태그가 있는 경우에만 식사로 분류
            hour = row['datetime'].hour
            
            # 실제 식사 여부 확인 (is_actual_meal 플래그 사용)
            is_actual_meal = row.get('is_actual_meal', False)
            
            if is_actual_meal:
                # 실제 식사 태그가 있는 경우에만 식사 시간대 구분
                if 6 <= hour < 9:
                    obs['time_period'] = 'morning'
                elif 11 <= hour < 14:
                    obs['time_period'] = 'lunch'
                elif 17 <= hour < 20:
                    obs['time_period'] = 'dinner'
                elif hour >= 23 or hour < 1:
                    obs['time_period'] = 'midnight'
                else:
                    obs['time_period'] = 'work'
            else:
                # 식사 태그가 없는 경우는 항상 work
                obs['time_period'] = 'work'
            
            # 식당 위치 확인
            obs['is_cafeteria'] = 'CAFETERIA' in row.get('DR_NM', '').upper() or '식당' in row.get('DR_NM', '')
            
            observations.append(obs)
        
        return observations
    
    def _apply_predictions(self, daily_data: pd.DataFrame, 
                         prediction_result: Dict[str, Any]) -> pd.DataFrame:
        """HMM 예측 결과를 DataFrame에 적용"""
        states = prediction_result.get('states', [])
        state_probabilities = prediction_result.get('state_probabilities', [])
        
        if len(states) != len(daily_data):
            self.logger.warning(f"예측 길이 불일치: {len(states)} vs {len(daily_data)}")
            return daily_data
        
        # 상태를 activity_code로 매핑
        state_to_code = {
            '근무': 'WORK',
            '집중근무': 'FOCUSED_WORK',
            '장비조작': 'EQUIPMENT_OPERATION',
            '회의': 'MEETING',
            '작업준비': 'WORK_PREPARATION',
            '작업중': 'WORKING',
            '조식': 'BREAKFAST',
            '중식': 'LUNCH',
            '석식': 'DINNER',
            '야식': 'MIDNIGHT_MEAL',
            '이동': 'MOVEMENT',
            '출근': 'COMMUTE_IN',
            '퇴근': 'COMMUTE_OUT',
            '휴식': 'REST',
            '피트니스': 'FITNESS',
            '연차': 'LEAVE',
            '배우자출산': 'LEAVE',
            '병가': 'LEAVE',
            '출장': 'BUSINESS_TRIP'
        }
        
        # 예측 결과 적용
        for i, (state, probs) in enumerate(zip(states, state_probabilities)):
            if i < len(daily_data):
                # 기존 confidence가 95 이상인 경우는 HMM이 덮어쓰지 않음 (사전 처리된 데이터 보존)
                existing_confidence = daily_data.iloc[i]['confidence'] if 'confidence' in daily_data.columns else 0
                if existing_confidence >= 95:
                    continue
                    
                # 활동 코드 설정
                activity_code = state_to_code.get(state, 'WORK')
                daily_data.iloc[i, daily_data.columns.get_loc('activity_code')] = activity_code
                
                # 신뢰도 = 최대 확률 * 100
                if probs:
                    max_prob = max(probs.values()) if isinstance(probs, dict) else probs
                    confidence = min(100, max_prob * 100)
                else:
                    confidence = 80
                
                daily_data.iloc[i, daily_data.columns.get_loc('confidence')] = confidence
                
                # HMM 소스 표시
                if 'hmm_source' not in daily_data.columns:
                    daily_data['hmm_source'] = 'hmm'
                daily_data.iloc[i, daily_data.columns.get_loc('hmm_source')] = 'hmm'
        
        # 특정 태그 코드는 항상 100% 신뢰도 (규칙 기반 오버라이드)
        if 'tag_code' in daily_data.columns:
            # T2, T3는 확실한 출퇴근
            mask_t2t3 = daily_data['tag_code'].isin(['T2', 'T3'])
            daily_data.loc[mask_t2t3, 'confidence'] = 100
            daily_data.loc[mask_t2t3, 'hmm_source'] = 'rule_override'
            
            # T2는 출근, T3는 퇴근으로 강제
            daily_data.loc[daily_data['tag_code'] == 'T2', 'activity_code'] = 'COMMUTE_IN'
            daily_data.loc[daily_data['tag_code'] == 'T3', 'activity_code'] = 'COMMUTE_OUT'
        
        return daily_data