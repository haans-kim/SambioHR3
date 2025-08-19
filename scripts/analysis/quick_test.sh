#!/bin/bash
# 빠른 테스트 스크립트

echo "========================================="
echo "부서별 차이 분석 시스템 테스트"
echo "========================================="

# 1. SQL 분석 실행
echo -e "\n[1] SQL 기반 빠른 분석 실행..."
sqlite3 ../../data/sambio_human.db < 01_basic_pattern_analysis.sql > output/sql_result.txt
echo "  → SQL 분석 완료: output/sql_result.txt"

# 2. Python 분석 실행 (가상환경 확인)
echo -e "\n[2] Python 분석 실행 준비..."
if [ ! -d "venv" ]; then
    echo "  → 가상환경 생성 중..."
    python -m venv venv
    source venv/bin/activate
    pip install pandas numpy scikit-learn scipy matplotlib seaborn
else
    source venv/bin/activate
fi

# 3. 메인 분석 실행
echo -e "\n[3] 메인 분석 실행..."
python run_analysis.py

echo -e "\n========================================="
echo "테스트 완료!"
echo "결과 확인: scripts/analysis/output/"
echo "========================================="