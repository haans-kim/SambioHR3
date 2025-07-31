# Knox PIMS 회의 Duration 및 활동분류 수정

## 문제
1. Knox PIMS 회의의 체류시간이 5분으로 표시 (실제: 13:00-14:00 = 60분)
2. 활동분류가 "근무중"으로 표시 (G3회의로 표시되어야 함)
3. 활동요약 카드에 회의 시간 미포함
4. 회의 종료 후 WORK로 돌아가는 로직 부재

## 해결 방법

### 1. Knox PIMS Duration 계산 개선
`_get_knox_and_equipment_tags`에서 Knox PIMS 태그 생성 시 종료시간과 duration 추가:
```python
# 회의 시간 계산 (분 단위)
meeting_duration = None
if end_time:
    meeting_duration = (end_time - start_time).total_seconds() / 60

tag = {
    # ... 기존 필드들 ...
    'knox_end_time': end_time,  # Knox PIMS 종료시간 저장
    'knox_duration': meeting_duration  # Knox PIMS 회의 시간(분) 저장
}
```

### 2. Segment 생성 시 Knox Duration 활용
`analyze_daily_data`에서 Knox PIMS 회의는 종료시간 기반으로 처리:
```python
# Knox PIMS 회의의 경우 종료시간 사용
if row.get('source') == 'knox_pims' and pd.notna(row.get('knox_end_time')):
    end_time = row['knox_end_time']
    duration_minutes = row.get('knox_duration', 60)  # Knox에서 계산된 duration 사용
```

### 3. 회의 종료 후 WORK 세그먼트 추가
회의와 다음 태그 사이에 간격이 있으면 WORK 세그먼트 자동 추가:
```python
# Knox PIMS 회의 후 WORK 세그먼트 추가
if gap_minutes > 5:  # 5분 이상의 간격이 있으면 WORK 세그먼트 추가
    work_segment = {
        'start_time': meeting_end,
        'end_time': next_start,
        'activity': 'WORK',
        'activity_code': 'WORK',
        'location': '작업장',
        'duration_minutes': gap_minutes,
        'confidence': 70,
        'source': 'inferred'
    }
```

### 4. 활동요약 카드에 회의 시간 포함
`confidence_calculator_v2.py`에서:
- work_activities에 'G3_MEETING' 추가
- activity_type 결정 시 G3_MEETING을 'meeting'으로 분류
- activity_minutes['meeting']에 시간 집계

### 5. 활동분류 표시 문제 해결
`activity_types.py`에 누락된 활동 코드 추가:
- G3_MEETING: 'G3회의'
- KNOX_APPROVAL: '결재업무'
- KNOX_MAIL: '메일업무'
- EAM_WORK: '안전설비'
- LAMS_WORK: '품질시스템'
- MES_WORK: '생산시스템'
- O_TAG_WORK: 'O태그작업'

## 변경된 파일
1. `/src/ui/components/individual_dashboard.py`
   - Knox PIMS 태그에 종료시간/duration 추가
   - Segment 생성 시 Knox duration 활용
   - 회의 후 WORK 세그먼트 추가 로직

2. `/src/tag_system/confidence_calculator_v2.py`
   - G3_MEETING을 work_activities에 추가
   - activity_type 결정 로직 개선
   - 회의 시간 올바르게 집계

3. `/src/config/activity_types.py`
   - G3_MEETING 및 Knox/Equipment 활동 타입 추가

## 결과
- Knox PIMS 회의가 정확한 duration(60분)으로 표시
- 활동분류가 'G3회의'로 올바르게 표시
- 활동요약에 회의 시간 포함
- 회의 종료 후 자동으로 WORK 활동 추가