-- 조직분석 통합 관리 시스템 뷰(View) 생성 스크립트
-- 생성일: 2025-08-05
-- 설명: 조직별 실시간 집계를 위한 뷰

-- 1. 센터별 일일 집계 View
DROP VIEW IF EXISTS v_center_daily_summary;
CREATE VIEW v_center_daily_summary AS
SELECT 
    dar.analysis_date,
    dar.center_id,
    dar.center_name,
    
    -- 인원 통계
    COUNT(DISTINCT dar.employee_id) as analyzed_employees,
    (SELECT COUNT(DISTINCT employee_id) FROM employees WHERE center_id = dar.center_id) as total_employees,
    ROUND(COUNT(DISTINCT dar.employee_id) * 100.0 / 
          NULLIF((SELECT COUNT(DISTINCT employee_id) FROM employees WHERE center_id = dar.center_id), 0), 1) as coverage_rate,
    
    -- 시간 지표 평균
    ROUND(AVG(dar.total_hours), 1) as avg_total_hours,
    ROUND(AVG(dar.actual_work_hours), 1) as avg_actual_work_hours,
    ROUND(AVG(dar.claimed_work_hours), 1) as avg_claimed_hours,
    ROUND(AVG(dar.efficiency_ratio), 1) as avg_efficiency_ratio,
    
    -- 활동별 평균 시간 (시간 단위)
    ROUND(AVG(dar.work_minutes) / 60.0, 1) as avg_work_hours,
    ROUND(AVG(dar.meeting_minutes) / 60.0, 1) as avg_meeting_hours,
    ROUND(AVG(dar.meal_minutes) / 60.0, 1) as avg_meal_hours,
    ROUND(AVG(dar.movement_minutes) / 60.0, 1) as avg_movement_hours,
    ROUND(AVG(dar.rest_minutes) / 60.0, 1) as avg_rest_hours,
    ROUND(AVG(dar.training_minutes) / 60.0, 1) as avg_training_hours,
    
    -- 구역별 비율
    ROUND(AVG(CASE 
        WHEN (dar.work_area_minutes + dar.non_work_area_minutes + dar.gate_area_minutes) > 0 
        THEN dar.work_area_minutes * 100.0 / (dar.work_area_minutes + dar.non_work_area_minutes + dar.gate_area_minutes)
        ELSE 0 
    END), 1) as avg_work_area_ratio,
    
    ROUND(AVG(CASE 
        WHEN (dar.work_area_minutes + dar.non_work_area_minutes + dar.gate_area_minutes) > 0 
        THEN dar.non_work_area_minutes * 100.0 / (dar.work_area_minutes + dar.non_work_area_minutes + dar.gate_area_minutes)
        ELSE 0 
    END), 1) as avg_non_work_area_ratio,
    
    -- 효율성 분포
    SUM(CASE WHEN dar.efficiency_ratio >= 90 THEN 1 ELSE 0 END) as efficiency_90_plus,
    SUM(CASE WHEN dar.efficiency_ratio >= 80 AND dar.efficiency_ratio < 90 THEN 1 ELSE 0 END) as efficiency_80_90,
    SUM(CASE WHEN dar.efficiency_ratio >= 70 AND dar.efficiency_ratio < 80 THEN 1 ELSE 0 END) as efficiency_70_80,
    SUM(CASE WHEN dar.efficiency_ratio < 70 THEN 1 ELSE 0 END) as efficiency_below_70,
    
    -- 데이터 품질
    ROUND(AVG(dar.confidence_score), 1) as avg_confidence_score,
    
    -- 근무 패턴
    SUM(CASE WHEN dar.shift_type = '야간근무' THEN 1 ELSE 0 END) as night_shift_count,
    SUM(CASE WHEN dar.shift_type = '주간근무' THEN 1 ELSE 0 END) as day_shift_count,
    SUM(CASE WHEN dar.shift_type NOT IN ('주간근무', '야간근무') THEN 1 ELSE 0 END) as special_shift_count
    
FROM daily_analysis_results dar
GROUP BY dar.analysis_date, dar.center_id, dar.center_name;

-- 2. 그룹별 일일 집계 View
DROP VIEW IF EXISTS v_group_daily_summary;
CREATE VIEW v_group_daily_summary AS
SELECT 
    dar.analysis_date,
    dar.center_id,
    dar.center_name,
    dar.group_id,
    dar.group_name,
    
    -- 인원 통계
    COUNT(DISTINCT dar.employee_id) as analyzed_employees,
    (SELECT COUNT(DISTINCT employee_id) FROM employees WHERE group_id = dar.group_id) as total_employees,
    ROUND(COUNT(DISTINCT dar.employee_id) * 100.0 / 
          NULLIF((SELECT COUNT(DISTINCT employee_id) FROM employees WHERE group_id = dar.group_id), 0), 1) as coverage_rate,
    
    -- 시간 지표 평균
    ROUND(AVG(dar.total_hours), 1) as avg_total_hours,
    ROUND(AVG(dar.actual_work_hours), 1) as avg_actual_work_hours,
    ROUND(AVG(dar.claimed_work_hours), 1) as avg_claimed_hours,
    ROUND(AVG(dar.efficiency_ratio), 1) as avg_efficiency_ratio,
    
    -- 활동별 평균 시간 (시간 단위)
    ROUND(AVG(dar.work_minutes) / 60.0, 1) as avg_work_hours,
    ROUND(AVG(dar.meeting_minutes) / 60.0, 1) as avg_meeting_hours,
    ROUND(AVG(dar.meal_minutes) / 60.0, 1) as avg_meal_hours,
    ROUND(AVG(dar.movement_minutes) / 60.0, 1) as avg_movement_hours,
    ROUND(AVG(dar.rest_minutes) / 60.0, 1) as avg_rest_hours,
    
    -- 효율성 분포
    SUM(CASE WHEN dar.efficiency_ratio >= 90 THEN 1 ELSE 0 END) as efficiency_90_plus,
    SUM(CASE WHEN dar.efficiency_ratio >= 80 AND dar.efficiency_ratio < 90 THEN 1 ELSE 0 END) as efficiency_80_90,
    SUM(CASE WHEN dar.efficiency_ratio >= 70 AND dar.efficiency_ratio < 80 THEN 1 ELSE 0 END) as efficiency_70_80,
    SUM(CASE WHEN dar.efficiency_ratio < 70 THEN 1 ELSE 0 END) as efficiency_below_70,
    
    -- 데이터 품질
    ROUND(AVG(dar.confidence_score), 1) as avg_confidence_score
    
FROM daily_analysis_results dar
GROUP BY dar.analysis_date, dar.center_id, dar.center_name, dar.group_id, dar.group_name;

-- 3. 팀별 일일 집계 View
DROP VIEW IF EXISTS v_team_daily_summary;
CREATE VIEW v_team_daily_summary AS
SELECT 
    dar.analysis_date,
    dar.center_id,
    dar.center_name,
    dar.group_id,
    dar.group_name,
    dar.team_id,
    dar.team_name,
    
    -- 인원 통계
    COUNT(DISTINCT dar.employee_id) as analyzed_employees,
    (SELECT COUNT(DISTINCT employee_id) FROM employees WHERE team_id = dar.team_id) as total_employees,
    ROUND(COUNT(DISTINCT dar.employee_id) * 100.0 / 
          NULLIF((SELECT COUNT(DISTINCT employee_id) FROM employees WHERE team_id = dar.team_id), 0), 1) as coverage_rate,
    
    -- 시간 지표 평균
    ROUND(AVG(dar.total_hours), 1) as avg_total_hours,
    ROUND(AVG(dar.actual_work_hours), 1) as avg_actual_work_hours,
    ROUND(AVG(dar.claimed_work_hours), 1) as avg_claimed_hours,
    ROUND(AVG(dar.efficiency_ratio), 1) as avg_efficiency_ratio,
    
    -- 활동별 평균 시간
    ROUND(AVG(dar.work_minutes) / 60.0, 1) as avg_work_hours,
    ROUND(AVG(dar.meeting_minutes) / 60.0, 1) as avg_meeting_hours,
    ROUND(AVG(dar.meal_minutes) / 60.0, 1) as avg_meal_hours,
    
    -- 효율성 분포
    SUM(CASE WHEN dar.efficiency_ratio >= 90 THEN 1 ELSE 0 END) as efficiency_90_plus,
    SUM(CASE WHEN dar.efficiency_ratio >= 80 AND dar.efficiency_ratio < 90 THEN 1 ELSE 0 END) as efficiency_80_90,
    SUM(CASE WHEN dar.efficiency_ratio < 80 THEN 1 ELSE 0 END) as efficiency_below_80,
    
    -- 데이터 품질
    ROUND(AVG(dar.confidence_score), 1) as avg_confidence_score
    
FROM daily_analysis_results dar
GROUP BY dar.analysis_date, dar.center_id, dar.center_name, 
         dar.group_id, dar.group_name, dar.team_id, dar.team_name;

-- 4. 개인별 상세 View (조직 정보 포함)
DROP VIEW IF EXISTS v_employee_daily_analysis;
CREATE VIEW v_employee_daily_analysis AS
SELECT 
    dar.*,
    
    -- 추가 계산 필드
    CASE 
        WHEN dar.efficiency_ratio >= 90 THEN '우수'
        WHEN dar.efficiency_ratio >= 80 THEN '양호'
        WHEN dar.efficiency_ratio >= 70 THEN '주의'
        ELSE '개선필요'
    END as efficiency_grade,
    
    CASE
        WHEN dar.meal_count >= 4 THEN '야간근무'
        WHEN dar.meal_count >= 2 THEN '주간근무'
        WHEN dar.meal_count = 1 THEN '반일근무'
        ELSE '특수근무'
    END as estimated_shift_type,
    
    -- 활동 시간 비율
    ROUND(dar.work_minutes * 100.0 / NULLIF(dar.total_hours * 60, 0), 1) as work_ratio,
    ROUND(dar.meeting_minutes * 100.0 / NULLIF(dar.total_hours * 60, 0), 1) as meeting_ratio,
    ROUND(dar.meal_minutes * 100.0 / NULLIF(dar.total_hours * 60, 0), 1) as meal_ratio,
    ROUND(dar.rest_minutes * 100.0 / NULLIF(dar.total_hours * 60, 0), 1) as rest_ratio
    
FROM daily_analysis_results dar;

-- 5. 조직별 주간 트렌드 View
DROP VIEW IF EXISTS v_organization_weekly_trend;
CREATE VIEW v_organization_weekly_trend AS
SELECT 
    strftime('%Y-W%W', dar.analysis_date) as week,
    dar.center_id,
    dar.center_name,
    'center' as org_type,
    
    -- 주간 평균
    ROUND(AVG(dar.efficiency_ratio), 1) as weekly_avg_efficiency,
    ROUND(AVG(dar.actual_work_hours), 1) as weekly_avg_work_hours,
    ROUND(AVG(dar.total_hours), 1) as weekly_avg_total_hours,
    
    -- 주간 통계
    COUNT(DISTINCT dar.employee_id) as unique_employees,
    COUNT(*) as total_records,
    
    -- 주간 근무 패턴
    SUM(CASE WHEN dar.shift_type = '야간근무' THEN 1 ELSE 0 END) as night_shift_days,
    SUM(CASE WHEN dar.shift_type = '주간근무' THEN 1 ELSE 0 END) as day_shift_days
    
FROM daily_analysis_results dar
GROUP BY strftime('%Y-W%W', dar.analysis_date), dar.center_id, dar.center_name

UNION ALL

SELECT 
    strftime('%Y-W%W', dar.analysis_date) as week,
    dar.group_id as organization_id,
    dar.group_name as organization_name,
    'group' as org_type,
    
    ROUND(AVG(dar.efficiency_ratio), 1) as weekly_avg_efficiency,
    ROUND(AVG(dar.actual_work_hours), 1) as weekly_avg_work_hours,
    ROUND(AVG(dar.total_hours), 1) as weekly_avg_total_hours,
    
    COUNT(DISTINCT dar.employee_id) as unique_employees,
    COUNT(*) as total_records,
    
    SUM(CASE WHEN dar.shift_type = '야간근무' THEN 1 ELSE 0 END) as night_shift_days,
    SUM(CASE WHEN dar.shift_type = '주간근무' THEN 1 ELSE 0 END) as day_shift_days
    
FROM daily_analysis_results dar
GROUP BY strftime('%Y-W%W', dar.analysis_date), dar.group_id, dar.group_name;

-- 6. 효율성 순위 View
DROP VIEW IF EXISTS v_efficiency_ranking;
CREATE VIEW v_efficiency_ranking AS
WITH latest_date AS (
    SELECT MAX(analysis_date) as max_date FROM daily_analysis_results
)
SELECT 
    'center' as org_type,
    center_id as org_id,
    center_name as org_name,
    analysis_date,
    avg_efficiency_ratio,
    analyzed_employees,
    total_employees,
    coverage_rate,
    RANK() OVER (PARTITION BY analysis_date ORDER BY avg_efficiency_ratio DESC) as efficiency_rank
FROM v_center_daily_summary
WHERE analysis_date = (SELECT max_date FROM latest_date)

UNION ALL

SELECT 
    'group' as org_type,
    group_id as org_id,
    group_name as org_name,
    analysis_date,
    avg_efficiency_ratio,
    analyzed_employees,
    total_employees,
    coverage_rate,
    RANK() OVER (PARTITION BY analysis_date ORDER BY avg_efficiency_ratio DESC) as efficiency_rank
FROM v_group_daily_summary
WHERE analysis_date = (SELECT max_date FROM latest_date)

UNION ALL

SELECT 
    'team' as org_type,
    team_id as org_id,
    team_name as org_name,
    analysis_date,
    avg_efficiency_ratio,
    analyzed_employees,
    total_employees,
    coverage_rate,
    RANK() OVER (PARTITION BY analysis_date ORDER BY avg_efficiency_ratio DESC) as efficiency_rank
FROM v_team_daily_summary
WHERE analysis_date = (SELECT max_date FROM latest_date);