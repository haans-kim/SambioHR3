# 데이터베이스 설계 문서

## 개요
SambioHR2는 SQLite 데이터베이스와 SQLAlchemy ORM을 사용하여 24시간 2교대 근무 환경의 근로자 활동을 분석합니다.

## 데이터베이스 구조

### 1. 메인 스키마 (schema.py) - 15개 테이블

#### DailyWorkData
일일 근무 데이터 저장
- `date`: 날짜
- `employee_code`: 사번
- `name`: 이름
- `shift`: 근무조 (주간/야간)
- `clock_in_time`: 출근시간
- `clock_out_time`: 퇴근시간
- `cross_day_flag`: 날짜 경계 플래그
- `gross_work_time`: 총 근무시간
- `actual_work_time`: 실제 작업시간
- `rest_time`: 휴식시간
- `meal_times`: 식사시간 (아침/점심/저녁/야식)

#### ShiftWorkData
교대 근무 시간 데이터
- `date`: 날짜
- `employee_code`: 사번
- `shift_hours`: 각 교대별 근무시간 (JSON)
- `total_work_time`: 총 근무시간

#### OrganizationSummary
조직별 집계 데이터
- `date`: 날짜
- `dept_name`: 부서명
- `type`: 집계 유형
- `value`: 집계값
- `count`: 인원수

#### TagLogs
위치 태그 로그
- `employee_code`: 사번
- `timestamp`: 시간
- `location`: 위치
- `tag_type`: 태그 타입
- `processed_flag`: 처리 플래그

### 2. 단순화 모델 (models.py) - 9개 테이블

#### Employee
직원 기본 정보
- `employee_id`: 사번
- `name`: 이름
- `department`: 부서
- `team`: 팀
- `shift_type`: 근무 유형

#### DailyWorkSummary
일일 근무 요약
- `work_date`: 근무일
- `employee_id`: 사번
- `work_hours`: 근무시간
- `efficiency_rate`: 효율성
- `activity_summary`: 활동 요약 (JSON)

### 3. 태그 시스템 스키마 (tag_schema.py) - 6개 테이블

#### TagMaster
태그 마스터 정의
- `tag_code`: 태그 코드
- `tag_category`: 카테고리 (G/N/T/M/O)
- `tag_name`: 태그명
- `description`: 설명
- `priority`: 우선순위

#### LocationTagMapping
위치-태그 매핑
- `location`: 위치
- `tag_code`: 태그 코드
- `is_primary`: 주 태그 여부

#### StateTransitionRules
상태 전환 규칙
- `from_state`: 이전 상태
- `to_state`: 다음 상태
- `probability`: 전환 확률
- `condition`: 조건 (JSON)

## 주요 특징

### 1. 2교대 근무 지원
- 주간: 08:00-20:00
- 야간: 20:00-08:00
- 자정 경계 처리 (cross_day_flag)

### 2. 4대 식사 시간
- 아침: 06:30-09:00
- 점심: 11:20-13:20
- 저녁: 17:00-20:00
- 야식: 23:30-01:00

### 3. HMM 모델 통합
- 17개 활동 상태
- 전환/방출 행렬 (JSON)
- 신뢰도 점수

### 4. 조직 계층
- Center > BU > Team > Group > Part
- 부서 재편 지원

## 인덱스 전략
```sql
-- 성능 최적화 인덱스
CREATE INDEX idx_daily_work_date_emp ON daily_work_data(date, employee_code);
CREATE INDEX idx_tag_logs_timestamp ON tag_logs(timestamp);
CREATE INDEX idx_tag_logs_emp_time ON tag_logs(employee_code, timestamp);
```

## 데이터 무결성
- NOT NULL 제약조건
- 외래키 관계
- 체크 제약조건 (근무시간, 확률값 등)

## 백업 전략
- 일일 자동 백업
- 월별 아카이브
- 트랜잭션 로그 유지