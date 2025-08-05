-- 조직분석 통합 관리 시스템 데이터베이스 스키마
-- 생성일: 2025-08-05
-- 설명: 개인별 분석 결과 저장 및 조직별 집계를 위한 테이블 및 뷰

-- 1. 개인별 일일 분석 결과 저장 테이블
CREATE TABLE IF NOT EXISTS daily_analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    analysis_date DATE NOT NULL,
    
    -- 조직 정보 (집계를 위한 denormalization)
    center_id TEXT,
    center_name TEXT,
    group_id TEXT,
    group_name TEXT,
    team_id TEXT,
    team_name TEXT,
    
    -- 시간 관련 지표
    work_start TIMESTAMP,
    work_end TIMESTAMP,
    total_hours REAL,              -- 총 체류시간
    actual_work_hours REAL,        -- 실제 근무시간
    claimed_work_hours REAL,       -- 신고 근무시간
    efficiency_ratio REAL,         -- 효율성 비율 (%)
    
    -- 활동별 시간 (분 단위)
    work_minutes INTEGER DEFAULT 0,          -- 업무 시간 (WORK + FOCUSED_WORK + EQUIPMENT_OPERATION)
    focused_work_minutes INTEGER DEFAULT 0,  -- 집중 업무
    equipment_minutes INTEGER DEFAULT 0,     -- 장비 조작
    meeting_minutes INTEGER DEFAULT 0,       -- 회의 시간
    training_minutes INTEGER DEFAULT 0,      -- 교육 시간
    
    -- 식사 시간 상세 (분 단위)
    meal_minutes INTEGER DEFAULT 0,          -- 식사 시간 (전체)
    breakfast_minutes INTEGER DEFAULT 0,     -- 조식
    lunch_minutes INTEGER DEFAULT 0,         -- 중식
    dinner_minutes INTEGER DEFAULT 0,        -- 석식
    midnight_meal_minutes INTEGER DEFAULT 0, -- 야식
    
    -- 기타 활동 시간 (분 단위)
    movement_minutes INTEGER DEFAULT 0,      -- 이동 시간
    rest_minutes INTEGER DEFAULT 0,          -- 휴식 시간
    fitness_minutes INTEGER DEFAULT 0,       -- 피트니스 시간
    commute_in_minutes INTEGER DEFAULT 0,    -- 출근 시간
    commute_out_minutes INTEGER DEFAULT 0,   -- 퇴근 시간
    preparation_minutes INTEGER DEFAULT 0,   -- 준비 시간
    
    -- 구역별 시간 (분 단위)
    work_area_minutes INTEGER DEFAULT 0,     -- 근무구역 (Y)
    non_work_area_minutes INTEGER DEFAULT 0, -- 비근무구역 (N)
    gate_area_minutes INTEGER DEFAULT 0,     -- 게이트 (G)
    
    -- 기타 지표
    confidence_score REAL DEFAULT 0,         -- 데이터 신뢰도 (0-100)
    activity_count INTEGER DEFAULT 0,        -- 활동 전환 횟수
    meal_count INTEGER DEFAULT 0,            -- 식사 횟수
    tag_count INTEGER DEFAULT 0,             -- 태그 기록 수
    
    -- 근무 패턴
    shift_type TEXT,                         -- 근무 유형 (주간/야간/특수)
    work_type TEXT,                          -- 근무제 (정규/탄력/자율)
    
    -- 메타데이터
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(employee_id, analysis_date)
);

-- 2. 조직별 일일 집계 테이블 (선택적 - Materialized View 대체용)
CREATE TABLE IF NOT EXISTS organization_daily_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id TEXT NOT NULL,     -- 센터/그룹/팀 ID
    organization_name TEXT,            -- 조직명
    organization_type TEXT NOT NULL,   -- 'center', 'group', 'team'
    summary_date DATE NOT NULL,
    
    -- 상위 조직 정보
    parent_org_id TEXT,
    parent_org_name TEXT,
    
    -- 인원 통계
    total_employees INTEGER DEFAULT 0,           -- 전체 인원
    analyzed_employees INTEGER DEFAULT 0,        -- 분석된 인원
    coverage_rate REAL DEFAULT 0,                -- 커버리지 비율 (%)
    
    -- 평균 지표
    avg_total_hours REAL DEFAULT 0,
    avg_actual_work_hours REAL DEFAULT 0,
    avg_claimed_work_hours REAL DEFAULT 0,
    avg_efficiency_ratio REAL DEFAULT 0,
    avg_confidence_score REAL DEFAULT 0,
    
    -- 활동별 평균 시간 (시간 단위)
    avg_work_hours REAL DEFAULT 0,
    avg_meeting_hours REAL DEFAULT 0,
    avg_meal_hours REAL DEFAULT 0,
    avg_movement_hours REAL DEFAULT 0,
    avg_rest_hours REAL DEFAULT 0,
    avg_training_hours REAL DEFAULT 0,
    
    -- 구역별 평균 비율
    avg_work_area_ratio REAL DEFAULT 0,         -- 근무구역 비율 (%)
    avg_non_work_area_ratio REAL DEFAULT 0,     -- 비근무구역 비율 (%)
    
    -- 효율성 분포
    efficiency_90_plus INTEGER DEFAULT 0,        -- 효율 90% 이상 인원
    efficiency_80_90 INTEGER DEFAULT 0,          -- 효율 80-90% 인원
    efficiency_70_80 INTEGER DEFAULT 0,          -- 효율 70-80% 인원
    efficiency_below_70 INTEGER DEFAULT 0,       -- 효율 70% 미만 인원
    
    -- 근무 패턴 분포
    day_shift_count INTEGER DEFAULT 0,           -- 주간 근무자 수
    night_shift_count INTEGER DEFAULT 0,         -- 야간 근무자 수
    special_shift_count INTEGER DEFAULT 0,       -- 특수 근무자 수
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(organization_id, organization_type, summary_date)
);

-- 3. 인덱스 생성
-- daily_analysis_results 인덱스
CREATE INDEX IF NOT EXISTS idx_dar_date ON daily_analysis_results(analysis_date);
CREATE INDEX IF NOT EXISTS idx_dar_employee ON daily_analysis_results(employee_id);
CREATE INDEX IF NOT EXISTS idx_dar_employee_date ON daily_analysis_results(employee_id, analysis_date);
CREATE INDEX IF NOT EXISTS idx_dar_center ON daily_analysis_results(center_id, analysis_date);
CREATE INDEX IF NOT EXISTS idx_dar_group ON daily_analysis_results(group_id, analysis_date);
CREATE INDEX IF NOT EXISTS idx_dar_team ON daily_analysis_results(team_id, analysis_date);
CREATE INDEX IF NOT EXISTS idx_dar_efficiency ON daily_analysis_results(efficiency_ratio);
CREATE INDEX IF NOT EXISTS idx_dar_created ON daily_analysis_results(created_at);

-- organization_daily_summary 인덱스
CREATE INDEX IF NOT EXISTS idx_ods_date ON organization_daily_summary(summary_date);
CREATE INDEX IF NOT EXISTS idx_ods_org ON organization_daily_summary(organization_id, organization_type);
CREATE INDEX IF NOT EXISTS idx_ods_org_date ON organization_daily_summary(organization_id, organization_type, summary_date);

-- 4. 트리거 생성 (updated_at 자동 업데이트)
DROP TRIGGER IF EXISTS update_dar_timestamp;
CREATE TRIGGER update_dar_timestamp 
AFTER UPDATE ON daily_analysis_results
BEGIN
    UPDATE daily_analysis_results 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE id = NEW.id;
END;