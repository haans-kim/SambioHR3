#!/usr/bin/env python3
"""
스크립트 공통 설정 파일
경로, 파일명 등 공통 설정을 중앙 관리
"""

import os
from pathlib import Path

# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).parent.parent.absolute()

# 디렉토리 경로
DATA_DIR = PROJECT_ROOT / "data"
PICKLE_DIR = DATA_DIR / "pickles"
DOC_DIR = PROJECT_ROOT / "doc"
SRC_DIR = PROJECT_ROOT / "src"
DATABASE_DIR = PROJECT_ROOT / "database"

# 데이터베이스 경로
DATABASE_PATH = DATABASE_DIR / "sambio_hr.db"

# 로그 디렉토리
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 파일 경로 패턴
TAG_LOCATION_MASTER_PATTERN = "tag_location_master_*.pkl.gz"
EQUIPMENT_DATA_PATTERN = "equipment_data_*.pkl.gz"
O_TAGS_PATTERN = "o_tags_equipment_*.pkl.gz"

# Excel 파일 경로
TAG_TRANSITION_PROB_FILE = DOC_DIR / "tag_transition_probabilities.xlsx"
TAG_LOCATION_MASTER_EXCEL = DATA_DIR / "tag_location_master.xlsx"

# 설정값
DEFAULT_ENCODING = "utf-8"
CHUNK_SIZE = 10000  # 대용량 파일 처리 시 청크 크기

# 날짜 형식
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# 교대 근무 시간 정의
SHIFT_TIMES = {
    "DAY": {"start": "08:00", "end": "20:00"},
    "NIGHT": {"start": "20:00", "end": "08:00"}
}

# 식사 시간 정의
MEAL_TIMES = {
    "BREAKFAST": {"start": "06:30", "end": "09:00"},
    "LUNCH": {"start": "11:20", "end": "13:20"},
    "DINNER": {"start": "17:00", "end": "20:00"},
    "MIDNIGHT_MEAL": {"start": "23:30", "end": "01:00"}
}

# 활동 상태 정의
ACTIVITY_STATES = [
    "WORK", "FOCUSED_WORK", "EQUIPMENT_OPERATION", "MEETING",
    "BREAKFAST", "LUNCH", "DINNER", "MIDNIGHT_MEAL",
    "BREAK", "MOVEMENT", "IDLE", "BATHROOM", "SMOKING",
    "PERSONAL", "TRAINING", "CLEANING", "OTHER"
]

def get_latest_file(pattern, directory=PICKLE_DIR):
    """
    주어진 패턴에 맞는 가장 최신 파일 반환
    
    Args:
        pattern: 파일명 패턴 (glob 패턴)
        directory: 검색할 디렉토리
        
    Returns:
        Path: 가장 최신 파일 경로 또는 None
    """
    files = list(directory.glob(pattern))
    if files:
        return max(files, key=lambda f: f.stat().st_mtime)
    return None

def ensure_directory(path):
    """디렉토리가 없으면 생성"""
    Path(path).mkdir(parents=True, exist_ok=True)
    return Path(path)