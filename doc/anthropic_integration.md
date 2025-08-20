# Anthropic Claude API 통합 가이드

## 개요
Sambio HR 분석 시스템에 Anthropic Claude API를 통합하여 실제 LLM 기반 패턴 분석을 수행할 수 있습니다.

## 설정 방법

### 1. API 키 발급
1. [Anthropic Console](https://console.anthropic.com/settings/keys)에 접속
2. 계정 생성 또는 로그인
3. API Keys 섹션에서 새 키 생성
4. 키를 안전한 곳에 보관

### 2. 라이브러리 설치
```bash
pip install anthropic
```

### 3. 환경 변수 설정

#### macOS/Linux
```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

#### Windows
```cmd
set ANTHROPIC_API_KEY=your-api-key-here
```

#### Python 코드에서 직접 설정
```python
import os
os.environ['ANTHROPIC_API_KEY'] = 'your-api-key-here'
```

## 사용 방법

### 기본 사용
```python
from scripts.analysis.lib.llm_analyzer_anthropic import LLMPatternAnalyzerWithAnthropic

# API 키와 함께 초기화
analyzer = LLMPatternAnalyzerWithAnthropic(
    db_path='data/sambio_human.db',
    api_key='your-api-key-here'
)

# 분석 실행
result = analyzer.analyze_with_claude('clustering')
```

### 환경 변수 사용
```python
import os
from scripts.analysis.lib.llm_analyzer_anthropic import LLMPatternAnalyzerWithAnthropic

# 환경 변수에서 API 키 가져오기
api_key = os.getenv('ANTHROPIC_API_KEY')

analyzer = LLMPatternAnalyzerWithAnthropic(
    db_path='data/sambio_human.db',
    api_key=api_key
)
```

## 모델 선택

### 사용 가능한 모델
- **claude-3-opus-20240229**: 가장 강력한 모델, 복잡한 분석에 적합
- **claude-3-sonnet-20240229**: 균형잡힌 성능과 속도 (권장)
- **claude-3-haiku-20240307**: 가장 빠른 응답, 간단한 분석에 적합

### 모델 변경 방법
`llm_analyzer_anthropic.py` 파일에서:
```python
message = self.client.messages.create(
    model="claude-3-sonnet-20240229",  # 여기서 모델 변경
    max_tokens=4000,
    temperature=0.3,
    ...
)
```

## 비용 정보

### 가격 (2024년 기준)
- **Opus**: 입력 $15/백만 토큰, 출력 $75/백만 토큰
- **Sonnet**: 입력 $3/백만 토큰, 출력 $15/백만 토큰
- **Haiku**: 입력 $0.25/백만 토큰, 출력 $1.25/백만 토큰

### 예상 비용
- 98개 팀 분석 (약 10,000 토큰): Sonnet 기준 약 $0.05

## 장점과 한계

### 장점
- **의미론적 분석**: 데이터의 비즈니스 의미 이해
- **동적 클러스터링**: 고정 규칙이 아닌 지능형 분류
- **자연어 인사이트**: 맥락적이고 실행 가능한 추천
- **지속적 개선**: 모델 업데이트로 분석 품질 향상

### 한계
- **API 비용**: 대량 분석 시 비용 발생
- **응답 시간**: 네트워크 지연 및 처리 시간
- **API 제한**: 분당/일당 요청 제한
- **데이터 프라이버시**: 민감한 데이터 전송 주의

## 폴백 메커니즘

API 사용 불가 시 자동으로 규칙 기반 분석으로 전환:
1. API 키가 없는 경우
2. 네트워크 오류 발생 시
3. API 제한 초과 시
4. 응답 파싱 실패 시

## 문제 해결

### API 키 오류
```
Error: Invalid API key
```
→ API 키가 올바른지 확인

### 라이브러리 오류
```
ImportError: No module named 'anthropic'
```
→ `pip install anthropic` 실행

### 네트워크 오류
```
Connection error
```
→ 인터넷 연결 및 방화벽 설정 확인

## 보안 주의사항

1. **API 키 보호**
   - 코드에 직접 하드코딩 금지
   - 환경 변수 또는 설정 파일 사용
   - Git에 커밋하지 않도록 주의

2. **데이터 보안**
   - 민감한 개인정보 제거 후 전송
   - 필요시 데이터 익명화 처리

3. **접근 제어**
   - API 키 권한 최소화
   - 사용량 모니터링 설정