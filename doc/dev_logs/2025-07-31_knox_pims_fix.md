# Knox PIMS 데이터 표시 문제 해결

## 문제
- 20220245 사번의 6/30 회의 데이터가 Knox PIMS 파일에는 존재하나 UI에 표시되지 않음
- "20220245 SCH202506240624095314254657 회의/보고/면담 2025.06.30 13:00:00 2025.06.30 14:00:00"

## 원인 분석
1. Knox PIMS 데이터는 정상적으로 로드됨 (48,864건)
2. 20220245 사번의 데이터도 정상적으로 필터링됨 (13건 중 1건이 6/30)
3. 데이터는 tag_logs가 아닌 daily_data에 병합되도록 구현되어 있음
4. **주요 문제**: `classify_activities` 메서드에서 G3 태그 처리 시 충돌 발생
   - Knox PIMS G3 태그는 `G3_MEETING`으로 설정
   - 일반 G3 태그 처리 로직이 이를 `MEETING`으로 덮어씀

## 해결 방법

### 1. 로깅 강화
- `_get_knox_and_equipment_tags` 메서드에 상세 로깅 추가
- Knox PIMS 데이터 로드 시 컬럼, 사번별 데이터 수, 날짜별 매칭 정보 출력
- G3 태그 생성 시 상세 정보 로깅

### 2. G3 태그 분류 충돌 해결
```python
# 6. G3 태그 (회의공간) 처리
g3_mask = daily_data['tag_code'] == 'G3'
if g3_mask.any():
    # Knox PIMS G3 태그는 G3_MEETING 유지
    if 'source' in daily_data.columns:
        knox_pims_mask = g3_mask & (daily_data['source'] == 'knox_pims')
        regular_g3_mask = g3_mask & (daily_data['source'] != 'knox_pims')
    else:
        knox_pims_mask = pd.Series([False] * len(daily_data))
        regular_g3_mask = g3_mask
    
    # Knox PIMS G3 태그 처리
    if knox_pims_mask.any():
        daily_data.loc[knox_pims_mask, 'activity_code'] = 'G3_MEETING'
        daily_data.loc[knox_pims_mask, 'activity_type'] = 'meeting'
        daily_data.loc[knox_pims_mask, '활동분류'] = 'G3회의'
        daily_data.loc[knox_pims_mask, 'confidence'] = 100
        
    # 일반 G3 태그 처리
    if regular_g3_mask.any():
        daily_data.loc[regular_g3_mask, 'activity_code'] = 'MEETING'
        daily_data.loc[regular_g3_mask, 'activity_type'] = activity_type.category if activity_type else 'meeting'
        daily_data.loc[regular_g3_mask, '활동분류'] = activity_type.name_ko if activity_type else '회의'
        daily_data.loc[regular_g3_mask, 'confidence'] = 95
```

### 3. 세그먼트 생성 시 로깅 추가
- G3_MEETING 활동이 세그먼트로 제대로 생성되는지 확인
- 활동 코드별 세그먼트 수 집계 및 로깅

## 테스트 결과
- Knox PIMS 데이터 로드: ✓
- 20220245 사번 데이터 필터링: ✓
- 6월 30일 회의 데이터 확인: ✓
  - 일정ID: SCH202506240624095314254657
  - 시작: 2025-06-30 13:00:00
  - 종료: 2025-06-30 14:00:00

## 변경된 파일
1. `/src/ui/components/individual_dashboard.py`
   - `_get_knox_and_equipment_tags`: Knox PIMS 로깅 강화
   - `classify_activities`: G3 태그 분류 충돌 해결
   - `analyze_daily_data`: 세그먼트 생성 로깅 추가

## 다음 단계
- Streamlit 앱 재시작 후 로그 확인
- 20220245 사번으로 6/30 날짜 선택하여 G3_MEETING 표시 확인
- Gantt 차트에 Knox PIMS 회의가 제대로 표시되는지 확인