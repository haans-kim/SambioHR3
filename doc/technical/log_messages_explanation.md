# 시스템 로그 메시지 설명

## 자주 보이는 WARNING 메시지 해석

### 1. 정문 태그 WORK 분류 문제
```
WARNING - 태그 기반 규칙 후에도 정문 태그가 WORK로 분류됨: 3건
WARNING -   - 2025-06-30 11:06:55 at 700-63_P4 정문동 방향 S/G #1 입문, Tag_Code=T1
```

**의미**: 
- T1, T2 태그는 출입 관련 태그인데 잘못 WORK로 분류된 경우
- T1 = 퇴문(OUT), T2 = 입문(IN), T3 = 퇴근용 태그

**처리 과정**:
1. 초기 분류에서 잘못 WORK로 분류됨
2. 시스템이 이를 감지하고 경고 로그 출력
3. 자동으로 올바른 분류로 수정 (T2 → COMMUTE_IN, T1/T3 → COMMUTE_OUT)

**실제 코드**:
```python
# individual_dashboard.py 1942-1947줄
gate_work_mask = daily_data['DR_NM'].str.contains('정문|SPEED GATE', case=False, na=False) & \
                (daily_data['activity_code'] == 'WORK')
if gate_work_mask.any():
    self.logger.warning(f"태그 기반 규칙 후에도 정문 태그가 WORK로 분류됨: {gate_work_mask.sum()}건")
```

### 2. T2 태그 강제 수정
```
WARNING - 태그 기반 분류 후 T2 태그 5건을 COMMUTE_IN으로 수정
```

**의미**:
- T2(입문) 태그가 다른 활동으로 잘못 분류되어 있던 것을 수정

**처리 과정**:
1. 태그 기반 분류 완료 후 T2 태그 확인
2. COMMUTE_IN이 아닌 다른 활동으로 분류된 T2 발견
3. 강제로 COMMUTE_IN으로 수정 (신뢰도 100%)

**실제 코드**:
```python
# individual_dashboard.py 2125-2132줄
t2_mask = (daily_data['Tag_Code'] == 'T2')
if t2_mask.any():
    t2_wrong = t2_mask & (~daily_data['activity_code'].isin(['COMMUTE_IN']))
    if t2_wrong.any():
        self.logger.warning(f"태그 기반 분류 후 T2 태그 {t2_wrong.sum()}건을 COMMUTE_IN으로 수정")
        daily_data.loc[t2_wrong, 'activity_code'] = 'COMMUTE_IN'
        daily_data.loc[t2_wrong, 'activity_type'] = 'commute'
        daily_data.loc[t2_wrong, 'confidence'] = 100
```

### 3. 긴 시간 간격 감지 및 제한
```
WARNING - 긴 시간 간격 감지: 2025-06-30 11:06:55 ~ 2025-06-30 12:33:07 (86분) -> 5분으로 제한
WARNING - 긴 시간 간격 감지: 2025-06-30 15:26:51 ~ 2025-06-30 17:16:59 (110분) -> 5분으로 제한
```

**의미**:
- 연속된 두 태그 사이 시간 간격이 60분을 초과하는 경우
- 비정상적으로 긴 간격은 데이터 수집 오류나 실제 비활동 시간

**처리 과정**:
1. 각 태그의 지속시간(duration) 계산 시 다음 태그까지 시간 측정
2. 60분 초과 시 비정상으로 판단
3. 해당 태그의 지속시간을 5분으로 제한
4. 과도한 근무시간 계산 방지

**실제 코드**:
```python
# individual_dashboard.py 3155-3164줄
if i < len(data) - 1:
    next_time = data.iloc[i + 1]['datetime']
    duration = (next_time - current_row['datetime']).total_seconds() / 60
    
    # 60분을 초과하는 간격은 5분으로 제한 (비정상적인 gap 방지)
    if duration > 60:
        self.logger.warning(f"긴 시간 간격 감지: {current_row['datetime']} ~ {next_time} ({duration:.0f}분) -> 5분으로 제한")
        duration = 5
```

**왜 5분으로 제한하는가?**
- 태그 리더기를 지나가는 순간만 기록되므로 실제 활동 시간은 알 수 없음
- 60분 이상 간격은 휴식, 외출, 데이터 누락 등의 가능성
- 과대 계산 방지를 위해 최소값(5분)만 인정

### 4. FutureWarning
```
FutureWarning: The default dtype for empty Series will be 'object' instead of 'float64' in a future version.
```

**의미**:
- Pandas 라이브러리의 향후 버전 변경 경고
- 빈 Series 생성 시 기본 데이터 타입이 변경될 예정

**영향**:
- 현재는 작동에 문제 없음
- 향후 Pandas 업그레이드 시 수정 필요

**해결 방법**:
```python
# 현재 코드
pd.Series()  # FutureWarning 발생

# 수정된 코드
pd.Series(dtype='float64')  # 명시적 타입 지정
```

## 로그 레벨별 의미

### INFO 레벨
- 정상적인 처리 과정 정보
- 예: "T2 태그의 activity_code 상태:", "activity_type이 비어있는 X개 발견, 재매핑 수행"

### WARNING 레벨
- 비정상 상황 감지 및 자동 수정
- 시스템이 자동으로 처리하지만 주의가 필요한 상황
- 예: 태그 분류 오류 수정, 긴 시간 간격 제한

### ERROR 레벨
- 처리할 수 없는 오류 발생
- 관리자 개입 필요

## 개선 권장사항

1. **태그 분류 정확도 향상**
   - Tag_Code 우선순위를 높여 초기 분류부터 정확하게
   - T1, T2, T3 태그는 무조건 출퇴근으로 분류

2. **시간 간격 처리 개선**
   - 60분 이상 간격에 대한 세분화된 처리
   - 점심시간(12-13시) 간격은 정상으로 처리
   - 회의실 이동 등 예상 가능한 패턴 학습

3. **로그 레벨 조정**
   - 자동 수정되는 경우 INFO 레벨로 낮추기
   - 실제 문제가 있는 경우만 WARNING 사용

4. **데이터 품질 모니터링**
   - 태그 누락 구간 자동 감지
   - 데이터 수집 장비 점검 알림