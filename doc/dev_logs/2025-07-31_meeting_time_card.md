# 활동요약 카드에 회의 시간 추가

## 구현 내용
활동요약 대시보드에 회의 시간 카드를 포함하여 주요 활동 시간을 한눈에 볼 수 있도록 개선

## 변경사항

### 1. 첫 번째 줄 - 핵심 지표
- **실제 근무시간**: 기존 유지
- **회의 시간**: 새로 추가 (activity_breakdown에서 meeting 시간)
- **식사 시간**: 새로 추가 (BREAKFAST + LUNCH + DINNER + MIDNIGHT_MEAL)
- **업무 효율성**: 기존 유지
- **초과근무**: 기존 유지

### 2. 두 번째 줄 - 부가 정보
- **근무 형태**: 기존 유지
- **데이터 신뢰도**: 기존 유지
- **이동 시간**: 새로 추가 (movement 시간)
- **휴식 시간**: 새로 추가 (rest 시간)
- **집중근무**: 새로 추가 (FOCUSED_WORK 시간)

## 구현 코드
```python
# 회의 시간 (activity_breakdown에서 가져오기)
meeting_hours = work_analysis.get('work_breakdown', {}).get('meeting', 0)
st.metric(
    "회의 시간",
    f"{meeting_hours:.1f}h",
    ""
)

# 식사 시간 계산
meal_minutes = 0
if 'activity_summary' in analysis_result:
    for meal_type in ['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL']:
        meal_minutes += analysis_result['activity_summary'].get(meal_type, 0)
meal_hours = meal_minutes / 60
st.metric(
    "식사 시간",
    f"{meal_hours:.1f}h",
    ""
)
```

## 결과
- Knox PIMS 회의 시간이 활동요약 카드에 표시됨
- 전체적인 시간 사용 패턴을 한눈에 파악 가능
- 근무, 회의, 식사, 이동, 휴식 등 주요 활동별 시간 분포 확인 가능

## 파일 변경
- `/src/ui/components/individual_dashboard.py`: render_daily_summary 메서드에서 활동요약 카드 확장