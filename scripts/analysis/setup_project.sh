#!/bin/bash
# 분석 프로젝트 구조 생성

# 디렉토리 생성
mkdir -p scripts/analysis
mkdir -p scripts/analysis/lib
mkdir -p scripts/analysis/output
mkdir -p scripts/analysis/reports
mkdir -p data/analysis_results

# Python 가상환경 생성
cd scripts/analysis
python -m venv venv
source venv/bin/activate

# 필요 패키지 설치
pip install pandas numpy scikit-learn scipy matplotlib seaborn plotly
pip install sqlite3 openpyxl xlsxwriter

echo "✅ 분석 환경 구축 완료"