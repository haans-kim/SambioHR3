"""
HMM (Hidden Markov Model) 모델 구현
2교대 근무 시스템을 반영한 상태 정의 및 관측값 처리
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum
import logging
from datetime import datetime, time
import json

class ActivityState(Enum):
    """활동 상태 정의 (2교대 근무 반영)"""
    # 근무 상태
    WORK = "근무"
    FOCUSED_WORK = "집중근무"
    EQUIPMENT_OPERATION = "장비조작"
    MEETING = "회의"
    WORK_PREPARATION = "작업준비"
    WORKING = "작업중"
    
    # 식사 상태 (4번 식사시간)
    BREAKFAST = "조식"
    LUNCH = "중식"
    DINNER = "석식"
    MIDNIGHT_MEAL = "야식"
    
    # 이동 상태
    MOVEMENT = "이동"
    CLOCK_IN = "출근"
    CLOCK_OUT = "퇴근"
    
    # 휴식 상태
    REST = "휴식"
    FITNESS = "피트니스"
    
    # 비근무 상태
    ANNUAL_LEAVE = "연차"
    MATERNITY_LEAVE = "배우자출산"
    SICK_LEAVE = "병가"
    BUSINESS_TRIP = "출장"

class ObservationFeature(Enum):
    """관측값 특성 정의"""
    TAG_LOCATION = "태그위치"
    TIME_INTERVAL = "시간간격"
    DAY_OF_WEEK = "요일"
    TIME_PERIOD = "시간대"
    WORK_AREA_TYPE = "근무구역여부"
    ABC_ACTIVITY = "ABC작업분류"
    ATTENDANCE_STATUS = "근태상태"
    EXCLUDE_TIME = "제외시간여부"
    CAFETERIA_LOCATION = "CAFETERIA위치"
    SHIFT_TYPE = "교대구분"

class HMMModel:
    """HMM 모델 클래스"""
    
    def __init__(self, model_name: str = "work_activity_hmm"):
        """
        Args:
            model_name: 모델 이름
        """
        self.model_name = model_name
        self.logger = logging.getLogger(__name__)
        
        # 상태 정의
        self.states = [state.value for state in ActivityState]
        self.n_states = len(self.states)
        self.state_to_index = {state: i for i, state in enumerate(self.states)}
        self.index_to_state = {i: state for i, state in enumerate(self.states)}
        
        # 관측값 특성
        self.observation_features = [feature.value for feature in ObservationFeature]
        
        # 모델 파라미터 초기화
        self.transition_matrix = None
        self.emission_matrix = None
        self.initial_probabilities = None
        
        # 식사시간 정의 (24시간 2교대 근무 반영)
        self.meal_time_windows = {
            'breakfast': (time(6, 30), time(9, 0)),
            'lunch': (time(11, 20), time(13, 20)),
            'dinner': (time(17, 0), time(20, 0)),
            'midnight_meal': [(time(23, 30), time(23, 59)), (time(0, 0), time(1, 0))]
        }
        
        # 시간대 정의
        self.time_periods = {
            'early_morning': (time(5, 0), time(9, 0)),
            'morning': (time(9, 0), time(12, 0)),
            'afternoon': (time(12, 0), time(18, 0)),
            'evening': (time(18, 0), time(22, 0)),
            'night': (time(22, 0), time(5, 0))
        }
        
        self.logger.info(f"HMM 모델 초기화 완료: {model_name}")
    
    def initialize_parameters(self, initialization_method: str = "uniform"):
        """
        모델 파라미터 초기화
        
        Args:
            initialization_method: 초기화 방법 ('uniform', 'random', 'domain_knowledge')
        """
        if initialization_method == "uniform":
            self._initialize_uniform()
        elif initialization_method == "random":
            self._initialize_random()
        elif initialization_method == "domain_knowledge":
            self._initialize_domain_knowledge()
        else:
            raise ValueError(f"지원하지 않는 초기화 방법: {initialization_method}")
        
        self.logger.info(f"파라미터 초기화 완료: {initialization_method}")
    
    def _initialize_uniform(self):
        """균등 분포로 초기화"""
        # 전이 확률 행렬
        self.transition_matrix = np.full((self.n_states, self.n_states), 1.0 / self.n_states)
        
        # 초기 상태 확률
        self.initial_probabilities = np.full(self.n_states, 1.0 / self.n_states)
        
        # 방출 확률 행렬 (관측값 특성별로 초기화)
        self.emission_matrix = {}
        for feature in self.observation_features:
            # 각 특성별로 임의의 관측값 개수 설정 (실제 데이터 기반으로 업데이트 필요)
            n_observations = 10  # 기본값
            self.emission_matrix[feature] = np.full((self.n_states, n_observations), 1.0 / n_observations)
    
    def _initialize_random(self):
        """랜덤 분포로 초기화"""
        np.random.seed(42)  # 재현성을 위한 시드 설정
        
        # 전이 확률 행렬
        self.transition_matrix = np.random.dirichlet(np.ones(self.n_states), size=self.n_states)
        
        # 초기 상태 확률
        self.initial_probabilities = np.random.dirichlet(np.ones(self.n_states))
        
        # 방출 확률 행렬
        self.emission_matrix = {}
        for feature in self.observation_features:
            n_observations = 10  # 기본값
            self.emission_matrix[feature] = np.random.dirichlet(np.ones(n_observations), size=self.n_states)
    
    def _initialize_domain_knowledge(self):
        """도메인 지식 기반 초기화"""
        # 전이 확률 행렬 (도메인 지식 기반)
        self.transition_matrix = np.zeros((self.n_states, self.n_states))
        
        # 각 상태별 전이 확률 설정
        for i, from_state in enumerate(self.states):
            for j, to_state in enumerate(self.states):
                self.transition_matrix[i, j] = self._get_transition_probability(from_state, to_state)
        
        # 행별 정규화
        for i in range(self.n_states):
            total = np.sum(self.transition_matrix[i, :])
            if total > 0:
                self.transition_matrix[i, :] /= total
        
        # 초기 상태 확률 (출근 상태가 높은 확률)
        self.initial_probabilities = np.zeros(self.n_states)
        for i, state in enumerate(self.states):
            if state == ActivityState.CLOCK_IN.value:
                self.initial_probabilities[i] = 0.3
            elif state == ActivityState.WORK.value:
                self.initial_probabilities[i] = 0.2
            elif state == ActivityState.MOVEMENT.value:
                self.initial_probabilities[i] = 0.1
            else:
                self.initial_probabilities[i] = 0.4 / (self.n_states - 3)
        
        # 방출 확률 행렬 (도메인 지식 기반)
        self.emission_matrix = {}
        for feature in self.observation_features:
            self.emission_matrix[feature] = self._initialize_emission_matrix(feature)
    
    def _get_transition_probability(self, from_state: str, to_state: str) -> float:
        """상태 간 전이 확률 계산 (도메인 지식 기반)"""
        # 기본 전이 확률
        base_prob = 0.01
        
        # 상태별 전이 규칙
        if from_state == ActivityState.CLOCK_IN.value:
            if to_state == ActivityState.WORK.value:
                return 0.4
            elif to_state == ActivityState.MOVEMENT.value:
                return 0.3
            elif to_state == ActivityState.BREAKFAST.value:
                return 0.2
        
        elif from_state == ActivityState.WORK.value:
            if to_state == ActivityState.FOCUSED_WORK.value:
                return 0.3
            elif to_state == ActivityState.MEETING.value:
                return 0.2
            elif to_state == ActivityState.REST.value:
                return 0.1
            elif to_state == ActivityState.MOVEMENT.value:
                return 0.2
        
        elif from_state == ActivityState.BREAKFAST.value:
            if to_state == ActivityState.WORK.value:
                return 0.5
            elif to_state == ActivityState.MOVEMENT.value:
                return 0.3
        
        elif from_state == ActivityState.LUNCH.value:
            if to_state == ActivityState.WORK.value:
                return 0.6
            elif to_state == ActivityState.REST.value:
                return 0.2
        
        elif from_state == ActivityState.DINNER.value:
            if to_state == ActivityState.WORK.value:
                return 0.4
            elif to_state == ActivityState.CLOCK_OUT.value:
                return 0.3
        
        elif from_state == ActivityState.MIDNIGHT_MEAL.value:
            if to_state == ActivityState.WORK.value:
                return 0.5
            elif to_state == ActivityState.CLOCK_OUT.value:
                return 0.2
        
        elif from_state == ActivityState.MOVEMENT.value:
            if to_state == ActivityState.WORK.value:
                return 0.2
            elif to_state in [ActivityState.BREAKFAST.value, ActivityState.LUNCH.value, 
                            ActivityState.DINNER.value, ActivityState.MIDNIGHT_MEAL.value]:
                return 0.1
        
        # 같은 상태 유지 확률
        if from_state == to_state:
            return 0.3
        
        return base_prob
    
    def _initialize_emission_matrix(self, feature: str) -> np.ndarray:
        """특성별 방출 확률 행렬 초기화"""
        # 특성별 기본 관측값 개수 설정
        n_observations_map = {
            ObservationFeature.TAG_LOCATION.value: 50,
            ObservationFeature.TIME_INTERVAL.value: 20,
            ObservationFeature.DAY_OF_WEEK.value: 7,
            ObservationFeature.TIME_PERIOD.value: 5,
            ObservationFeature.WORK_AREA_TYPE.value: 2,
            ObservationFeature.ABC_ACTIVITY.value: 15,
            ObservationFeature.ATTENDANCE_STATUS.value: 10,
            ObservationFeature.EXCLUDE_TIME.value: 2,
            ObservationFeature.CAFETERIA_LOCATION.value: 2,
            ObservationFeature.SHIFT_TYPE.value: 2
        }
        
        n_observations = n_observations_map.get(feature, 10)
        emission_matrix = np.full((self.n_states, n_observations), 1.0 / n_observations)
        
        # 특성별 도메인 지식 적용
        if feature == ObservationFeature.CAFETERIA_LOCATION.value:
            for i, state in enumerate(self.states):
                if state in [ActivityState.BREAKFAST.value, ActivityState.LUNCH.value,
                           ActivityState.DINNER.value, ActivityState.MIDNIGHT_MEAL.value]:
                    emission_matrix[i, 1] = 0.9  # CAFETERIA 위치 높은 확률
                    emission_matrix[i, 0] = 0.1  # 기타 위치 낮은 확률
        
        elif feature == ObservationFeature.SHIFT_TYPE.value:
            for i, state in enumerate(self.states):
                if state == ActivityState.MIDNIGHT_MEAL.value:
                    emission_matrix[i, 1] = 0.8  # 야간 교대 높은 확률
                    emission_matrix[i, 0] = 0.2  # 주간 교대 낮은 확률
        
        return emission_matrix
    
    def extract_observations(self, tag_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        태그 데이터에서 관측값 추출
        
        Args:
            tag_data: 태그 데이터 DataFrame
            
        Returns:
            List[Dict]: 관측값 시퀀스
        """
        observations = []
        
        for _, row in tag_data.iterrows():
            obs = {}
            
            # 태그 위치
            obs[ObservationFeature.TAG_LOCATION.value] = row.get('DR_NO', 'unknown')
            
            # 시간 간격 (이전 태그와의 시간 차이)
            obs[ObservationFeature.TIME_INTERVAL.value] = self._calculate_time_interval(row)
            
            # 요일
            obs[ObservationFeature.DAY_OF_WEEK.value] = row.get('DAY_NM', 'unknown')
            
            # 시간대
            obs[ObservationFeature.TIME_PERIOD.value] = self._get_time_period(row.get('datetime'))
            
            # 근무구역 여부
            obs[ObservationFeature.WORK_AREA_TYPE.value] = row.get('work_area_type', 'work')
            
            # ABC 작업 분류 (있는 경우)
            obs[ObservationFeature.ABC_ACTIVITY.value] = row.get('activity_classification', 'none')
            
            # 근태 상태
            obs[ObservationFeature.ATTENDANCE_STATUS.value] = row.get('attendance_status', 'normal')
            
            # 제외시간 여부
            obs[ObservationFeature.EXCLUDE_TIME.value] = row.get('exclude_time_flag', False)
            
            # CAFETERIA 위치
            obs[ObservationFeature.CAFETERIA_LOCATION.value] = self._is_cafeteria_location(row.get('DR_NM', ''))
            
            # 교대 구분
            obs[ObservationFeature.SHIFT_TYPE.value] = row.get('shift_type', '주간')
            
            observations.append(obs)
        
        return observations
    
    def _calculate_time_interval(self, row: pd.Series) -> str:
        """시간 간격 계산"""
        # 실제 구현에서는 이전 태그와의 시간 차이를 계산
        # 여기서는 간단한 분류로 처리
        return "medium"  # short, medium, long
    
    def _get_time_period(self, timestamp: datetime) -> str:
        """시간대 분류"""
        if timestamp is None:
            return "unknown"
        
        current_time = timestamp.time()
        
        for period, (start, end) in self.time_periods.items():
            if period == "night":
                # 야간 시간대 (22:00-05:00)
                if current_time >= start or current_time < end:
                    return period
            else:
                if start <= current_time < end:
                    return period
        
        return "unknown"
    
    def _is_cafeteria_location(self, location_name: str) -> bool:
        """CAFETERIA 위치 여부 확인"""
        return 'CAFETERIA' in location_name.upper()
    
    def predict_activity_sequence(self, observations: List[Dict[str, Any]]) -> List[str]:
        """
        관측값 시퀀스로부터 활동 상태 시퀀스 예측
        
        Args:
            observations: 관측값 시퀀스
            
        Returns:
            List[str]: 예측된 활동 상태 시퀀스
        """
        if not observations:
            return []
        
        # 간단한 규칙 기반 예측 (Viterbi 알고리즘 구현 전)
        predicted_states = []
        
        for obs in observations:
            # CAFETERIA 위치이고 식사시간대인 경우
            if obs.get(ObservationFeature.CAFETERIA_LOCATION.value):
                meal_state = self._predict_meal_state(obs)
                if meal_state:
                    predicted_states.append(meal_state)
                    continue
            
            # 근무구역 여부에 따른 예측
            if obs.get(ObservationFeature.WORK_AREA_TYPE.value) == 'work':
                predicted_states.append(ActivityState.WORK.value)
            else:
                predicted_states.append(ActivityState.MOVEMENT.value)
        
        return predicted_states
    
    def _predict_meal_state(self, obs: Dict[str, Any]) -> Optional[str]:
        """식사 상태 예측"""
        time_period = obs.get(ObservationFeature.TIME_PERIOD.value)
        
        if time_period == "early_morning":
            return ActivityState.BREAKFAST.value
        elif time_period == "afternoon":
            return ActivityState.LUNCH.value
        elif time_period == "evening":
            return ActivityState.DINNER.value
        elif time_period == "night":
            return ActivityState.MIDNIGHT_MEAL.value
        
        return None
    
    def get_model_summary(self) -> Dict[str, Any]:
        """모델 요약 정보"""
        return {
            'model_name': self.model_name,
            'n_states': self.n_states,
            'states': self.states,
            'observation_features': self.observation_features,
            'meal_time_windows': {k: str(v) for k, v in self.meal_time_windows.items()},
            'time_periods': {k: str(v) for k, v in self.time_periods.items()},
            'is_initialized': self.transition_matrix is not None
        }
    
    def save_model(self, filepath: str):
        """모델 저장"""
        model_data = {
            'model_name': self.model_name,
            'states': self.states,
            'observation_features': self.observation_features,
            'transition_matrix': self.transition_matrix.tolist() if self.transition_matrix is not None else None,
            'initial_probabilities': self.initial_probabilities.tolist() if self.initial_probabilities is not None else None,
            'emission_matrix': {k: v.tolist() for k, v in self.emission_matrix.items()} if self.emission_matrix else None,
            'meal_time_windows': {k: str(v) for k, v in self.meal_time_windows.items()},
            'time_periods': {k: str(v) for k, v in self.time_periods.items()}
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(model_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"모델 저장 완료: {filepath}")
    
    def load_model(self, filepath: str):
        """모델 로드"""
        with open(filepath, 'r', encoding='utf-8') as f:
            model_data = json.load(f)
        
        self.model_name = model_data['model_name']
        self.states = model_data['states']
        self.observation_features = model_data['observation_features']
        
        if model_data['transition_matrix']:
            self.transition_matrix = np.array(model_data['transition_matrix'])
        
        if model_data['initial_probabilities']:
            self.initial_probabilities = np.array(model_data['initial_probabilities'])
        
        if model_data['emission_matrix']:
            self.emission_matrix = {k: np.array(v) for k, v in model_data['emission_matrix'].items()}
        
        self.logger.info(f"모델 로드 완료: {filepath}")
    
    def validate_model(self) -> Dict[str, Any]:
        """모델 검증"""
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': []
        }
        
        # 전이 확률 행렬 검증
        if self.transition_matrix is not None:
            for i in range(self.n_states):
                row_sum = np.sum(self.transition_matrix[i, :])
                if not np.isclose(row_sum, 1.0):
                    validation_result['errors'].append(f"전이 확률 행렬 {i}행의 합이 1이 아닙니다: {row_sum}")
        
        # 초기 확률 검증
        if self.initial_probabilities is not None:
            prob_sum = np.sum(self.initial_probabilities)
            if not np.isclose(prob_sum, 1.0):
                validation_result['errors'].append(f"초기 확률의 합이 1이 아닙니다: {prob_sum}")
        
        # 방출 확률 행렬 검증
        if self.emission_matrix:
            for feature, matrix in self.emission_matrix.items():
                for i in range(self.n_states):
                    row_sum = np.sum(matrix[i, :])
                    if not np.isclose(row_sum, 1.0):
                        validation_result['errors'].append(f"방출 확률 행렬 {feature} {i}행의 합이 1이 아닙니다: {row_sum}")
        
        validation_result['is_valid'] = len(validation_result['errors']) == 0
        
        return validation_result