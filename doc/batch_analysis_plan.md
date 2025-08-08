# 대규모 배치 분석 실행 계획

## 1. 분석 최적화 전략

### 1.1 Claim 기반 필터링
```python
def get_analysis_targets(start_date, end_date):
    """Claim 데이터가 있는 날짜만 추출"""
    query = """
    SELECT DISTINCT 
        employee_id,
        work_date
    FROM employee_claims
    WHERE work_date BETWEEN ? AND ?
        AND claim_hours > 0
    ORDER BY employee_id, work_date
    """
    return db.execute(query, (start_date, end_date))
```

### 1.2 병렬 처리 아키텍처
```python
from multiprocessing import Pool, cpu_count
from concurrent.futures import ProcessPoolExecutor, as_completed
import pandas as pd
from datetime import datetime, timedelta

class BatchAnalysisProcessor:
    def __init__(self, num_workers=None):
        self.num_workers = num_workers or min(cpu_count() - 1, 8)
        self.batch_size = 100  # 한 번에 처리할 직원 수
        
    def process_batch(self, employee_batch):
        """배치 단위로 직원 분석"""
        results = []
        for employee_id, dates in employee_batch:
            for date in dates:
                result = self.analyze_single(employee_id, date)
                results.append(result)
        return results
    
    def run_parallel_analysis(self, target_list):
        """병렬 분석 실행"""
        # 배치 분할
        batches = self.create_batches(target_list)
        
        # 진행률 추적
        total_batches = len(batches)
        completed = 0
        
        with ProcessPoolExecutor(max_workers=self.num_workers) as executor:
            futures = {executor.submit(self.process_batch, batch): batch 
                      for batch in batches}
            
            for future in as_completed(futures):
                result = future.result()
                self.save_results(result)
                completed += 1
                print(f"Progress: {completed}/{total_batches} batches "
                      f"({completed*100/total_batches:.1f}%)")
```

## 2. 데이터베이스 분리 전략

### 2.1 분석 결과 전용 DB 스키마
```sql
-- sambio_analytics.db

-- 일별 개인 분석 결과
CREATE TABLE daily_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    analysis_date DATE NOT NULL,
    
    -- 기본 정보
    center_name TEXT,
    team_name TEXT,
    group_name TEXT,
    job_grade TEXT,
    
    -- 근무 시간 분석
    total_hours REAL,
    work_hours REAL,
    focused_work_hours REAL,
    meeting_hours REAL,
    break_hours REAL,
    meal_hours REAL,
    
    -- 효율성 지표
    efficiency_ratio REAL,
    focus_ratio REAL,
    productivity_score REAL,
    
    -- 패턴 분석
    peak_hours TEXT,  -- JSON: 집중 시간대
    activity_distribution TEXT,  -- JSON: 활동 분포
    location_patterns TEXT,  -- JSON: 위치 패턴
    
    -- 메타 정보
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    analysis_version TEXT,
    
    UNIQUE(employee_id, analysis_date)
);

-- 집계 테이블 (빠른 조회용)
CREATE TABLE team_daily_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id TEXT NOT NULL,
    analysis_date DATE NOT NULL,
    
    -- 팀 통계
    total_employees INTEGER,
    analyzed_employees INTEGER,
    avg_efficiency_ratio REAL,
    avg_work_hours REAL,
    avg_focus_ratio REAL,
    
    -- 분포 데이터
    efficiency_distribution TEXT,  -- JSON
    grade_distribution TEXT,  -- JSON
    
    UNIQUE(team_id, analysis_date)
);

CREATE TABLE center_daily_summary (
    -- 센터 레벨 집계
    -- 구조는 team_daily_summary와 유사
);

-- 인덱스
CREATE INDEX idx_daily_analysis_employee_date 
    ON daily_analysis(employee_id, analysis_date);
CREATE INDEX idx_daily_analysis_date 
    ON daily_analysis(analysis_date);
CREATE INDEX idx_team_summary_date 
    ON team_daily_summary(analysis_date);
```

## 3. 실행 계획 (3일 내 완료)

### Day 1: 준비 및 초기 실행
```python
# 1. Claim 데이터 기반 타겟 리스트 생성
targets = extract_analysis_targets()
print(f"Total targets: {len(targets)} (예상: 100,000)")

# 2. 분석 DB 초기화
init_analytics_database()

# 3. 첫 배치 실행 (20% 목표)
processor = BatchAnalysisProcessor(num_workers=8)
processor.run_parallel_analysis(targets[:20000])
```

### Day 2: 메인 처리
```python
# 4. 메인 배치 처리 (60% 목표)
processor.run_parallel_analysis(targets[20000:80000])

# 5. 중간 검증
validate_results()
```

### Day 3: 완료 및 검증
```python
# 6. 나머지 처리 (20%)
processor.run_parallel_analysis(targets[80000:])

# 7. 집계 테이블 생성
generate_aggregations()

# 8. 최종 검증
final_validation()
```

## 4. 성능 모니터링

```python
class PerformanceMonitor:
    def __init__(self):
        self.start_time = datetime.now()
        self.processed = 0
        self.total = 0
        
    def update(self, batch_size):
        self.processed += batch_size
        elapsed = (datetime.now() - self.start_time).total_seconds()
        rate = self.processed / elapsed if elapsed > 0 else 0
        
        remaining = self.total - self.processed
        eta_seconds = remaining / rate if rate > 0 else 0
        eta = timedelta(seconds=int(eta_seconds))
        
        print(f"""
        Progress: {self.processed}/{self.total} ({self.processed*100/self.total:.1f}%)
        Rate: {rate:.1f} items/sec
        Elapsed: {timedelta(seconds=int(elapsed))}
        ETA: {eta}
        """)
```

## 5. React UI 연동 전략

### 5.1 API 엔드포인트 설계
```python
# FastAPI 백엔드 예시
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

@app.get("/api/centers/{date}")
async def get_centers_summary(date: str):
    """센터별 요약 데이터"""
    return query_analytics_db(f"""
        SELECT * FROM center_daily_summary 
        WHERE analysis_date = ?
    """, (date,))

@app.get("/api/teams/{center_id}/{date}")
async def get_teams_by_center(center_id: str, date: str):
    """특정 센터의 팀 목록"""
    # 드릴다운 데이터 반환

@app.get("/api/employees/{team_id}/{date}")
async def get_employees_by_team(team_id: str, date: str):
    """특정 팀의 직원 상세"""
    # 상세 데이터 반환
```

### 5.2 React 컴포넌트 구조
```javascript
// React 프로젝트 구조
src/
  components/
    OrganizationDashboard/
      CenterGrid.jsx       // 센터 카드 그리드
      TeamGrid.jsx         // 팀 카드 그리드
      EmployeeDetail.jsx   // 직원 상세
      MetricCard.jsx       // 재사용 가능한 카드 컴포넌트
  services/
    analyticsAPI.js        // API 통신
  hooks/
    useAnalytics.js        // 데이터 페칭 훅
```

## 6. 예상 결과

### 시간 예측
- **Claim 필터링**: 150,000 → 100,000 작업 (33% 감소)
- **8코어 병렬**: 100,000초 ÷ 8 = 12,500초 = **약 3.5시간**
- **여유 시간**: 충분한 재실행 및 검증 시간 확보

### 리스크 관리
1. **메모리 부족**: 배치 크기 조절로 해결
2. **DB 락**: 별도 DB 사용으로 해결
3. **실패 복구**: 체크포인트 저장으로 재시작 가능

### 최종 산출물
- `sambio_analytics.db`: 분석 결과 DB (약 2-3GB 예상)
- React UI 프로젝트: 독립 실행 가능한 대시보드
- API 서버: FastAPI 기반 데이터 서빙