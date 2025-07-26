"""
태그 기반 활동 분류 시스템을 위한 데이터베이스 스키마
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, ForeignKey, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class TagMaster(Base):
    """태그 마스터 테이블"""
    __tablename__ = 'tag_master'
    
    tag_code = Column(String(10), primary_key=True)
    tag_name = Column(String(100), nullable=False)
    tag_category = Column(String(20), nullable=False)  # G, N, T, M, O
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계
    mappings = relationship("LocationTagMapping", back_populates="tag")
    
    def __repr__(self):
        return f"<TagMaster(tag_code='{self.tag_code}', tag_name='{self.tag_name}')>"

class LocationTagMapping(Base):
    """위치 정보와 태그 코드 매핑 테이블"""
    __tablename__ = 'location_tag_mapping'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    location_code = Column(String(50), nullable=False, index=True)
    location_name = Column(String(200), nullable=True)
    tag_code = Column(String(10), ForeignKey('tag_master.tag_code'), nullable=False)
    mapping_confidence = Column(Float, default=1.0)
    mapping_rule = Column(Text, nullable=True)  # 매핑 규칙 설명
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계
    tag = relationship("TagMaster", back_populates="mappings")
    
    # 인덱스
    __table_args__ = (
        Index('idx_location_tag', 'location_code', 'tag_code'),
    )

class StateTransitionRules(Base):
    """상태 전환 규칙 테이블"""
    __tablename__ = 'state_transition_rules'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    from_tag = Column(String(10), nullable=False, index=True)
    to_tag = Column(String(10), nullable=False, index=True)
    from_state = Column(String(50), nullable=True)
    to_state = Column(String(50), nullable=False)
    base_probability = Column(Float, default=0.1)
    time_condition = Column(JSON, nullable=True)  # {"start": "11:20", "end": "13:20"}
    location_condition = Column(JSON, nullable=True)  # {"type": "CAFETERIA"}
    shift_condition = Column(String(20), nullable=True)  # "day", "night"
    duration_condition = Column(JSON, nullable=True)  # {"min": 5, "max": 30}
    priority = Column(Integer, default=100)  # 낮을수록 우선순위 높음
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 인덱스
    __table_args__ = (
        Index('idx_transition_tags', 'from_tag', 'to_tag'),
        Index('idx_transition_states', 'from_state', 'to_state'),
    )

class ActivityStates(Base):
    """활동 상태 정의 테이블"""
    __tablename__ = 'activity_states'
    
    state_code = Column(String(50), primary_key=True)
    state_name = Column(String(100), nullable=False)
    state_category = Column(String(50), nullable=True)  # work, meal, rest, movement
    description = Column(Text, nullable=True)
    color_code = Column(String(10), nullable=True)  # 시각화용 색상 코드
    is_work_time = Column(Boolean, default=True)  # 실근무시간 포함 여부
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=999)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TagSequencePatterns(Base):
    """태그 시퀀스 패턴 정의 테이블"""
    __tablename__ = 'tag_sequence_patterns'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    pattern_name = Column(String(100), nullable=False)
    pattern_type = Column(String(50), nullable=False)  # normal, anomaly, meal, shift_change
    tag_sequence = Column(JSON, nullable=False)  # ["T2", "G2", "G1"]
    state_sequence = Column(JSON, nullable=False)  # ["출입(IN)", "준비", "업무"]
    min_duration_minutes = Column(Integer, nullable=True)
    max_duration_minutes = Column(Integer, nullable=True)
    confidence_score = Column(Float, default=0.9)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TagProcessingLog(Base):
    """태그 처리 로그 테이블"""
    __tablename__ = 'tag_processing_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(20), nullable=False, index=True)
    process_date = Column(DateTime, nullable=False, index=True)
    original_location = Column(String(200), nullable=True)
    mapped_tag = Column(String(10), nullable=False)
    predicted_state = Column(String(50), nullable=False)
    confidence_score = Column(Float, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    rule_applied = Column(String(200), nullable=True)
    is_anomaly = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 인덱스
    __table_args__ = (
        Index('idx_processing_emp_date', 'employee_id', 'process_date'),
    )