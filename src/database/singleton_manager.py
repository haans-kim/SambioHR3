"""
싱글톤 패턴을 사용한 데이터베이스 및 데이터 매니저
메모리 효율성을 위해 인스턴스를 재사용
"""

import threading
from typing import Optional
from .db_manager import DatabaseManager
from ..data_processing import PickleManager
import logging

logger = logging.getLogger(__name__)


class SingletonMeta(type):
    """
    스레드 안전한 싱글톤 메타클래스
    """
    _instances = {}
    _lock = threading.Lock()
    
    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
                logger.debug(f"{cls.__name__} 싱글톤 인스턴스 생성")
            return cls._instances[cls]


class SingletonDatabaseManager(DatabaseManager, metaclass=SingletonMeta):
    """
    싱글톤 패턴을 적용한 데이터베이스 매니저
    """
    _initialized = False
    
    def __init__(self, *args, **kwargs):
        if not self._initialized:
            super().__init__(*args, **kwargs)
            SingletonDatabaseManager._initialized = True
            logger.debug("SingletonDatabaseManager 초기화 완료")
    
    def _auto_load_pickle_data(self):
        """
        첫 번째 인스턴스 생성 시에만 pickle 데이터 로드
        """
        if hasattr(self, '_pickle_loaded'):
            logger.debug("Pickle 데이터가 이미 로드되어 있습니다.")
            return
            
        super()._auto_load_pickle_data()
        self._pickle_loaded = True


class SingletonPickleManager(PickleManager, metaclass=SingletonMeta):
    """
    싱글톤 패턴을 적용한 Pickle 매니저
    캐시된 데이터를 메모리에 유지
    """
    _initialized = False
    _cache = {}
    
    def __init__(self, *args, **kwargs):
        if not self._initialized:
            super().__init__(*args, **kwargs)
            SingletonPickleManager._initialized = True
            logger.debug("SingletonPickleManager 초기화 완료")
    
    def load_dataframe(self, name: str, version: Optional[str] = None):
        """
        캐시를 확인한 후 데이터프레임 로드
        """
        cache_key = f"{name}_{version or 'latest'}"
        
        if cache_key in self._cache:
            logger.debug(f"캐시 히트: {cache_key}")
            return self._cache[cache_key]
        
        # 캐시에 없으면 부모 클래스에서 로드
        df = super().load_dataframe(name, version)
        
        if df is not None:
            # 캐시에 저장 (메모리 사용량 제한을 위해 최대 10개만 유지)
            if len(self._cache) >= 10:
                # 가장 오래된 항목 제거
                first_key = next(iter(self._cache))
                del self._cache[first_key]
                logger.debug(f"캐시 오버플로우 - 제거: {first_key}")
            
            self._cache[cache_key] = df
            logger.debug(f"캐시 저장: {cache_key}")
        
        return df
    
    def clear_cache(self):
        """캐시 비우기"""
        self._cache.clear()
        logger.debug("PickleManager 캐시 비움")


def get_database_manager():
    """싱글톤 데이터베이스 매니저 인스턴스 반환"""
    return SingletonDatabaseManager()


def get_pickle_manager():
    """싱글톤 Pickle 매니저 인스턴스 반환"""
    return SingletonPickleManager()


def reset_singletons():
    """싱글톤 인스턴스 초기화 (테스트 용도)"""
    SingletonMeta._instances.clear()
    SingletonDatabaseManager._initialized = False
    SingletonPickleManager._initialized = False
    SingletonPickleManager._cache.clear()
    logger.debug("모든 싱글톤 인스턴스 초기화")