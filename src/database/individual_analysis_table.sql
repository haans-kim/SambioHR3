-- 개인별 일간 분석 결과 저장 테이블
-- 조직별 분석에서 생성되는 개인별 일간 데이터를 저장

CREATE TABLE IF NOT EXISTS individual_daily_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 기본 정보
    employee_id VARCHAR(20) NOT NULL,
    employee_name VARCHAR(50),
    department VARCHAR(100),
    center VARCHAR(100),
    team VARCHAR(100),
    analysis_date DATE NOT NULL,
    
    -- 근태 및 실제 작업 시간
    attendance_hours FLOAT,        -- 근태기록시간 (출퇴근 기록 기반)
    actual_work_hours FLOAT,       -- 실제 작업시간 (태그 분석 기반)
    work_estimation_rate FLOAT,    -- 작업시간 추정률 (%)
    
    -- 활동별 시간 분석
    meeting_hours FLOAT,           -- 회의시간
    meal_hours FLOAT,              -- 식사시간 (조식, 중식, 석식, 야식)
    movement_hours FLOAT,          -- 이동시간
    rest_hours FLOAT,              -- 휴식시간
    
    -- 식사 세부 분석
    breakfast_time FLOAT,          -- 조식 시간
    lunch_time FLOAT,              -- 중식 시간  
    dinner_time FLOAT,             -- 석식 시간
    midnight_meal_time FLOAT,      -- 야식 시간
    
    -- 교대 근무 정보
    shift_type VARCHAR(20),        -- 주간/야간
    cross_day_flag BOOLEAN DEFAULT 0,  -- 날짜 교차 근무
    
    -- 데이터 품질 지표
    data_reliability FLOAT,        -- 데이터 신뢰도 (0-100)
    tag_count INTEGER,             -- 태그 수
    data_completeness FLOAT,       -- 데이터 완전성 (%)
    
    -- 효율성 지표
    work_efficiency FLOAT,         -- 업무 효율성 (%)
    productivity_score FLOAT,      -- 생산성 점수
    
    -- 메타데이터
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    analysis_version VARCHAR(20),
    
    -- 인덱스
    UNIQUE(employee_id, analysis_date),
    INDEX idx_employee (employee_id),
    INDEX idx_date (analysis_date),
    INDEX idx_department (department, center, team)
);