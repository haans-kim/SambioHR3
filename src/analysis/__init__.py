"""
분석 엔진 모듈

이 모듈은 2교대 근무 시스템을 반영한 개인별 및 조직별 분석 기능을 제공합니다.
HMM 모델을 활용하여 태깅 데이터를 분석하고 근무 패턴을 파악합니다.

주요 구성 요소:
- IndividualAnalyzer: 개인별 근무 분석
- OrganizationAnalyzer: 조직별 근무 분석
"""

from .individual_analyzer import IndividualAnalyzer
from .organization_analyzer import OrganizationAnalyzer

__all__ = [
    'IndividualAnalyzer',
    'OrganizationAnalyzer'
]

# 버전 정보
__version__ = '1.0.0'
__author__ = 'Sambio Human Analytics Team'
__description__ = 'Work Analysis Engine for 2-Shift System'