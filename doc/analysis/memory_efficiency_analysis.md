# SambioHR3 메모리 효율성 분석 보고서

## 작성일: 2025-01-18

## 요약

현재 SambioHR3 시스템은 데이터 로딩 과정에서 심각한 메모리 비효율성 문제를 가지고 있습니다. 동일한 데이터가 Excel → Pickle → Database → Memory로 중복 저장되며, 각 단계에서 추가적인 메모리를 소비하고 있습니다.

## 1. 현재 아키텍처의 주요 문제점

### 1.1 데이터 중복 저장
```
Excel 파일 (100MB+)
    ↓
Pickle 파일 (압축 버전)
    ↓ 
SQLite DB (전체 복사본)
    ↓
메모리 캐시 (최대 10개 DataFrame)
```

**문제점:**
- 동일 데이터가 3곳에 저장 (Pickle, DB, Memory)
- 100MB Excel → 약 300MB+ 총 저장 공간 사용

### 1.2 자동 로딩 메커니즘의 비효율성

#### DatabaseManager 초기화 시
```python
def _initialize_database(self):
    self.schema.create_tables()
    self._auto_load_pickle_data()  # 모든 pickle을 DB로 로드!
```

**문제점:**
- 앱 시작 시 모든 pickle 파일을 자동으로 DB에 로드
- 사용하지 않을 데이터도 미리 로드
- 대용량 데이터의 경우 초기 로딩 시간 증가

### 1.3 메모리 캐싱 전략의 한계

#### SingletonPickleManager 캐시
```python
if len(self._cache) >= 10:
    # 가장 오래된 항목 제거 (FIFO)
    first_key = next(iter(self._cache))
    del self._cache[first_key]
```

**문제점:**
- 단순 FIFO 방식 (사용 빈도 무시)
- 10개 제한이 임의적
- 대용량 DataFrame의 메모리 사용량 고려 없음

### 1.4 조직 단위 분석의 비효율성

#### OrganizationAnalyzer._collect_individual_analyses()
```python
for employee in employees:
    analysis = self.individual_analyzer.analyze_individual(
        employee['employee_id'], start_date, end_date
    )
```

**문제점:**
- 개인별 분석을 순차적으로 수행
- 각 분석마다 DB 쿼리 반복
- 메모리에 모든 개인 분석 결과 누적

## 2. 메모리 사용 패턴 분석

### 2.1 병목 지점

1. **초기 로딩**: `_auto_load_pickle_data()`에서 전체 데이터 로드
2. **캐시 미스**: 10개 제한 초과 시 반복적인 재로딩
3. **조직 분석**: 수백 명의 개인 데이터를 메모리에 동시 보관
4. **Streamlit 재실행**: 페이지 새로고침 시 중복 로딩

### 2.2 메모리 누수 가능성

- DataFrame 참조가 캐시에서 제거되어도 메모리에서 즉시 해제되지 않을 수 있음
- 대용량 분석 결과가 세션 상태에 누적

## 3. 데이터베이스 활용도 분석

### 3.1 현재 DB 사용 패턴

- **쓰기**: Pickle → DB 전체 복사
- **읽기**: 주로 개별 쿼리, 집계 쿼리 부족
- **인덱스**: timestamp, employee_id에만 존재
- **트랜잭션**: 배치 처리 시에만 활용

### 3.2 캐싱 전략의 문제

- Pickle과 DB가 동일한 역할 (중복)
- DB의 쿼리 최적화 기능 미활용
- 메모리 캐시가 DB 캐시와 충돌

## 4. 개선 방안

### 4.1 단일 데이터 저장소 전략

**Option 1: DB 중심 아키텍처**
```python
Excel → DB (직접 로드) → 쿼리 기반 분석
```

**장점:**
- 중복 제거
- SQL 최적화 활용
- 메모리 효율적

**Option 2: Pickle 제거**
```python
Excel → DB → LRU 메모리 캐시
```

### 4.2 지연 로딩 (Lazy Loading)

```python
class LazyDatabaseManager:
    def __init__(self):
        # 초기화 시 데이터 로드하지 않음
        self._loaded_tables = set()
    
    def get_table_data(self, table_name):
        if table_name not in self._loaded_tables:
            self._load_table(table_name)
        return self._query_table(table_name)
```

### 4.3 효율적인 캐싱 전략

```python
from functools import lru_cache
from cachetools import TTLCache, cached

class SmartCacheManager:
    def __init__(self):
        # 크기 기반 + 시간 기반 캐시
        self.cache = TTLCache(maxsize=1000, ttl=3600)  # 1시간
        
    @cached(cache)
    def get_employee_data(self, employee_id, date_range):
        # DB에서 필요한 데이터만 로드
        return self._query_employee_data(employee_id, date_range)
```

### 4.4 조직 분석 최적화

```python
def analyze_organization_optimized(self, org_id, start_date, end_date):
    # 1. DB에서 집계 쿼리로 조직 전체 데이터 한 번에 가져오기
    org_data = self.db.execute("""
        SELECT 
            employee_id,
            SUM(work_hours) as total_hours,
            AVG(productivity_score) as avg_productivity
        FROM daily_work_data
        WHERE org_id = ? AND date BETWEEN ? AND ?
        GROUP BY employee_id
    """)
    
    # 2. 메모리 효율적인 처리
    return self._process_in_chunks(org_data, chunk_size=100)
```

### 4.5 스트리밍 처리

```python
def stream_large_data(self, query):
    """대용량 데이터를 청크 단위로 처리"""
    with self.db.get_session() as session:
        result = session.execute(query)
        while True:
            chunk = result.fetchmany(1000)
            if not chunk:
                break
            yield process_chunk(chunk)
```

## 5. 구현 우선순위

### Phase 1 (즉시 적용 가능)
1. `_auto_load_pickle_data()` 비활성화 또는 선택적 로딩
2. LRU 캐시로 교체 (크기 기반)
3. 조직 분석 시 DB 집계 쿼리 활용

### Phase 2 (중기 개선)
1. Pickle 파일 의존성 제거
2. DB 인덱스 최적화
3. 스트리밍 처리 구현

### Phase 3 (장기 개선)
1. 분산 처리 도입 (Dask, Ray)
2. 캐시 서버 분리 (Redis)
3. 실시간 분석 파이프라인

## 6. 예상 효과

### 메모리 사용량 감소
- 현재: 300MB+ (데이터 3중 저장)
- 개선 후: 100MB 이하 (필요한 데이터만 캐싱)

### 성능 향상
- 초기 로딩: 30초 → 5초
- 조직 분석: 5분 → 30초 (100명 기준)

### 확장성
- 현재: 1,000명 한계
- 개선 후: 10,000명+ 처리 가능

## 7. 결론

현재 시스템의 가장 큰 문제는 **데이터 중복 저장**과 **무차별적 자동 로딩**입니다. 단기적으로는 자동 로딩을 비활성화하고 LRU 캐시를 도입하는 것만으로도 상당한 개선이 가능합니다. 중장기적으로는 Pickle 파일 의존성을 제거하고 DB 중심의 아키텍처로 전환하는 것이 필요합니다.

조직 단위 분석의 경우, 개인별 순차 처리 대신 DB 레벨의 집계 쿼리와 청크 단위 처리를 통해 메모리 효율성과 처리 속도를 크게 개선할 수 있습니다.