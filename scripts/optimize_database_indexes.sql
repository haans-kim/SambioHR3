-- SambioHR3 Database Performance Optimization
-- 성능 최적화를 위한 인덱스 생성 스크립트
-- 목표: classify_activities 0.454초 → 0.150초 (66% 향상)

-- =============================================================================
-- 1. TAG_DATA 테이블 최적화 (가장 큰 병목)
-- =============================================================================

-- 개인별 + 날짜별 조회 최적화
CREATE INDEX IF NOT EXISTS idx_tag_data_employee_date 
ON tag_data("사번", "ENTE_DT");

-- 시간순 정렬 최적화
CREATE INDEX IF NOT EXISTS idx_tag_data_datetime_employee 
ON tag_data("ENTE_DT", "출입시각", "사번");

-- 위치별 조회 최적화 (게이트, 구역)
CREATE INDEX IF NOT EXISTS idx_tag_data_location_employee 
ON tag_data("DR_NM", "사번", "ENTE_DT");

-- IN/OUT 구분 조회 최적화
CREATE INDEX IF NOT EXISTS idx_tag_data_inout_employee 
ON tag_data("INOUT_GB", "사번", "ENTE_DT");

-- =============================================================================
-- 2. TAG_LOGS 테이블 추가 최적화
-- =============================================================================

-- 복합 인덱스로 기존 단일 인덱스 성능 향상
CREATE INDEX IF NOT EXISTS idx_tag_logs_employee_timestamp_action 
ON tag_logs(employee_id, timestamp, action_type);

-- 식사 시간 분석 최적화
CREATE INDEX IF NOT EXISTS idx_tag_logs_meal_analysis 
ON tag_logs(employee_id, meal_type, timestamp) 
WHERE meal_type IS NOT NULL;

-- 작업 영역 분석 최적화  
CREATE INDEX IF NOT EXISTS idx_tag_logs_work_area_analysis 
ON tag_logs(employee_id, work_area_type, timestamp)
WHERE work_area_type IS NOT NULL;

-- =============================================================================
-- 3. EQUIPMENT_LOGS 테이블 최적화
-- =============================================================================

-- 일별 장비 사용 분석 최적화
CREATE INDEX IF NOT EXISTS idx_equipment_logs_employee_date_type 
ON equipment_logs(employee_id, DATE(datetime), equipment_type);

-- 장비별 사용 시간 분석 최적화
CREATE INDEX IF NOT EXISTS idx_equipment_logs_type_employee_time 
ON equipment_logs(equipment_type, employee_id, datetime);

-- =============================================================================
-- 4. ATTENDANCE_DATA 테이블 최적화  
-- =============================================================================

-- 개인별 출근 기록 조회 최적화
CREATE INDEX IF NOT EXISTS idx_attendance_employee_startdate 
ON attendance_data(employee_id, start_date);

-- 날짜 범위 쿼리 최적화
CREATE INDEX IF NOT EXISTS idx_attendance_date_range 
ON attendance_data(start_date, end_date, employee_id);

-- 근태 유형별 조회 최적화
CREATE INDEX IF NOT EXISTS idx_attendance_code_employee_date 
ON attendance_data(attendance_code, employee_id, start_date);

-- =============================================================================
-- 5. DAILY_ANALYSIS_RESULTS 테이블 추가 최적화
-- =============================================================================

-- 조직별 집계 쿼리 최적화
CREATE INDEX IF NOT EXISTS idx_dar_center_date_efficiency 
ON daily_analysis_results(center_name, analysis_date, efficiency_ratio);

CREATE INDEX IF NOT EXISTS idx_dar_team_date_efficiency 
ON daily_analysis_results(team_name, analysis_date, efficiency_ratio);

-- 효율성 랭킹 쿼리 최적화
CREATE INDEX IF NOT EXISTS idx_dar_date_efficiency_desc 
ON daily_analysis_results(analysis_date, efficiency_ratio DESC);

-- 근무 시간 분석 최적화
CREATE INDEX IF NOT EXISTS idx_dar_employee_date_hours 
ON daily_analysis_results(employee_id, analysis_date, actual_work_hours);

-- =============================================================================
-- 6. 기타 성능 최적화 인덱스
-- =============================================================================

-- 조직 매핑 최적화 (빠른 조직 정보 조회)
CREATE INDEX IF NOT EXISTS idx_org_mapping_employee 
ON employee_organization_mapping(employee_id, is_active);

-- 시프트 근무 데이터 최적화
CREATE INDEX IF NOT EXISTS idx_shift_work_employee_date 
ON shift_work_data(employee_id, work_date);

-- 비근무시간 데이터 최적화
CREATE INDEX IF NOT EXISTS idx_non_work_time_employee_date 
ON non_work_time_data(employee_id, work_date);

-- =============================================================================
-- 인덱스 생성 완료 로그
-- =============================================================================

-- 생성된 인덱스 확인을 위한 뷰
CREATE VIEW IF NOT EXISTS v_performance_indexes AS
SELECT 
    name as index_name,
    tbl_name as table_name,
    sql as index_definition
FROM sqlite_master 
WHERE type = 'index' 
    AND name LIKE 'idx_tag_data_%' 
    OR name LIKE 'idx_tag_logs_%'
    OR name LIKE 'idx_equipment_logs_%' 
    OR name LIKE 'idx_attendance_%'
    OR name LIKE 'idx_dar_%'
ORDER BY tbl_name, name;

-- 성능 최적화 완료 확인
INSERT OR REPLACE INTO processing_log (process_type, process_date, start_time, status, processing_details)
VALUES (
    'INDEX_OPTIMIZATION', 
    datetime('now'), 
    datetime('now'),
    'COMPLETED', 
    'Performance optimization indexes created for tag_data, tag_logs, equipment_logs, attendance_data, daily_analysis_results'
);