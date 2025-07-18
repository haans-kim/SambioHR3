"""
데이터베이스 스키마 정의
2교대 근무 시스템을 반영한 테이블 구조를 정의합니다.
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import logging

Base = declarative_base()

class DailyWorkData(Base):
    """개인별 일간 데이터 (2교대 근무 반영)"""
    __tablename__ = 'daily_work_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(20), nullable=False, index=True)
    work_date = Column(DateTime, nullable=False, index=True)
    shift_type = Column(String(10), nullable=False)  # '주간', '야간' 구분
    actual_work_time = Column(Float, nullable=True)
    work_time = Column(Float, nullable=True)
    rest_time = Column(Float, nullable=True)
    non_work_time = Column(Float, nullable=True)
    meal_time = Column(Float, nullable=True)  # 4번 식사시간 합계
    breakfast_time = Column(Float, nullable=True)  # 조식시간
    lunch_time = Column(Float, nullable=True)      # 중식시간
    dinner_time = Column(Float, nullable=True)     # 석식시간
    midnight_meal_time = Column(Float, nullable=True)  # 야식시간
    cross_day_flag = Column(Boolean, default=False)  # 출근일과 퇴근일이 다른 경우
    efficiency_ratio = Column(Float, nullable=True)
    data_quality_score = Column(Float, nullable=True)  # 데이터 품질 점수
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ShiftWorkData(Base):
    """교대근무 시간 데이터"""
    __tablename__ = 'shift_work_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(20), nullable=False, index=True)
    work_date = Column(DateTime, nullable=False, index=True)
    clock_in_time = Column(DateTime, nullable=True)
    clock_out_time = Column(DateTime, nullable=True)
    shift_duration = Column(Float, nullable=True)
    cross_midnight = Column(Boolean, default=False)  # 자정을 넘나는 근무
    shift_pattern = Column(String(20), nullable=True)  # 교대 패턴
    created_at = Column(DateTime, default=datetime.utcnow)

class OrganizationSummary(Base):
    """조직별 집계 데이터"""
    __tablename__ = 'organization_summary'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(String(50), nullable=False, index=True)
    org_name = Column(String(100), nullable=False)
    org_level = Column(String(20), nullable=True)  # 센터, BU, 팀, 그룹, 파트
    date = Column(DateTime, nullable=False, index=True)
    avg_work_time = Column(Float, nullable=True)
    avg_efficiency_ratio = Column(Float, nullable=True)
    operation_rate = Column(Float, nullable=True)
    total_employees = Column(Integer, nullable=True)
    day_shift_count = Column(Integer, nullable=True)
    night_shift_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class TagLogs(Base):
    """태그 로그 데이터"""
    __tablename__ = 'tag_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    tag_location = Column(String(100), nullable=False)
    gate_number = Column(String(20), nullable=True)
    gate_name = Column(String(100), nullable=True)
    action_type = Column(String(10), nullable=False)  # 입문, 출문
    work_area_type = Column(String(20), nullable=True)  # work, non_work
    meal_type = Column(String(20), nullable=True)  # breakfast, lunch, dinner, midnight_meal
    is_tailgating = Column(Boolean, default=False)
    confidence_score = Column(Float, nullable=True)  # 신뢰도 점수
    created_at = Column(DateTime, default=datetime.utcnow)

class AbcActivityData(Base):
    """ABC 작업 활동 데이터"""
    __tablename__ = 'abc_activity_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(20), nullable=False, index=True)
    work_date = Column(DateTime, nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    department_code = Column(String(50), nullable=True)
    department_name = Column(String(100), nullable=True)
    activity_code_1 = Column(String(50), nullable=True)
    activity_code_2 = Column(String(50), nullable=True)
    activity_code_3 = Column(String(50), nullable=True)
    activity_classification = Column(String(50), nullable=True)
    activity_target = Column(String(100), nullable=True)
    duration_minutes = Column(Integer, nullable=False)
    duration_hours = Column(Float, nullable=False)
    activity_major = Column(String(100), nullable=True)
    activity_medium = Column(String(100), nullable=True)
    activity_minor = Column(String(100), nullable=True)
    activity_hierarchy = Column(String(300), nullable=True)
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class ClaimData(Base):
    """근무시간 Claim 데이터"""
    __tablename__ = 'claim_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(20), nullable=False, index=True)
    work_date = Column(DateTime, nullable=False, index=True)
    employee_name = Column(String(50), nullable=False)
    department = Column(String(100), nullable=True)
    position = Column(String(50), nullable=True)
    work_schedule_type = Column(String(50), nullable=True)
    claimed_work_hours = Column(String(10), nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    exclude_time = Column(Float, nullable=True)
    attendance_name = Column(String(50), nullable=True)
    attendance_code = Column(String(20), nullable=True)
    cross_day_work = Column(Boolean, default=False)
    actual_work_duration = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class AttendanceData(Base):
    """근태 사용 데이터"""
    __tablename__ = 'attendance_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(20), nullable=False, index=True)
    employee_name = Column(String(50), nullable=False)
    department_name = Column(String(100), nullable=True)
    position_name = Column(String(50), nullable=True)
    attendance_code = Column(String(20), nullable=True)
    attendance_name = Column(String(50), nullable=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    attendance_days = Column(Integer, nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    attendance_hours = Column(Float, nullable=True)
    reason = Column(String(200), nullable=True)
    reason_detail = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class NonWorkTimeData(Base):
    """비근무시간 데이터"""
    __tablename__ = 'non_work_time_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(20), nullable=False, index=True)
    work_date = Column(DateTime, nullable=False, index=True)
    exclude_time_code = Column(String(20), nullable=True)
    exclude_time_type = Column(String(50), nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    exclude_duration = Column(Float, nullable=True)
    input_type = Column(String(20), nullable=True)
    is_reflected = Column(Boolean, default=True)
    table_type = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class EmployeeInfo(Base):
    """직원 정보"""
    __tablename__ = 'employee_info'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(20), nullable=False, unique=True, index=True)
    employee_name = Column(String(50), nullable=False)
    gender = Column(String(10), nullable=True)
    join_year = Column(String(10), nullable=True)
    nationality = Column(String(20), nullable=True)
    position_name = Column(String(50), nullable=True)
    position_type = Column(String(50), nullable=True)
    join_route = Column(String(50), nullable=True)
    group_join_date = Column(DateTime, nullable=True)
    company_join_date = Column(DateTime, nullable=True)
    internal_dept_code = Column(String(50), nullable=True)
    department_code = Column(String(50), nullable=True)
    department_name = Column(String(100), nullable=True)
    center = Column(String(100), nullable=True)
    bu = Column(String(100), nullable=True)
    team = Column(String(100), nullable=True)
    group_name = Column(String(100), nullable=True)
    part = Column(String(100), nullable=True)
    employment_status = Column(String(20), nullable=True)
    employee_type = Column(String(50), nullable=True)
    job_title = Column(String(50), nullable=True)
    job_function = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TagLocationMaster(Base):
    """태깅 지점 마스터"""
    __tablename__ = 'tag_location_master'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sort_no = Column(Integer, nullable=True)
    source_file = Column(String(100), nullable=True)
    location = Column(String(100), nullable=False)
    device_number = Column(String(20), nullable=False, unique=True)
    gate_name = Column(String(200), nullable=False)
    display_name = Column(String(200), nullable=False)
    inout_type = Column(String(10), nullable=True)  # IN, OUT
    work_area_flag = Column(String(10), nullable=True)  # G(일반), W(근무구역)
    work_classification = Column(String(10), nullable=True)  # M(근무), N(비근무)
    labeling = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class OrganizationMapping(Base):
    """조직 매핑"""
    __tablename__ = 'organization_mapping'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    center = Column(String(100), nullable=True)
    division = Column(String(100), nullable=True)
    team = Column(String(100), nullable=True)
    group_name = Column(String(100), nullable=True)
    part = Column(String(100), nullable=True)
    unit = Column(String(100), nullable=True)
    code = Column(String(50), nullable=True)
    changed_dept_name = Column(String(100), nullable=True)
    org_level = Column(Integer, nullable=True)
    parent_center = Column(String(100), nullable=True)
    english_dept_name = Column(String(200), nullable=True)
    job_title = Column(String(50), nullable=True)
    position = Column(String(50), nullable=True)
    employee_id = Column(String(20), nullable=True)
    employee_name = Column(String(50), nullable=True)
    rr_description = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class HmmModelConfig(Base):
    """HMM 모델 설정"""
    __tablename__ = 'hmm_model_config'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(20), nullable=False)
    states = Column(Text, nullable=False)  # JSON 형태로 저장
    transition_matrix = Column(Text, nullable=False)  # JSON 형태로 저장
    emission_matrix = Column(Text, nullable=False)  # JSON 형태로 저장
    initial_probabilities = Column(Text, nullable=False)  # JSON 형태로 저장
    model_parameters = Column(Text, nullable=True)  # JSON 형태로 저장
    training_accuracy = Column(Float, nullable=True)
    validation_accuracy = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ProcessingLog(Base):
    """처리 로그"""
    __tablename__ = 'processing_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    process_type = Column(String(50), nullable=False)  # data_loading, hmm_analysis, etc.
    employee_id = Column(String(20), nullable=True)
    process_date = Column(DateTime, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False)  # success, failed, running
    processed_records = Column(Integer, nullable=True)
    error_count = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    processing_details = Column(Text, nullable=True)  # JSON 형태로 저장
    created_at = Column(DateTime, default=datetime.utcnow)

class DatabaseSchema:
    """데이터베이스 스키마 관리 클래스"""
    
    def __init__(self, database_url: str = "sqlite:///data/sambio_human.db"):
        """
        Args:
            database_url: 데이터베이스 연결 URL
        """
        self.database_url = database_url
        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.logger = logging.getLogger(__name__)
    
    def create_tables(self):
        """모든 테이블 생성"""
        try:
            Base.metadata.create_all(bind=self.engine)
            self.logger.info("모든 테이블 생성 완료")
        except Exception as e:
            self.logger.error(f"테이블 생성 실패: {e}")
            raise
    
    def drop_tables(self):
        """모든 테이블 삭제"""
        try:
            Base.metadata.drop_all(bind=self.engine)
            self.logger.info("모든 테이블 삭제 완료")
        except Exception as e:
            self.logger.error(f"테이블 삭제 실패: {e}")
            raise
    
    def get_session(self):
        """데이터베이스 세션 반환"""
        return self.SessionLocal()
    
    def get_table_info(self) -> dict:
        """테이블 정보 반환"""
        from sqlalchemy import inspect
        inspector = inspect(self.engine)
        table_info = {}
        
        for table_name in inspector.get_table_names():
            columns = inspector.get_columns(table_name)
            table_info[table_name] = {
                'columns': [(col['name'], str(col['type'])) for col in columns],
                'column_count': len(columns)
            }
        
        return table_info
    
    def execute_query(self, query: str):
        """SQL 쿼리 실행"""
        try:
            with self.engine.connect() as connection:
                result = connection.execute(query)
                return result.fetchall()
        except Exception as e:
            self.logger.error(f"쿼리 실행 실패: {e}")
            raise