# API 변경사항 추적 가이드

## 개요
Claude Code에서 작업할 때 API, 데이터베이스, 페이지 등의 변경사항을 자동으로 추적하고 문서화하는 시스템입니다.

## 구성 요소

### 1. 변경 추적 스크립트
- **위치**: `/scripts/track_changes.py`
- **기능**:
  - Service Layer API 함수 추적
  - Streamlit 페이지 변경 감지
  - 데이터베이스 모델 변경 확인
  - 변경 로그 자동 생성

### 2. 자동 실행 훅
- **사전 훅**: `/.claude_hooks/pre_edit.sh`
  - 편집 전 현재 상태 캡처
- **사후 훅**: `/.claude_hooks/post_edit.sh`
  - 편집 후 변경사항 감지 및 알림

### 3. 변경 로그 저장
- **위치**: `/doc/changes/`
- **형식**:
  - `api_changes_YYYYMMDD_HHMMSS.md`: 타임스탬프별 로그
  - `LATEST.md`: 최신 변경사항

## 추적 대상

### API 함수
- `/src/analysis/individual_analyzer.py`
- `/src/analysis/organization_analyzer.py`
- `/src/analysis/network_analyzer.py`
- `/src/database/db_manager.py`

### 데이터베이스 스키마
- `/src/database/schema.py`
- `/src/database/models.py`
- `/src/database/tag_schema.py`

### Streamlit 페이지
- `/src/ui/streamlit_app.py`의 페이지 정의

## 수동 실행 방법

```bash
# 프로젝트 루트에서 실행
python scripts/track_changes.py

# 또는 특정 디렉토리 지정
python scripts/track_changes.py /path/to/project
```

## 변경 로그 예시

```markdown
# API 변경 로그 - 2025-01-29 15:30:00

## API 변경사항
- ➕ 새 함수: analyze_productivity(employee_id, period)
  - 파일: `src/analysis/individual_analyzer.py`
- 📝 함수 시그니처 또는 문서 변경
  - 파일: `src/database/db_manager.py`

## 페이지 변경사항
- ➕ 새 페이지: 생산성 대시보드 (productivity_dashboard.py)

## 데이터베이스 변경사항
- ➕ 새 테이블: ProductivityMetrics
  - 파일: `src/database/schema.py`
```

## 캐시 파일
- **위치**: `/.claude_cache/api_tracking.json`
- **내용**: 마지막 추적 상태 저장
- **용도**: 변경사항 비교 기준

## 주의사항

1. **Git 무시**: `.claude_cache/` 디렉토리는 .gitignore에 추가됨
2. **권한**: 스크립트와 훅은 실행 권한 필요 (`chmod +x`)
3. **Python 의존성**: Python 3.6+ 필요, 표준 라이브러리만 사용

## 확장 방법

추적 대상을 추가하려면 `track_changes.py`에서:

1. 새 파일 경로를 `service_files` 리스트에 추가
2. 새 추적 메서드 작성 (예: `find_new_components()`)
3. `track_changes()` 메서드에 호출 추가
4. `compare_states()` 메서드에 비교 로직 추가