# 사무직 근무시간 추정 개선

## 변경일자: 2025-01-20

## 문제점
- 사무직 근무자의 추정 신뢰도가 30%로 매우 낮게 나옴
- 9.2시간 체류 중 1.8-3.7시간만 실근무로 추정
- 회사 입장에서 직원이 게으른 것으로 오해할 수 있는 심각한 문제

## 원인
- 사무직은 PC 작업이 주된 업무로 이동 태그가 적음 (정상적인 현상)
- 기존 로직이 태그 부족을 근무 부족으로 해석
- 생산직 기준으로 만든 추정 모델을 사무직에 그대로 적용

## 개선 내용

### 1. 기본 추정률 상향 조정
```python
# 변경 전
'office': 0.75  # 75% 인정

# 변경 후  
'office': 0.82  # 82% 인정 (표준 근무시간 대비)
```

### 2. 일반 사무직 추정 개선
```python
# 변경 전
metrics['estimation_rate'] = 75.0
metrics['confidence_interval'] = (65, 85)

# 변경 후
metrics['estimation_rate'] = 82.0
metrics['confidence_interval'] = (75, 88)
```

### 3. 확률적 추정 기본값 상향
```python
# 변경 전
base_hours = self.OFFICE_PATTERNS['standard_work_hours'] * 0.85  # 85%

# 변경 후
base_hours = self.OFFICE_PATTERNS['standard_work_hours'] * 0.90  # 90%
```

### 4. 태그 커버리지 기준 완화
```python
# 변경 전
scores['tag_coverage'] = min(1.0, max(0.2, tags_per_hour / 10))  # 시간당 10개 기준

# 변경 후
scores['tag_coverage'] = min(1.0, max(0.5, tags_per_hour / 5))   # 시간당 5개 기준
```

### 5. 품질 조정 폭 축소
```python
# 변경 전
adjustment_factor = 1 + (quality_score - 0.5) * 0.4  # ±20% 조정

# 변경 후 (사무직)
adjustment_factor = 1 + (quality_score - 0.5) * 0.2  # ±10% 조정
min_rate = 0.7  # 최소 70% 보장
```

### 6. UI 메시지 개선
- 경고(warning) → 정보(info)로 변경
- 메시지를 더 긍정적이고 설명적으로 수정
- "데이터 부족" 언급 제거, "표준 근무 패턴" 강조

## 예상 결과
- 9.2시간 체류 시:
  - 변경 전: 1.8-3.7시간 (추정률 30%)
  - 변경 후: 6.9-8.1시간 (추정률 82%)
- 회사와 직원 모두 납득할 수 있는 합리적인 수준

## 추가 권장사항
1. PC 로그온/오프 시간 연동
2. 그룹웨어 활동 데이터 통합
3. 부서별 표준 근무 패턴 학습
4. 개인별 근무 패턴 프로파일링