#!/bin/bash

# 대규모 배치 분석 실행 스크립트
# 3일 계획에 따라 단계적으로 실행

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 프로젝트 경로
PROJECT_ROOT="/Users/hanskim/Project/SambioHR3"
cd "$PROJECT_ROOT"

# 가상환경 활성화
source venv/bin/activate

# 날짜 설정 (최근 30일)
END_DATE=$(date +%Y-%m-%d)
START_DATE=$(date -v-30d +%Y-%m-%d)

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}대규모 배치 분석 실행${NC}"
echo -e "${GREEN}========================================${NC}"
echo "시작 날짜: $START_DATE"
echo "종료 날짜: $END_DATE"
echo "워커 수: 8"
echo ""

# Day 1: 준비 및 초기 실행 (테스트 + 20%)
if [ "$1" == "day1" ] || [ "$1" == "" ]; then
    echo -e "${YELLOW}[Day 1] 준비 및 초기 실행${NC}"
    
    # 1. 테스트 실행 (최근 3일, 100명)
    echo "1. 테스트 실행 (최근 3일 데이터)..."
    TEST_START=$(date -v-3d +%Y-%m-%d)
    python scripts/batch_analysis.py \
        --start-date "$TEST_START" \
        --end-date "$END_DATE" \
        --workers 4
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}테스트 실패! 설정을 확인하세요.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}테스트 성공!${NC}"
    
    # 2. 첫 번째 주 실행 (7일)
    echo "2. 첫 번째 주 데이터 처리..."
    WEEK1_START=$(date -v-30d +%Y-%m-%d)
    WEEK1_END=$(date -v-23d +%Y-%m-%d)
    
    python scripts/batch_analysis.py \
        --start-date "$WEEK1_START" \
        --end-date "$WEEK1_END" \
        --workers 8
    
    echo -e "${GREEN}Day 1 완료!${NC}"
fi

# Day 2: 메인 처리 (60%)
if [ "$1" == "day2" ]; then
    echo -e "${YELLOW}[Day 2] 메인 배치 처리${NC}"
    
    # 중간 2주 처리
    WEEK2_START=$(date -v-22d +%Y-%m-%d)
    WEEK2_END=$(date -v-8d +%Y-%m-%d)
    
    python scripts/batch_analysis.py \
        --start-date "$WEEK2_START" \
        --end-date "$WEEK2_END" \
        --workers 8
    
    echo -e "${GREEN}Day 2 완료!${NC}"
fi

# Day 3: 완료 및 검증
if [ "$1" == "day3" ]; then
    echo -e "${YELLOW}[Day 3] 마지막 주 처리 및 검증${NC}"
    
    # 마지막 주 처리
    WEEK4_START=$(date -v-7d +%Y-%m-%d)
    
    python scripts/batch_analysis.py \
        --start-date "$WEEK4_START" \
        --end-date "$END_DATE" \
        --workers 8
    
    # 검증
    echo "데이터 검증 중..."
    python scripts/verify_batch_results.py
    
    echo -e "${GREEN}Day 3 완료!${NC}"
fi

# 전체 실행 (한 번에)
if [ "$1" == "all" ]; then
    echo -e "${YELLOW}전체 기간 한 번에 처리${NC}"
    echo -e "${RED}주의: 이 작업은 3-4시간이 소요될 수 있습니다.${NC}"
    
    read -p "계속하시겠습니까? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        python scripts/batch_analysis.py \
            --start-date "$START_DATE" \
            --end-date "$END_DATE" \
            --workers 8
        
        echo -e "${GREEN}전체 처리 완료!${NC}"
    fi
fi

# 재시작 (실패 시)
if [ "$1" == "resume" ]; then
    if [ -z "$2" ]; then
        echo -e "${RED}재시작 위치를 지정하세요. 예: ./run_batch_analysis.sh resume 50000${NC}"
        exit 1
    fi
    
    echo -e "${YELLOW}위치 $2부터 재시작${NC}"
    
    python scripts/batch_analysis.py \
        --start-date "$START_DATE" \
        --end-date "$END_DATE" \
        --workers 8 \
        --resume-from $2
fi

# 상태 확인
if [ "$1" == "status" ]; then
    echo -e "${YELLOW}분석 진행 상태 확인${NC}"
    python scripts/check_analysis_status.py
fi

# 도움말
if [ "$1" == "help" ] || [ "$1" == "-h" ]; then
    echo "사용법:"
    echo "  ./run_batch_analysis.sh day1    # Day 1 실행 (테스트 + 첫 주)"
    echo "  ./run_batch_analysis.sh day2    # Day 2 실행 (중간 2주)"
    echo "  ./run_batch_analysis.sh day3    # Day 3 실행 (마지막 주 + 검증)"
    echo "  ./run_batch_analysis.sh all     # 전체 한 번에 실행"
    echo "  ./run_batch_analysis.sh resume N # N번째부터 재시작"
    echo "  ./run_batch_analysis.sh status  # 진행 상태 확인"
fi