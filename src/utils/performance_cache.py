"""
성능 최적화를 위한 메모리 캐싱 시스템
태그 데이터 등 대용량 데이터의 반복 로딩을 방지
"""

import pandas as pd
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

class PerformanceCache:
    """성능 최적화를 위한 메모리 캐싱 시스템"""
    
    # 클래스 레벨 캐시 (싱글톤 패턴)
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize_cache()
        return cls._instance
    
    def _initialize_cache(self):
        """캐시 초기화"""
        self.tag_data_cache: Optional[pd.DataFrame] = None
        self.tag_data_loaded_at: Optional[datetime] = None
        
        self.organization_data_cache: Optional[pd.DataFrame] = None
        self.organization_loaded_at: Optional[datetime] = None
        
        self.tag_location_master_cache: Optional[pd.DataFrame] = None
        self.tag_location_master_loaded_at: Optional[datetime] = None
        
        self.claim_data_cache: Optional[pd.DataFrame] = None
        self.claim_data_loaded_at: Optional[datetime] = None
        
        self.analysis_results_cache: Dict[str, Any] = {}
        self.cache_ttl_minutes = 30  # 캐시 유지 시간
        
        logger.info("PerformanceCache 초기화 완료")
    
    def get_tag_data(self, pickle_manager=None) -> Optional[pd.DataFrame]:
        """태그 데이터 캐시된 로드"""
        try:
            # 캐시 유효성 확인
            if self._is_cache_valid('tag_data'):
                # Cache hit - removed debug logging
                return self.tag_data_cache
            
            # 캐시 미스 - 새로 로드
            logger.info("태그 데이터 새로 로드 중...")
            
            if pickle_manager is None:
                from ..database import get_pickle_manager
                pickle_manager = get_pickle_manager()
            
            start_time = datetime.now()
            self.tag_data_cache = pickle_manager.load_dataframe('tag_data')
            self.tag_data_loaded_at = start_time
            
            load_time = (datetime.now() - start_time).total_seconds()
            
            if self.tag_data_cache is not None:
                cache_size_mb = self.tag_data_cache.memory_usage(deep=True).sum() / 1024 / 1024
                logger.info(f"태그 데이터 로드 완료: {len(self.tag_data_cache):,}건, {cache_size_mb:.1f}MB, {load_time:.3f}초")
            else:
                logger.warning("태그 데이터 로드 실패")
            
            return self.tag_data_cache
            
        except Exception as e:
            logger.error(f"태그 데이터 캐시 로드 실패: {e}")
            return None
    
    def get_organization_data(self, pickle_manager=None) -> Optional[pd.DataFrame]:
        """조직 데이터 캐시된 로드"""
        try:
            if self._is_cache_valid('organization'):
                # Cache hit - removed debug logging
                return self.organization_data_cache
            
            logger.info("조직 데이터 새로 로드 중...")
            
            if pickle_manager is None:
                from ..database import get_pickle_manager
                pickle_manager = get_pickle_manager()
            
            start_time = datetime.now()
            
            # organization_data 또는 organization 시도
            self.organization_data_cache = pickle_manager.load_dataframe('organization_data')
            if self.organization_data_cache is None:
                self.organization_data_cache = pickle_manager.load_dataframe('organization')
            
            self.organization_loaded_at = start_time
            load_time = (datetime.now() - start_time).total_seconds()
            
            if self.organization_data_cache is not None:
                logger.info(f"조직 데이터 로드 완료: {len(self.organization_data_cache):,}건, {load_time:.3f}초")
            
            return self.organization_data_cache
            
        except Exception as e:
            logger.error(f"조직 데이터 캐시 로드 실패: {e}")
            return None
    
    def get_daily_tag_data(self, employee_id: str, selected_date, work_type: str = 'day_shift') -> Optional[pd.DataFrame]:
        """개인별 일별 태그 데이터 최적화 로드"""
        try:
            # 캐시 키 생성
            cache_key = f"daily_tag_{employee_id}_{selected_date}_{work_type}"
            
            # 분석 결과 캐시 확인 (짧은 TTL)
            if cache_key in self.analysis_results_cache:
                cache_entry = self.analysis_results_cache[cache_key]
                cache_time = cache_entry.get('cached_at')
                if cache_time and (datetime.now() - cache_time).seconds < 300:  # 5분 TTL
                    # Cache hit - removed debug logging
                    return cache_entry.get('data')
            
            # 전체 태그 데이터 가져오기 (캐시 활용)
            tag_data = self.get_tag_data()
            if tag_data is None:
                return None
            
            # 효율적인 필터링
            date_int = int(selected_date.strftime('%Y%m%d'))
            emp_id_int = int(employee_id)
            
            if work_type == 'night_shift':
                # 야간 근무: 전날 + 당일 데이터
                prev_date_int = int((selected_date - timedelta(days=1)).strftime('%Y%m%d'))
                
                # 벡터화된 필터링
                mask = (tag_data['사번'] == emp_id_int) & (
                    (tag_data['ENTE_DT'] == prev_date_int) | 
                    (tag_data['ENTE_DT'] == date_int)
                )
                daily_data = tag_data[mask].copy()
                
                # 시간 필터링 최적화
                if not daily_data.empty:
                    daily_data['hour'] = daily_data['출입시각'].astype(str).str[:2].astype(int)
                    mask = (
                        (daily_data['ENTE_DT'] == prev_date_int) & (daily_data['hour'] >= 17)
                    ) | (
                        (daily_data['ENTE_DT'] == date_int) & (daily_data['hour'] < 12)
                    )
                    daily_data = daily_data[mask]
            else:
                # 일반 근무: 당일 데이터만
                mask = (tag_data['사번'] == emp_id_int) & (tag_data['ENTE_DT'] == date_int)
                daily_data = tag_data[mask].copy()
            
            # 결과 캐싱
            if not daily_data.empty:
                # datetime 컬럼 생성 (필수)
                daily_data['time'] = daily_data['출입시각'].astype(str).str.zfill(6)
                daily_data['datetime'] = pd.to_datetime(
                    daily_data['ENTE_DT'].astype(str) + ' ' + daily_data['time'],
                    format='%Y%m%d %H%M%S'
                )
                daily_data = daily_data.sort_values('datetime')
                
                self.analysis_results_cache[cache_key] = {
                    'data': daily_data,
                    'cached_at': datetime.now()
                }
                
                # Data filtering complete - removed debug logging
            
            return daily_data if not daily_data.empty else None
            
        except Exception as e:
            logger.error(f"일별 태그 데이터 로드 실패: {employee_id}, {selected_date}, {e}")
            return None
    
    def get_tag_location_master(self, db_manager=None) -> Optional[pd.DataFrame]:
        """태깅지점 마스터 데이터 캐시된 로드"""
        try:
            # 캐시 유효성 확인
            if self._is_cache_valid('tag_location_master'):
                # Cache hit - removed debug logging
                return self.tag_location_master_cache
            
            # 캐시 미스 - 새로 로드
            logger.info("태깅지점 마스터 데이터 새로 로드 중...")
            
            if db_manager is None:
                from ..database import get_database_manager
                db_manager = get_database_manager()
            
            start_time = datetime.now()
            
            # 데이터베이스에서 로드
            from sqlalchemy import text
            query = """
            SELECT 
                "정렬No",
                "위치",
                COALESCE("DR_NO", "기기번호") as DR_NO,
                "게이트명" as DR_NM,
                "표기명",
                "입출구분" as INOUT_GB,
                "공간구분_code",
                "세부유형_code",
                "Tag_Code",
                "공간구분_NM",
                "세부유형_NM",
                "라벨링_활동"
            FROM tag_location_master
            ORDER BY "정렬No"
            """
            
            with db_manager.engine.connect() as conn:
                self.tag_location_master_cache = pd.read_sql(text(query), conn)
                
            self.tag_location_master_loaded_at = start_time
            load_time = (datetime.now() - start_time).total_seconds()
            
            if self.tag_location_master_cache is not None:
                # DR_NO 컬럼 정리
                self.tag_location_master_cache['DR_NO'] = self.tag_location_master_cache['DR_NO'].astype(str).str.strip()
                logger.info(f"태깅지점 마스터 데이터 로드 완료: {len(self.tag_location_master_cache):,}건, {load_time:.3f}초")
            else:
                logger.warning("태깅지점 마스터 데이터 로드 실패")
            
            return self.tag_location_master_cache
            
        except Exception as e:
            logger.error(f"태깅지점 마스터 데이터 캐시 로드 실패: {e}")
            return None
    
    def get_claim_data(self, pickle_manager=None) -> Optional[pd.DataFrame]:
        """Claim 데이터 캐시된 로드"""
        try:
            # 캐시 유효성 확인
            if self._is_cache_valid('claim_data'):
                # Cache hit - removed debug logging
                return self.claim_data_cache
            
            # 캐시 미스 - 새로 로드
            logger.info("Claim 데이터 새로 로드 중...")
            
            if pickle_manager is None:
                from ..database import get_pickle_manager
                pickle_manager = get_pickle_manager()
            
            start_time = datetime.now()
            self.claim_data_cache = pickle_manager.load_dataframe('claim_data')
            self.claim_data_loaded_at = start_time
            
            load_time = (datetime.now() - start_time).total_seconds()
            
            if self.claim_data_cache is not None:
                logger.info(f"Claim 데이터 로드 완료: {len(self.claim_data_cache):,}건, {load_time:.3f}초")
            else:
                logger.warning("Claim 데이터 로드 실패")
            
            return self.claim_data_cache
            
        except Exception as e:
            logger.error(f"Claim 데이터 캐시 로드 실패: {e}")
            return None
    
    def _is_cache_valid(self, cache_type: str) -> bool:
        """캐시 유효성 검사"""
        if cache_type == 'tag_data':
            return (self.tag_data_cache is not None and 
                   self.tag_data_loaded_at is not None and
                   (datetime.now() - self.tag_data_loaded_at).seconds < self.cache_ttl_minutes * 60)
        elif cache_type == 'organization':
            return (self.organization_data_cache is not None and 
                   self.organization_loaded_at is not None and
                   (datetime.now() - self.organization_loaded_at).seconds < self.cache_ttl_minutes * 60)
        elif cache_type == 'tag_location_master':
            return (self.tag_location_master_cache is not None and 
                   self.tag_location_master_loaded_at is not None and
                   (datetime.now() - self.tag_location_master_loaded_at).seconds < self.cache_ttl_minutes * 60)
        elif cache_type == 'claim_data':
            return (self.claim_data_cache is not None and 
                   self.claim_data_loaded_at is not None and
                   (datetime.now() - self.claim_data_loaded_at).seconds < self.cache_ttl_minutes * 60)
        return False
    
    def clear_cache(self, cache_type: str = 'all'):
        """캐시 클리어"""
        if cache_type in ['all', 'tag_data']:
            self.tag_data_cache = None
            self.tag_data_loaded_at = None
            logger.info("태그 데이터 캐시 클리어")
        
        if cache_type in ['all', 'organization']:
            self.organization_data_cache = None
            self.organization_loaded_at = None
            logger.info("조직 데이터 캐시 클리어")
        
        if cache_type in ['all', 'analysis']:
            self.analysis_results_cache.clear()
            logger.info("분석 결과 캐시 클리어")
        
        if cache_type in ['all', 'tag_location_master']:
            self.tag_location_master_cache = None
            self.tag_location_master_loaded_at = None
            logger.info("태깅지점 마스터 캐시 클리어")
        
        if cache_type in ['all', 'claim_data']:
            self.claim_data_cache = None
            self.claim_data_loaded_at = None
            logger.info("Claim 데이터 캐시 클리어")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 정보"""
        stats = {
            'tag_data_cached': self.tag_data_cache is not None,
            'tag_data_size': len(self.tag_data_cache) if self.tag_data_cache is not None else 0,
            'organization_cached': self.organization_data_cache is not None,
            'organization_size': len(self.organization_data_cache) if self.organization_data_cache is not None else 0,
            'tag_location_master_cached': self.tag_location_master_cache is not None,
            'tag_location_master_size': len(self.tag_location_master_cache) if self.tag_location_master_cache is not None else 0,
            'claim_data_cached': self.claim_data_cache is not None,
            'claim_data_size': len(self.claim_data_cache) if self.claim_data_cache is not None else 0,
            'analysis_cache_count': len(self.analysis_results_cache),
            'memory_usage_mb': self._calculate_memory_usage()
        }
        return stats
    
    def _calculate_memory_usage(self) -> float:
        """캐시 메모리 사용량 계산 (MB)"""
        total_bytes = 0
        
        if self.tag_data_cache is not None:
            total_bytes += self.tag_data_cache.memory_usage(deep=True).sum()
        
        if self.organization_data_cache is not None:
            total_bytes += self.organization_data_cache.memory_usage(deep=True).sum()
        
        if self.tag_location_master_cache is not None:
            total_bytes += self.tag_location_master_cache.memory_usage(deep=True).sum()
        
        if self.claim_data_cache is not None:
            total_bytes += self.claim_data_cache.memory_usage(deep=True).sum()
        
        # 분석 결과 캐시는 대략 추정
        total_bytes += len(self.analysis_results_cache) * 10 * 1024  # 대략 10KB per entry
        
        return total_bytes / 1024 / 1024

# 전역 캐시 인스턴스
_cache_instance = None

def get_performance_cache() -> PerformanceCache:
    """성능 캐시 싱글톤 인스턴스 반환"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = PerformanceCache()
    return _cache_instance