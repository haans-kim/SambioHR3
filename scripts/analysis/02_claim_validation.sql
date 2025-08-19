-- 02_claim_validation.sql
-- Claim 데이터와 태그 기반 추정 비교

-- Claim 데이터와 태그 추정 비교
WITH tag_estimation AS (
    SELECT 
        t.사번,
        t.ENTE_DT as 날짜,
        COUNT(*) as 태그수,
        -- 간단한 추정: 태그수 기반 근무시간 (개선 필요)
        MIN(t.출입시각) as 첫태그,
        MAX(t.출입시각) as 막태그,
        (MAX(t.출입시각) - MIN(t.출입시각)) / 100.0 as 추정_근무시간
    FROM tag_data t
    GROUP BY t.사번, t.ENTE_DT
),
claim_comparison AS (
    SELECT 
        c.사번,
        c.근무일,
        c.실제근무시간 as claim_시간,
        t.추정_근무시간 as 태그_추정시간,
        ABS(c.실제근무시간 - t.추정_근무시간) as 오차,
        o.센터,
        o.팀
    FROM claim_data c
    JOIN tag_estimation t 
        ON c.사번 = t.사번 
        AND DATE(c.근무일) = DATE('2025-06-' || SUBSTR('0' || t.날짜, -2, 2))
    JOIN organization_data o ON c.사번 = o.사번
    WHERE c.실제근무시간 > 0
)
SELECT 
    센터,
    팀,
    COUNT(*) as 비교건수,
    ROUND(AVG(claim_시간), 2) as 평균_claim,
    ROUND(AVG(태그_추정시간), 2) as 평균_추정,
    ROUND(AVG(오차), 2) as 평균_오차,
    ROUND(AVG(오차) / AVG(claim_시간) * 100, 1) as 오차율
FROM claim_comparison
GROUP BY 센터, 팀
HAVING COUNT(*) >= 100
ORDER BY 오차율;