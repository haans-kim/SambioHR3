from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, ForeignKey, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime

Base = declarative_base()


class Employee(Base):
    """직원 정보 테이블"""
    __tablename__ = 'employees'
    
    employee_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    department = Column(String)
    position = Column(String)
    start_date = Column(Date)
    
    # Relationships
    daily_summaries = relationship("DailyWorkSummary", back_populates="employee")
    processed_tags = relationship("ProcessedTagData", back_populates="employee")
    
    def __repr__(self):
        return f"<Employee(id={self.employee_id}, name={self.name})>"


class DailyWorkSummary(Base):
    """일일 근무 요약 테이블"""
    __tablename__ = 'daily_work_summary'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String, ForeignKey('employees.employee_id'))
    date = Column(Date, nullable=False)
    total_time = Column(Integer)  # 총 시간 (분)
    work_time = Column(Integer)  # 근무 시간
    focused_work_time = Column(Integer)  # 집중근무 시간
    rest_time = Column(Integer)  # 휴식 시간
    movement_time = Column(Integer)  # 이동 시간
    meal_time = Column(Integer)  # 식사 시간
    meeting_time = Column(Integer)  # 회의 시간
    equipment_time = Column(Integer)  # 장비조작 시간
    utilization_rate = Column(Float)  # 가동률
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    employee = relationship("Employee", back_populates="daily_summaries")
    
    def __repr__(self):
        return f"<DailyWorkSummary(employee={self.employee_id}, date={self.date})>"


class OrgSummary(Base):
    """조직 요약 데이터 테이블"""
    __tablename__ = 'org_summary'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    avg_work_time = Column(Float)
    avg_utilization_rate = Column(Float)
    total_employees = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<OrgSummary(org={self.org_id}, date={self.date})>"


class ProcessedTagData(Base):
    """전처리된 태그 데이터 테이블"""
    __tablename__ = 'processed_tag_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String, ForeignKey('employees.employee_id'))
    timestamp = Column(DateTime, nullable=False)
    location = Column(String)
    activity_state = Column(String)
    confidence_score = Column(Float)
    duration_minutes = Column(Float)
    is_interpolated = Column(Boolean, default=False)
    
    # Relationships
    employee = relationship("Employee", back_populates="processed_tags")
    
    def __repr__(self):
        return f"<ProcessedTagData(employee={self.employee_id}, time={self.timestamp})>"


class HMMModel(Base):
    """HMM 모델 설정 테이블"""
    __tablename__ = 'hmm_models'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String, unique=True, nullable=False)
    transition_matrix = Column(Text)  # JSON 형태
    emission_matrix = Column(Text)  # JSON 형태
    states = Column(Text)  # JSON 형태
    observations = Column(Text)  # JSON 형태
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<HMMModel(name={self.model_name}, version={self.version})>"


class InteractionNetwork(Base):
    """네트워크 분석 데이터 테이블"""
    __tablename__ = 'interaction_networks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    time_window = Column(String)  # morning, afternoon, evening, night
    employee1_id = Column(String, ForeignKey('employees.employee_id'))
    employee2_id = Column(String, ForeignKey('employees.employee_id'))
    interaction_type = Column(String)  # co-location, meeting, collaboration
    duration = Column(Integer)  # 상호작용 시간 (분)
    location = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<InteractionNetwork({self.employee1_id}<->{self.employee2_id})>"


class MovementNetwork(Base):
    """공간 이동 네트워크 테이블"""
    __tablename__ = 'movement_networks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String, ForeignKey('employees.employee_id'))
    date = Column(Date, nullable=False)
    from_location = Column(String)
    to_location = Column(String)
    movement_time = Column(DateTime)
    transition_count = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<MovementNetwork({self.from_location}->{self.to_location})>"


class DailyActivity(Base):
    """일일 활동 상세 테이블"""
    __tablename__ = 'daily_activities'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String, ForeignKey('employees.employee_id'))
    date = Column(Date, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    activity_type = Column(String, nullable=False)
    location = Column(String)
    duration_minutes = Column(Float)
    created_at = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<DailyActivity({self.employee_id}, {self.activity_type})>"


# 활동 상태 상수
ACTIVITY_STATES = {
    'WORK': '근무',
    'FOCUSED_WORK': '집중근무',
    'MOVEMENT': '이동',
    'MEAL': '식사',
    'FITNESS': '피트니스',
    'COMMUTE': '출근/퇴근',
    'LEAVE': '연차',
    'EQUIPMENT': '장비조작',
    'MEETING': '회의',
    'REST': '휴식',
    'WORK_PREP': '작업준비',
    'ACTIVE_WORK': '작업중'
}

# 시간대 구분
TIME_WINDOWS = {
    'MORNING': (6, 12),
    'AFTERNOON': (12, 18),
    'EVENING': (18, 22),
    'NIGHT': (22, 6)
}