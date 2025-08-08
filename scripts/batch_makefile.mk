# Makefile for Batch Analysis Operations
# Usage: make -f scripts/batch_makefile.mk [target]

PYTHON = python3
VENV = venv
PROJECT_ROOT = /Users/hanskim/Project/SambioHR3
WORKERS = 8

# 날짜 설정 (최근 30일)
END_DATE := $(shell date +%Y-%m-%d)
START_DATE := $(shell date -v-30d +%Y-%m-%d)

.PHONY: help test day1 day2 day3 all status verify clean

help:
	@echo "Sambio 배치 분석 명령어:"
	@echo "  make test     - 테스트 실행 (3일 데이터)"
	@echo "  make day1     - Day 1 실행 (첫 주)"
	@echo "  make day2     - Day 2 실행 (중간 2주)"
	@echo "  make day3     - Day 3 실행 (마지막 주)"
	@echo "  make all      - 전체 실행 (3-4시간)"
	@echo "  make status   - 진행 상태 확인"
	@echo "  make verify   - 결과 검증"
	@echo "  make clean    - 분석 DB 초기화"

test:
	@echo "테스트 실행 (최근 3일)..."
	@$(PYTHON) scripts/batch_analysis.py \
		--start-date $$(date -v-3d +%Y-%m-%d) \
		--end-date $(END_DATE) \
		--workers 4

day1:
	@echo "Day 1: 첫 주 처리..."
	@$(PYTHON) scripts/batch_analysis.py \
		--start-date $(START_DATE) \
		--end-date $$(date -v-23d +%Y-%m-%d) \
		--workers $(WORKERS)

day2:
	@echo "Day 2: 중간 2주 처리..."
	@$(PYTHON) scripts/batch_analysis.py \
		--start-date $$(date -v-22d +%Y-%m-%d) \
		--end-date $$(date -v-8d +%Y-%m-%d) \
		--workers $(WORKERS)

day3:
	@echo "Day 3: 마지막 주 처리..."
	@$(PYTHON) scripts/batch_analysis.py \
		--start-date $$(date -v-7d +%Y-%m-%d) \
		--end-date $(END_DATE) \
		--workers $(WORKERS)
	@echo "검증 실행..."
	@$(PYTHON) scripts/verify_batch_results.py

all:
	@echo "전체 기간 처리 (30일)..."
	@echo "예상 시간: 3-4시간"
	@read -p "계속하시겠습니까? [y/N] " confirm && \
	if [ "$$confirm" = "y" ]; then \
		$(PYTHON) scripts/batch_analysis.py \
			--start-date $(START_DATE) \
			--end-date $(END_DATE) \
			--workers $(WORKERS); \
	fi

status:
	@$(PYTHON) scripts/check_analysis_status.py

verify:
	@$(PYTHON) scripts/verify_batch_results.py

clean:
	@echo "분석 DB 초기화..."
	@read -p "정말로 삭제하시겠습니까? [y/N] " confirm && \
	if [ "$$confirm" = "y" ]; then \
		rm -f $(PROJECT_ROOT)/data/sambio_analytics.db; \
		echo "삭제 완료"; \
	fi

# 재시작 (특정 위치부터)
resume-%:
	@echo "위치 $* 부터 재시작..."
	@$(PYTHON) scripts/batch_analysis.py \
		--start-date $(START_DATE) \
		--end-date $(END_DATE) \
		--workers $(WORKERS) \
		--resume-from $*