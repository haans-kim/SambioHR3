# Scripts 디렉토리 가이드

## 디렉토리 구조

```
scripts/
├── active/          # 현재 사용 중인 프로덕션 스크립트
├── debug/           # 디버깅 및 검증용 스크립트
├── archive/         # 더 이상 사용하지 않는 스크립트
├── config.py        # 공통 설정 파일
└── README.md        # 이 문서
```

## Active Scripts (현재 사용 중)

### 데이터 처리
- `process_equipment_data.py` - 장비 사용 데이터 처리 (EAM, LAMS, MES)
- `generate_o_tags_fast.py` - 장비 데이터에서 O 태그 생성 (30분 그룹핑)
- `map_locations_to_tags.py` - 기존 위치 데이터를 태그로 매핑

### 데이터베이스 관리
- `upload_tag_location_master_v3.py` - 태그 위치 마스터 데이터 업로드 (최신 버전)
- `create_tag_tables.py` - 태그 시스템 관련 테이블 생성
- `initialize_transition_rules.py` - 상태 전환 규칙 초기화
- `fix_tag_mapping_v2.py` - 태그 매핑 수정 (DR_NO 컬럼 포함)

### 분석
- `analyze_individual_with_tags.py` - 태그 시스템을 사용한 개인별 분석
- `analyze_duration.py` - 활동 지속 시간 분석
- `analyze_work_status.py` - work_status 분포 분석
- `compare_systems.py` - HMM vs 태그 시스템 성능 비교

### 유틸리티
- `track_changes.py` - API 및 데이터베이스 변경사항 자동 추적

## Debug Scripts (디버깅용)

- `check_gate_tags.py` - 게이트 관련 태그 확인
- `check_specific_gate.py` - 특정 게이트 정보 확인
- `check_tag_master.py` - 태그 마스터 테이블 구조 및 데이터 확인
- `check_meal_data.py` - 특정 직원의 식사 데이터 확인
- `check_pickle_structure.py` - pickle 파일 구조 확인
- `debug_night_shift_data.py` - 야간 근무자 데이터 범위 디버깅
- `read_transition_probabilities.py` - 태그 전이 확률 Excel 파일 읽기

## Archive Scripts (보관용)

이전 버전이나 일회성 스크립트들:
- `upload_tag_location_master.py` (v1)
- `upload_tag_location_master_v2.py`
- `fix_tag_mapping.py` (v1)
- `generate_o_tags.py` (느린 버전)
- `fix_gate_tags.py` - 게이트 태그 수정 (완료됨)
- `convert_hmm_rules.py` - HMM 규칙 변환 (일회성)
- `extract_transition_data.py` - 전이 데이터 추출 (일회성)
- `load_existing_tag_mapping.py` - 기존 태그 매핑 로드

## 공통 설정 (config.py)

모든 스크립트는 `config.py`의 설정을 사용합니다:
- 프로젝트 경로
- 데이터베이스 경로
- 파일 패턴
- 교대 근무 시간
- 식사 시간
- 활동 상태 정의

## 사용 방법

### 1. 새 스크립트 작성 시
```python
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.config import *

# config.py의 설정 사용
data_file = get_latest_file(TAG_LOCATION_MASTER_PATTERN)
```

### 2. 스크립트 실행
```bash
# active 디렉토리의 스크립트 실행
python scripts/active/analyze_individual_with_tags.py

# debug 스크립트 실행
python scripts/debug/check_tag_master.py
```

## 주의사항

1. **경로 문제**: 일부 스크립트에 하드코딩된 경로가 있습니다. `config.py` 사용을 권장합니다.
2. **데이터 파일**: pickle 파일이 필요한 스크립트는 실행 전 파일 존재 여부를 확인하세요.
3. **버전 관리**: 스크립트 수정 시 새 버전을 만들지 말고 기존 파일을 업데이트하세요.

## 유지보수

- 새 스크립트는 적절한 디렉토리에 배치
- 더 이상 사용하지 않는 스크립트는 archive로 이동
- 디버깅 완료 후 debug 스크립트는 정리 또는 archive로 이동