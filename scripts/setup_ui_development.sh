#!/bin/bash

# UI 개발 환경 설정 스크립트
# Mock 데이터 생성 및 서버 실행

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_ROOT="/Users/hanskim/Project/SambioHR3"
cd "$PROJECT_ROOT"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Sambio Analytics UI 개발 환경 설정${NC}"
echo -e "${BLUE}========================================${NC}"

# 1. Mock 데이터 생성
if [ "$1" == "mock" ] || [ "$1" == "" ]; then
    echo -e "\n${YELLOW}[1/3] Mock 데이터 생성${NC}"
    
    # 가상환경 활성화
    source venv/bin/activate
    
    # Mock DB 생성
    if [ -f "data/sambio_analytics_mock.db" ]; then
        echo -e "${YELLOW}기존 Mock DB가 있습니다. 재생성하시겠습니까? (y/n)${NC}"
        read -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -f data/sambio_analytics_mock.db
            python scripts/create_mock_analytics_db.py --quick
        fi
    else
        python scripts/create_mock_analytics_db.py --quick
    fi
    
    echo -e "${GREEN}✅ Mock 데이터 생성 완료${NC}"
fi

# 2. FastAPI 서버 실행
if [ "$1" == "server" ] || [ "$1" == "" ]; then
    echo -e "\n${YELLOW}[2/3] FastAPI 백엔드 서버 시작${NC}"
    
    # uvicorn 설치 확인
    if ! pip show uvicorn > /dev/null 2>&1; then
        echo "uvicorn 설치 중..."
        pip install fastapi uvicorn pandas
    fi
    
    # 서버 실행 (백그라운드)
    echo -e "${GREEN}서버 시작 중...${NC}"
    echo -e "API 문서: ${BLUE}http://localhost:8000/docs${NC}"
    
    if [ "$1" == "server" ]; then
        # 포그라운드 실행
        python backend/fastapi_server.py
    else
        # 백그라운드 실행
        nohup python backend/fastapi_server.py > backend/server.log 2>&1 &
        echo $! > backend/server.pid
        echo -e "${GREEN}✅ 서버가 백그라운드에서 실행 중 (PID: $(cat backend/server.pid))${NC}"
    fi
fi

# 3. React 프로젝트 설정
if [ "$1" == "react" ]; then
    echo -e "\n${YELLOW}[3/3] React 프로젝트 설정${NC}"
    
    # React 프로젝트 생성
    if [ ! -d "sambio-analytics-ui" ]; then
        echo "React 프로젝트 생성 중..."
        npx create-react-app sambio-analytics-ui --template typescript
        
        cd sambio-analytics-ui
        
        # 필요한 패키지 설치
        echo "패키지 설치 중..."
        npm install axios react-router-dom @reduxjs/toolkit react-redux
        npm install recharts react-datepicker classnames
        npm install @types/react-datepicker --save-dev
        
        echo -e "${GREEN}✅ React 프로젝트 생성 완료${NC}"
    else
        echo -e "${YELLOW}React 프로젝트가 이미 존재합니다.${NC}"
    fi
    
    # React 개발 서버 실행
    cd sambio-analytics-ui
    echo -e "${GREEN}React 개발 서버 시작...${NC}"
    npm start
fi

# 상태 확인
if [ "$1" == "status" ]; then
    echo -e "\n${YELLOW}시스템 상태 확인${NC}"
    
    # Mock DB 확인
    if [ -f "data/sambio_analytics_mock.db" ]; then
        SIZE=$(du -h data/sambio_analytics_mock.db | cut -f1)
        echo -e "✅ Mock DB: ${GREEN}존재 ($SIZE)${NC}"
    else
        echo -e "❌ Mock DB: ${RED}없음${NC}"
    fi
    
    # 서버 상태 확인
    if [ -f "backend/server.pid" ]; then
        PID=$(cat backend/server.pid)
        if ps -p $PID > /dev/null; then
            echo -e "✅ FastAPI 서버: ${GREEN}실행 중 (PID: $PID)${NC}"
            
            # API 상태 확인
            if curl -s http://localhost:8000 > /dev/null; then
                echo -e "✅ API 응답: ${GREEN}정상${NC}"
            else
                echo -e "⚠️  API 응답: ${YELLOW}확인 필요${NC}"
            fi
        else
            echo -e "❌ FastAPI 서버: ${RED}중지됨${NC}"
        fi
    else
        echo -e "❌ FastAPI 서버: ${RED}실행되지 않음${NC}"
    fi
    
    # React 프로젝트 확인
    if [ -d "sambio-analytics-ui" ]; then
        echo -e "✅ React 프로젝트: ${GREEN}존재${NC}"
    else
        echo -e "❌ React 프로젝트: ${RED}없음${NC}"
    fi
fi

# 서버 중지
if [ "$1" == "stop" ]; then
    echo -e "\n${YELLOW}서버 중지${NC}"
    
    if [ -f "backend/server.pid" ]; then
        PID=$(cat backend/server.pid)
        kill $PID 2>/dev/null
        rm backend/server.pid
        echo -e "${GREEN}✅ 서버 중지됨${NC}"
    else
        echo -e "${YELLOW}실행 중인 서버가 없습니다.${NC}"
    fi
fi

# 도움말
if [ "$1" == "help" ] || [ "$1" == "-h" ]; then
    echo -e "\n${BLUE}사용법:${NC}"
    echo "  ./setup_ui_development.sh         # 전체 설정 (Mock 생성 + 서버 시작)"
    echo "  ./setup_ui_development.sh mock    # Mock 데이터만 생성"
    echo "  ./setup_ui_development.sh server  # FastAPI 서버만 실행"
    echo "  ./setup_ui_development.sh react   # React 프로젝트 설정 및 실행"
    echo "  ./setup_ui_development.sh status  # 시스템 상태 확인"
    echo "  ./setup_ui_development.sh stop    # 서버 중지"
    echo ""
    echo -e "${BLUE}빠른 시작:${NC}"
    echo "  1. ./setup_ui_development.sh      # Mock 데이터 + 서버"
    echo "  2. ./setup_ui_development.sh react # 별도 터미널에서 React"
fi

# 기본 실행 (인자 없을 때)
if [ "$1" == "" ]; then
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}설정 완료!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "다음 단계:"
    echo -e "1. API 문서 확인: ${BLUE}http://localhost:8000/docs${NC}"
    echo -e "2. React 프로젝트 실행: ${YELLOW}./setup_ui_development.sh react${NC}"
    echo ""
    echo -e "상태 확인: ${YELLOW}./setup_ui_development.sh status${NC}"
    echo -e "서버 중지: ${YELLOW}./setup_ui_development.sh stop${NC}"
fi