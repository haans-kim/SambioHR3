# 조직분석 통합 관리 시스템 설계 문서

## 1. 개요

### 1.1 배경
- 현재 개인별 분석 기능만 구현되어 있음
- 조직별 통합 관리 및 작업지시 시스템 부재
- 개인별 분석 결과를 조직 단위로 집계하여 활용할 필요

### 1.2 목표
- 개인별 분석 지표를 DB에 체계적으로 저장
- 조직 계층별(센터/그룹/팀) 자동 집계
- 효율적인 조직별 대시보드 구현
- 작업지시 및 진행현황 통합 관리

## 2. 현재 시스템 분석

### 2.1 구현된 기능
1. **태그 기반 근무유형 분석 시스템**
   - 12개 태그 코드 (G1-G4, N1-N2, T1-T3, M1-M2, O)
   - 11개 상태 정의 (업무, 준비, 회의, 교육, 휴게, 식사, 경유, 출입 등)
   - 24시간 2교대 근무 시스템 지원

2. **개인별 분석 대시보드** (individual_dashboard.py)
   - 일일 활동 요약 및 시간 분석
   - Gantt 차트 형태의 타임라인 시각화
   - 근태 데이터와 실제 근무시간 비교

### 2.2 개인별 분석 지표 정리

#### 기본 지표
- `total_hours`: 총 체류시간
- `actual_work_hours`: 실제 근무시간
- `claimed_work_hours`: 신고 근무시간
- `efficiency_ratio`: 업무 효율성 (%)

#### 활동별 시간 (activity_summary)
- 업무: WORK, FOCUSED_WORK, EQUIPMENT_OPERATION
- 회의: MEETING, G3_MEETING
- 식사: BREAKFAST, LUNCH, DINNER, MIDNIGHT_MEAL
- 이동: MOVEMENT
- 휴식: REST, FITNESS
- 출퇴근: COMMUTE_IN, COMMUTE_OUT

#### 구역별 시간 (area_summary)
- Y: 근무구역 체류시간
- N: 비근무구역 체류시간
- G: 1선게이트 통과시간

#### 기타 지표
- `confidence_score`: 데이터 신뢰도
- `activity_count`: 활동 전환 횟수
- `meal_count`: 식사 횟수

## 3. 데이터베이스 설계

### 3.1 개인별 분석 결과 저장 테이블

```sql
-- 개인별 일일 분석 결과 저장
CREATE TABLE daily_analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    analysis_date DATE NOT NULL,
    
    -- 조직 정보 (집계를 위한 denormalization)
    center_id TEXT,
    group_id TEXT,
    team_id TEXT,
    
    -- 시간 관련 지표
    work_start TIMESTAMP,
    work_end TIMESTAMP,
    total_hours REAL,              -- 총 체류시간
    actual_work_hours REAL,        -- 실제 근무시간
    claimed_work_hours REAL,       -- 신고 근무시간
    efficiency_ratio REAL,         -- 효율성 비율
    
    -- 활동별 시간 (분 단위)
    work_minutes INTEGER,          -- 업무 시간
    focused_work_minutes INTEGER,  -- 집중 업무
    equipment_minutes INTEGER,     -- 장비 조작
    meeting_minutes INTEGER,       -- 회의 시간
    meal_minutes INTEGER,          -- 식사 시간 (전체)
    breakfast_minutes INTEGER,     -- 조식
    lunch_minutes INTEGER,         -- 중식
    dinner_minutes INTEGER,        -- 석식
    midnight_meal_minutes INTEGER, -- 야식
    movement_minutes INTEGER,      -- 이동 시간
    rest_minutes INTEGER,          -- 휴식 시간
    commute_minutes INTEGER,       -- 출퇴근 시간
    
    -- 구역별 시간 (분 단위)
    work_area_minutes INTEGER,     -- 근무구역 (Y)
    non_work_area_minutes INTEGER, -- 비근무구역 (N)
    gate_area_minutes INTEGER,     -- 게이트 (G)
    
    -- 기타 지표
    confidence_score REAL,         -- 데이터 신뢰도
    activity_count INTEGER,        -- 활동 전환 횟수
    meal_count INTEGER,            -- 식사 횟수
    
    -- 메타데이터
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(employee_id, analysis_date)
);
```

### 3.2 조직별 집계 테이블

```sql
-- 조직별 일일 집계 테이블
CREATE TABLE organization_daily_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id TEXT NOT NULL,     -- 센터/그룹/팀 ID
    organization_type TEXT NOT NULL,   -- 'center', 'group', 'team'
    summary_date DATE NOT NULL,
    
    -- 인원 통계
    total_employees INTEGER,           -- 전체 인원
    analyzed_employees INTEGER,        -- 분석된 인원
    
    -- 평균 지표
    avg_total_hours REAL,
    avg_actual_work_hours REAL,
    avg_efficiency_ratio REAL,
    avg_confidence_score REAL,
    
    -- 활동별 평균 시간
    avg_work_minutes REAL,
    avg_meeting_minutes REAL,
    avg_meal_minutes REAL,
    avg_movement_minutes REAL,
    avg_rest_minutes REAL,
    
    -- 구역별 평균 시간
    avg_work_area_ratio REAL,         -- 근무구역 비율
    avg_non_work_area_ratio REAL,     -- 비근무구역 비율
    
    -- 분포 통계
    efficiency_90_plus INTEGER,        -- 효율 90% 이상 인원
    efficiency_80_90 INTEGER,          -- 효율 80-90% 인원
    efficiency_below_80 INTEGER,       -- 효율 80% 미만 인원
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(organization_id, organization_type, summary_date)
);
```

### 3.3 조직별 View 설계

#### 센터별 실시간 집계 View
```sql
CREATE VIEW v_center_daily_summary AS
SELECT 
    dar.analysis_date,
    dar.center_id,
    org.center_name,
    
    -- 인원 통계
    COUNT(DISTINCT dar.employee_id) as analyzed_employees,
    COUNT(DISTINCT e.employee_id) as total_employees,
    ROUND(COUNT(DISTINCT dar.employee_id) * 100.0 / COUNT(DISTINCT e.employee_id), 1) as coverage_rate,
    
    -- 시간 지표 평균
    ROUND(AVG(dar.total_hours), 1) as avg_total_hours,
    ROUND(AVG(dar.actual_work_hours), 1) as avg_actual_work_hours,
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
LEFT JOIN employees e ON e.center_id = dar.center_id
LEFT JOIN organization_master org ON org.center_id = dar.center_id
GROUP BY dar.analysis_date, dar.center_id, org.center_name;
```

#### 개인별 상세 View (조직 정보 포함)
```sql
CREATE VIEW v_employee_daily_analysis AS
SELECT 
    dar.*,
    e.employee_name,
    e.position,
    e.job_grade,
    org.center_name,
    org.group_name,
    org.team_name,
    
    -- 추가 계산 필드
    CASE 
        WHEN dar.efficiency_ratio >= 90 THEN '우수'
        WHEN dar.efficiency_ratio >= 80 THEN '양호'
        ELSE '개선필요'
    END as efficiency_grade,
    
    CASE
        WHEN dar.meal_count = 4 THEN '야간근무'
        WHEN dar.meal_count >= 2 THEN '주간근무'
        ELSE '특수근무'
    END as shift_type
    
FROM daily_analysis_results dar
JOIN employees e ON e.employee_id = dar.employee_id
JOIN organization_master org ON org.team_id = e.team_id;
```

### 3.4 인덱스 전략

```sql
-- 성능 최적화를 위한 인덱스
CREATE INDEX idx_daily_analysis_date ON daily_analysis_results(analysis_date);
CREATE INDEX idx_daily_analysis_employee ON daily_analysis_results(employee_id);
CREATE INDEX idx_daily_analysis_org ON daily_analysis_results(center_id, group_id, team_id);
CREATE INDEX idx_dar_efficiency ON daily_analysis_results(efficiency_ratio);
CREATE INDEX idx_dar_date_center ON daily_analysis_results(analysis_date, center_id);
```

## 4. 구현 계획

### 4.1 Phase 1: 데이터 저장 구조 구현 (1주)

#### AnalysisResultSaver 클래스
```python
# src/analysis/analysis_result_saver.py

class AnalysisResultSaver:
    """개인별 분석 결과를 DB에 저장"""
    
    def save_individual_analysis(self, analysis_result: dict, employee_info: dict):
        """개인별 분석 결과 저장"""
        
        # analysis_result에서 필요한 데이터 추출
        data = {
            'employee_id': analysis_result['employee_id'],
            'analysis_date': analysis_result['analysis_date'],
            
            # 조직 정보
            'center_id': employee_info.get('center_id'),
            'group_id': employee_info.get('group_id'), 
            'team_id': employee_info.get('team_id'),
            
            # 시간 지표
            'total_hours': analysis_result['total_hours'],
            'actual_work_hours': analysis_result['work_time_analysis']['actual_work_hours'],
            'efficiency_ratio': analysis_result['work_time_analysis']['efficiency_ratio'],
            
            # 활동별 시간 집계
            'work_minutes': self._sum_work_activities(analysis_result['activity_summary']),
            'meeting_minutes': self._sum_meeting_activities(analysis_result['activity_summary']),
            # ... 기타 활동별 시간
        }
        
        # DB에 저장 (upsert)
        self.db_manager.upsert_daily_analysis(data)
```

### 4.2 Phase 2: 조직별 집계 로직 구현 (1주)

#### OrganizationAggregator 클래스
```python
# src/analysis/organization_aggregator.py

class OrganizationAggregator:
    """조직별 데이터 집계"""
    
    def aggregate_by_organization(self, date: date, org_type: str, org_id: str):
        """특정 조직의 특정 날짜 데이터 집계"""
        
        # View를 활용한 집계 데이터 조회
        if org_type == 'center':
            query = "SELECT * FROM v_center_daily_summary WHERE analysis_date = ? AND center_id = ?"
        elif org_type == 'group':
            query = "SELECT * FROM v_group_daily_summary WHERE analysis_date = ? AND group_id = ?"
        elif org_type == 'team':
            query = "SELECT * FROM v_team_daily_summary WHERE analysis_date = ? AND team_id = ?"
        
        return self.db_manager.query_one(query, [date, org_id])
```

### 4.3 Phase 3: 조직별 대시보드 구현 (2주)

#### OrganizationDashboard 클래스
```python
# src/ui/components/organization_dashboard.py

class OrganizationDashboard:
    """조직별 대시보드"""
    
    def render_organization_summary(self, org_type: str, org_id: str, date: date):
        """조직 요약 정보 표시"""
        
        # View에서 집계 데이터 조회
        summary = self.get_organization_summary(org_type, org_id, date)
        
        # 카드 형태로 표시 (참조 이미지 스타일)
        self._render_summary_cards(summary)
        
        # 하위 조직 표시
        if org_type == 'center':
            self._render_group_cards(org_id, date)
        elif org_type == 'group':
            self._render_team_cards(org_id, date)
```

### 4.4 Phase 4: 작업지시 시스템 구현 (2주)

작업지시 테이블 및 관리 화면 구현

## 5. 성능 최적화 전략

### 5.1 View 활용 효과
| 접근 방식 | 응답 시간 | 장점 | 단점 |
|----------|----------|------|------|
| 직접 쿼리 | 500-1000ms | 항상 최신 데이터 | 반복적인 복잡한 연산 |
| View 사용 | 100-300ms | 쿼리 단순화, 중간 수준 성능 | 실시간 연산 부하 |
| Materialized View | 10-50ms | 매우 빠른 응답 | 갱신 지연, 저장 공간 필요 |

### 5.2 권장 사항
- 실시간성이 중요한 경우: 일반 View 사용
- 대용량 데이터 + 빠른 응답: Materialized View 사용
- 하이브리드 접근: 당일 데이터는 View, 과거 데이터는 Materialized View

## 6. UI/UX 디자인 가이드

### 6.1 색상 체계
- **초록색**: 양호/정상 (90% 이상)
- **파란색**: 보통 (80-90%)
- **빨간색**: 경고/주의 (80% 미만)
- **회색**: 데이터 없음/미할당

### 6.2 레이아웃 구조
```
┌─────────────────────────────────────┐
│ 헤더: 조직명 | 날짜 선택 | 필터     │
├─────────────────────────────────────┤
│ 전체 현황 (총 인원, 평균 근무율)    │
├─────────────────────────────────────┤
│ 조직별 카드 (센터/그룹/팀)          │
│ - 인원수, 근무율, 상태별 분포       │
├─────────────────────────────────────┤
│ 작업지시 현황                       │
│ - 신규/진행중/완료 작업 수          │
├─────────────────────────────────────┤
│ 진행 상황 상세                      │
└─────────────────────────────────────┘
```

## 7. 실행 흐름

1. **개인별 분석 실행 시**:
   - individual_dashboard에서 분석 완료
   - AnalysisResultSaver가 결과를 DB에 저장

2. **배치 처리 (일일/주기적)**:
   - 모든 직원에 대해 분석 실행
   - 각 결과를 DB에 저장
   - View를 통한 자동 집계

3. **조직별 대시보드 조회 시**:
   - View에서 실시간 집계된 데이터 조회
   - 빠른 응답 속도 보장

## 8. 예상 일정
- **Phase 1**: 1주 (데이터 저장 구조)
- **Phase 2**: 1주 (조직별 집계)
- **Phase 3**: 2주 (조직별 대시보드)
- **Phase 4**: 2주 (작업지시 시스템)
- **총 소요**: 6주

## 9. 주요 성과 지표
- 조직별 실시간 근무율 표시
- 개인 분석 결과 100% DB 저장
- 조직 대시보드 응답 시간 < 300ms
- 사용자 만족도 4.5/5.0 이상