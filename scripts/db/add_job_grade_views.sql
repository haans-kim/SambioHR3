-- 직급별 집계를 위한 추가 뷰 생성
-- 생성일: 2025-08-05

-- 1. 직급 정보를 daily_analysis_results에 추가하기 위한 컬럼 추가
ALTER TABLE daily_analysis_results ADD COLUMN job_grade TEXT;

-- 2. 센터-직급별 일일 집계 View
DROP VIEW IF EXISTS v_center_grade_daily_summary;
CREATE VIEW v_center_grade_daily_summary AS
SELECT 
    dar.analysis_date,
    dar.center_id,
    dar.center_name,
    dar.job_grade,
    
    -- 인원 통계
    COUNT(DISTINCT dar.employee_id) as employee_count,
    
    -- 효율성 평균
    ROUND(AVG(dar.efficiency_ratio), 1) as avg_efficiency_ratio,
    
    -- 효율성 분포
    CASE 
        WHEN AVG(dar.efficiency_ratio) >= 90 THEN 'green'
        WHEN AVG(dar.efficiency_ratio) >= 80 THEN 'blue'
        ELSE 'red'
    END as efficiency_color,
    
    -- 이전 날짜 대비 변화 (임시로 0으로 설정)
    0 as efficiency_change
    
FROM daily_analysis_results dar
WHERE dar.job_grade IS NOT NULL
GROUP BY dar.analysis_date, dar.center_id, dar.center_name, dar.job_grade;

-- 3. 그룹-직급별 일일 집계 View
DROP VIEW IF EXISTS v_group_grade_daily_summary;
CREATE VIEW v_group_grade_daily_summary AS
SELECT 
    dar.analysis_date,
    dar.center_id,
    dar.center_name,
    dar.group_id,
    dar.group_name,
    dar.job_grade,
    
    -- 인원 통계
    COUNT(DISTINCT dar.employee_id) as employee_count,
    
    -- 효율성 평균
    ROUND(AVG(dar.efficiency_ratio), 1) as avg_efficiency_ratio,
    
    -- 효율성 분포
    CASE 
        WHEN AVG(dar.efficiency_ratio) >= 90 THEN 'green'
        WHEN AVG(dar.efficiency_ratio) >= 80 THEN 'blue'
        ELSE 'red'
    END as efficiency_color,
    
    -- 이전 날짜 대비 변화
    0 as efficiency_change
    
FROM daily_analysis_results dar
WHERE dar.job_grade IS NOT NULL
GROUP BY dar.analysis_date, dar.center_id, dar.center_name, 
         dar.group_id, dar.group_name, dar.job_grade;