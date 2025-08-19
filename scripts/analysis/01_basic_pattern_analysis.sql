-- 01_basic_pattern_analysis.sql
-- 부서별 기본 패턴 분석 (즉시 실행 가능)

-- 1. 부서별 위치 패턴 분석
CREATE TEMP TABLE IF NOT EXISTS dept_location_patterns AS
WITH team_patterns AS (
    SELECT 
        o.센터,
        o.BU,
        o.팀,
        COUNT(DISTINCT o.사번) as 직원수,
        COUNT(t.사번) as 총태그수,
        
        -- 위치별 비율 계산
        ROUND(COUNT(CASE WHEN t.DR_NM LIKE '%P3%' OR t.DR_NM LIKE '%P4%' 
                   OR t.DR_NM LIKE '%P5%' THEN 1 END) * 100.0 / 
              NULLIF(COUNT(t.사번), 0), 1) as 생산동_비율,
        
        ROUND(COUNT(CASE WHEN t.DR_NM LIKE '%정문%' THEN 1 END) * 100.0 / 
              NULLIF(COUNT(t.사번), 0), 1) as 정문_비율,
        
        ROUND(COUNT(CASE WHEN t.DR_NM LIKE '%브릿지%' OR t.DR_NM LIKE '%브리지%' 
                   THEN 1 END) * 100.0 / 
              NULLIF(COUNT(t.사번), 0), 1) as 이동통로_비율,
        
        -- 활동 지표
        ROUND(COUNT(t.사번) * 1.0 / NULLIF(COUNT(DISTINCT o.사번), 0) / 20, 1) as 일평균_태그수,
        COUNT(DISTINCT t.DR_NM) as 위치_다양성
        
    FROM organization_data o
    LEFT JOIN tag_data t ON o.사번 = t.사번
    WHERE o.센터 IS NOT NULL
    GROUP BY o.센터, o.BU, o.팀
    HAVING 직원수 >= 20  -- 통계적 유의성
)
SELECT 
    센터,
    팀,
    직원수,
    생산동_비율,
    정문_비율,
    이동통로_비율,
    일평균_태그수,
    위치_다양성,
    
    -- 패턴 분류 (3개 주요 그룹)
    CASE 
        WHEN 생산동_비율 >= 80 THEN 'Type_A_생산중심'
        WHEN 생산동_비율 >= 20 THEN 'Type_B_혼합형'
        ELSE 'Type_C_사무중심'
    END as 패턴_유형
    
FROM team_patterns
ORDER BY 생산동_비율 DESC;

-- 결과 확인
SELECT 
    패턴_유형,
    COUNT(*) as 팀수,
    SUM(직원수) as 총인원,
    ROUND(AVG(생산동_비율), 1) as 평균_생산동,
    ROUND(AVG(일평균_태그수), 1) as 평균_태그
FROM dept_location_patterns
GROUP BY 패턴_유형
ORDER BY 패턴_유형;

-- 2. 부서별 신뢰도 점수 계산
CREATE TEMP TABLE IF NOT EXISTS dept_reliability_scores AS
SELECT 
    센터,
    팀,
    직원수,
    생산동_비율,
    일평균_태그수,
    위치_다양성,
    패턴_유형,
    
    -- 신뢰도 점수 계산 (0~1)
    ROUND(
        (생산동_비율 / 100.0) * 0.4 +  -- 위치 고정성 40%
        MIN(일평균_태그수 / 15.0, 1.0) * 0.3 +  -- 데이터 밀도 30%
        (1.0 - MIN(위치_다양성 / 100.0, 1.0)) * 0.3,  -- 패턴 단순성 30%
        3
    ) as 신뢰도_점수,
    
    -- 보정 Factor 도출
    CASE 
        WHEN 패턴_유형 = 'Type_A_생산중심' THEN 0.96
        WHEN 패턴_유형 = 'Type_B_혼합형' THEN 0.92
        ELSE 0.88
    END as 보정_factor
    
FROM dept_location_patterns;

-- 결과 저장을 위한 출력
SELECT * FROM dept_reliability_scores
ORDER BY 신뢰도_점수 DESC;