"""
HMM (Hidden Markov Model) 모듈

이 모듈은 2교대 근무 시스템을 반영한 HMM 모델을 제공합니다.
태깅 데이터를 기반으로 근무 활동 상태를 예측하고 분석합니다.

주요 구성 요소:
- HMMModel: 기본 HMM 모델 클래스
- BaumWelchAlgorithm: 파라미터 학습 알고리즘
- ViterbiAlgorithm: 상태 시퀀스 예측 알고리즘
- HMMRuleEditor: 규칙 편집 및 관리 도구
"""

from .hmm_model import HMMModel, ActivityState, ObservationFeature
from .baum_welch import BaumWelchAlgorithm
from .viterbi import ViterbiAlgorithm
from .rule_editor import HMMRuleEditor

__all__ = [
    # 모델 클래스
    'HMMModel',
    'ActivityState',
    'ObservationFeature',
    
    # 알고리즘 클래스
    'BaumWelchAlgorithm',
    'ViterbiAlgorithm',
    
    # 유틸리티 클래스
    'HMMRuleEditor'
]

# 버전 정보
__version__ = '1.0.0'
__author__ = 'Sambio Human Analytics Team'
__description__ = 'HMM-based Work Activity Analysis for 2-Shift System'