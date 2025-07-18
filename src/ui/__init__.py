"""
UI 모듈

Streamlit 기반 사용자 인터페이스를 제공합니다.
2교대 근무 시스템 분석 대시보드의 모든 UI 컴포넌트를 포함합니다.
"""

from .streamlit_app import SambioHumanApp
from .components import (
    IndividualDashboard,
    OrganizationDashboard,
    DataUploadComponent,
    ModelConfigComponent
)

__all__ = [
    'SambioHumanApp',
    'IndividualDashboard',
    'OrganizationDashboard',
    'DataUploadComponent',
    'ModelConfigComponent'
]

# 버전 정보
__version__ = '1.0.0'
__author__ = 'Sambio Human Analytics Team'
__description__ = 'Streamlit UI for 2-Shift Work Analysis Dashboard'