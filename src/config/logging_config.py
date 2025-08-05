"""
로깅 설정 모듈
애플리케이션 전체의 로깅 레벨과 포맷을 관리
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

# 로그 디렉토리 생성
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# 로깅 레벨 설정
LOG_LEVEL = logging.WARNING  # INFO -> WARNING으로 변경 (불필요한 로그 제거)
DEBUG_MODE = False  # 개발 시에만 True로 설정

# 로그 포맷
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
SIMPLE_FORMAT = "%(levelname)s - %(message)s"

# 모듈별 로깅 레벨 커스터마이징
MODULE_LOG_LEVELS = {
    "src.data_processing.pickle_manager": logging.WARNING,  # 캐시 로드 메시지 제거
    "src.database.singleton_manager": logging.WARNING,      # 싱글톤 메시지 제거
    "src.analysis.individual_analyzer": logging.WARNING,    # 분석 상세 메시지 제거
    "src.data.knox_processors": logging.WARNING,           # Knox 처리 메시지 제거
    "src.hmm": logging.WARNING,                            # HMM 관련 메시지 제거
    "src.ui": logging.INFO,                                # UI는 INFO 유지
    "streamlit": logging.WARNING,                          # Streamlit 메시지 제거
}

def setup_logging(log_file: str = None, debug: bool = False):
    """
    로깅 설정 초기화
    
    Args:
        log_file: 로그 파일명 (None이면 콘솔만 출력)
        debug: 디버그 모드 활성화 여부
    """
    global DEBUG_MODE
    DEBUG_MODE = debug
    
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if debug else LOG_LEVEL)
    
    # 기존 핸들러 제거
    root_logger.handlers = []
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if debug else LOG_LEVEL)
    console_handler.setFormatter(logging.Formatter(SIMPLE_FORMAT))
    root_logger.addHandler(console_handler)
    
    # 파일 핸들러 (옵션)
    if log_file:
        file_path = LOG_DIR / f"{log_file}_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(file_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # 파일에는 모든 로그 저장
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root_logger.addHandler(file_handler)
    
    # 모듈별 로깅 레벨 설정
    for module_name, level in MODULE_LOG_LEVELS.items():
        module_logger = logging.getLogger(module_name)
        module_logger.setLevel(level)
    
    # 외부 라이브러리 로깅 억제
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    
def get_logger(name: str) -> logging.Logger:
    """
    모듈별 로거 생성
    
    Args:
        name: 모듈명 (보통 __name__ 사용)
        
    Returns:
        logging.Logger: 설정된 로거
    """
    logger = logging.getLogger(name)
    
    # 디버그 모드일 때만 상세 로깅
    if DEBUG_MODE:
        logger.setLevel(logging.DEBUG)
    
    return logger

# 성능 중요 함수들을 위한 조건부 로깅
def debug_log(logger: logging.Logger, message: str, *args):
    """디버그 모드에서만 로깅"""
    if DEBUG_MODE:
        logger.debug(message, *args)

def info_log(logger: logging.Logger, message: str, *args):
    """중요한 정보만 로깅"""
    if logger.isEnabledFor(logging.INFO):
        logger.info(message, *args)

# 데이터 로딩 관련 특별 처리
class DataLoadingLogger:
    """데이터 로딩 관련 로깅을 스마트하게 처리"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self._load_count = {}
        self._last_log_time = {}
    
    def log_cache_hit(self, cache_key: str):
        """캐시 히트는 디버그 레벨로만"""
        debug_log(self.logger, f"캐시 히트: {cache_key}")
    
    def log_cache_miss(self, cache_key: str):
        """캐시 미스는 처음 또는 일정 시간 후에만 로깅"""
        current_time = datetime.now()
        last_time = self._last_log_time.get(cache_key)
        
        # 5분 이내 동일 키 로깅 억제
        if last_time and (current_time - last_time).seconds < 300:
            return
            
        self.logger.info(f"캐시 미스 (DB 조회): {cache_key}")
        self._last_log_time[cache_key] = current_time
    
    def log_data_loaded(self, source: str, rows: int, duration: float = None):
        """데이터 로드 완료 시 요약 정보만"""
        if rows > 10000:  # 대용량 데이터만 로깅
            msg = f"{source}에서 {rows:,}행 로드"
            if duration:
                msg += f" ({duration:.2f}초)"
            self.logger.info(msg)