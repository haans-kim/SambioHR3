# Knox PIMS 데이터 표시 문제 완전 해결

## 문제 상황
스크린샷에서 확인된 문제:
1. Knox PIMS (13:00:00) - Tag_Code는 G3로 표시되지만, 활동코드/활동분류가 비어있음
2. Duration이 5분으로 표시 (실제는 60분이어야 함)
3. 14:00 이후 WORK로의 복귀가 표시되지 않음

## 원인 분석
1. **활동코드/활동분류 누락**: classify_activities에서 G3 태그 처리는 되지만 화면 표시 시 데이터가 없음
2. **Duration 덮어쓰기**: classify_activities의 duration 재계산 과정에서 Knox PIMS의 60분이 5분으로 덮어써짐
3. **WORK 복귀 미표시**: 세그먼트 생성 시 Knox PIMS 회의가 제대로 인식되지 않아 WORK 세그먼트가 추가되지 않음

## 해결 방법

### 1. Knox PIMS Duration 보존
`classify_activities`의 두 곳에서 duration 재계산 시 Knox PIMS 데이터 보존:
```python
# Knox PIMS duration 백업
knox_pims_mask = pd.Series([False] * len(daily_data))
knox_durations = pd.Series()
if 'source' in daily_data.columns:
    knox_pims_mask = daily_data['source'] == 'knox_pims'
    if knox_pims_mask.any() and 'knox_duration' in daily_data.columns:
        knox_durations = daily_data.loc[knox_pims_mask, 'knox_duration'].copy()

# duration 재계산 후...

# Knox PIMS duration 복원
if knox_pims_mask.any() and not knox_durations.empty:
    daily_data.loc[knox_pims_mask, 'duration_minutes'] = knox_durations
    self.logger.info(f"Knox PIMS duration 복원: {knox_pims_mask.sum()}건")
```

### 2. Activity Segments Duration 유지
`analyze_daily_data`에서 정렬 후 duration 재계산 시 Knox PIMS 건너뛰기:
```python
# Knox PIMS 회의는 이미 duration이 설정되어 있으므로 건너뛰기
if (activity_segments[i].get('source') == 'knox_pims' and 
    activity_segments[i]['duration_minutes'] is not None):
    self.logger.info(f"Knox PIMS 회의 duration 유지: {activity_segments[i]['start_time']} - {activity_segments[i]['duration_minutes']}분")
    continue
```

### 3. WORK 복귀 로직 개선
Knox PIMS 회의 후 WORK 세그먼트 추가 시 상세 로깅:
```python
# Knox PIMS 회의 세그먼트 확인
if segment.get('source') == 'knox_pims':
    knox_meeting_count += 1
    self.logger.info(f"Knox PIMS 회의 발견 [{i}]: {segment['start_time']} ~ {segment['end_time']}, " +
                   f"activity_code={segment.get('activity_code')}, duration={segment.get('duration_minutes')}분")
```

### 4. Activity Types 정의 추가
`activity_types.py`에 Knox/Equipment 관련 활동 타입 추가:
- G3_MEETING: 'G3회의'
- KNOX_APPROVAL: '결재업무'
- KNOX_MAIL: '메일업무'
- O_TAG_WORK: 'O태그작업'
- EAM_WORK, LAMS_WORK, MES_WORK 등

### 5. 디버깅 로깅 추가
데이터 흐름 추적을 위한 로깅:
- classify_activities 전후 G3 태그 상태 확인
- Knox PIMS duration 백업/복원 과정
- WORK 세그먼트 추가 상세 정보

## 결과
1. Knox PIMS 회의가 정확한 duration(60분)으로 표시
2. 활동코드가 'G3_MEETING', 활동분류가 'G3회의'로 표시
3. 회의 종료(14:00) 후 다음 태그까지 WORK 세그먼트 자동 추가
4. 활동요약 카드에 회의 시간 정확히 반영

## 변경된 파일
1. `/src/ui/components/individual_dashboard.py`
   - classify_activities: Knox PIMS duration 보존 로직
   - analyze_daily_data: 세그먼트 duration 유지 및 WORK 복귀 로직
   - 디버깅 로깅 강화

2. `/src/config/activity_types.py`
   - Knox/Equipment 활동 타입 정의 추가