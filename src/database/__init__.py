"""
데이터베이스 모듈

이 모듈은 SQLAlchemy를 사용한 데이터베이스 스키마, 매니저, 모델을 제공합니다.
2교대 근무 시스템과 4번 식사시간을 반영한 데이터베이스 구조를 포함합니다.
"""

from .schema import (
    Base, DatabaseSchema,
    DailyWorkData, ShiftWorkData, OrganizationSummary, TagLogs,
    AbcActivityData, ClaimData, AttendanceData, NonWorkTimeData,
    EmployeeInfo, TagLocationMaster, OrganizationMapping,
    HmmModelConfig, ProcessingLog
)
from .db_manager import DatabaseManager
from .models import (
    Employee, DailyWorkSummary, OrgSummary,
    ProcessedTagData, HMMModel, InteractionNetwork,
    MovementNetwork, DailyActivity, ACTIVITY_STATES, TIME_WINDOWS
)
from .singleton_manager import (
    SingletonDatabaseManager, 
    SingletonPickleManager,
    get_database_manager,
    get_pickle_manager,
    reset_singletons
)

__all__ = [
    # Schema
    'Base', 'DatabaseSchema',
    'DailyWorkData', 'ShiftWorkData', 'OrganizationSummary', 'TagLogs',
    'AbcActivityData', 'ClaimData', 'AttendanceData', 'NonWorkTimeData',
    'EmployeeInfo', 'TagLocationMaster', 'OrganizationMapping',
    'HmmModelConfig', 'ProcessingLog',
    
    # Manager
    'DatabaseManager',
    'SingletonDatabaseManager',
    'SingletonPickleManager',
    'get_database_manager',
    'get_pickle_manager',
    'reset_singletons',
    
    # Models
    'Employee', 'DailyWorkSummary', 'OrgSummary',
    'ProcessedTagData', 'HMMModel', 'InteractionNetwork',
    'MovementNetwork', 'DailyActivity', 'ACTIVITY_STATES', 'TIME_WINDOWS'
]