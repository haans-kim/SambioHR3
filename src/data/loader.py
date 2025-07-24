import pandas as pd
import pickle
import time
import os
from typing import Optional, Union
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataLoader:
    """Excel 및 Pickle 파일을 로드하는 클래스"""
    
    def __init__(self, cache_dir: str = "./cache"):
        """
        Args:
            cache_dir: Pickle 캐시 파일을 저장할 디렉토리
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
    
    def load_excel(self, file_path: Union[str, Path], use_cache: bool = True) -> pd.DataFrame:
        """
        Excel 파일을 로드하고 캐시를 생성합니다.
        
        Args:
            file_path: Excel 파일 경로
            use_cache: 캐시 사용 여부
            
        Returns:
            pd.DataFrame: 로드된 데이터프레임
        """
        file_path = Path(file_path)
        cache_path = self._get_cache_path(file_path)
        
        # 캐시 확인
        if use_cache and cache_path.exists():
            # 캐시가 원본보다 최신인지 확인
            if cache_path.stat().st_mtime > file_path.stat().st_mtime:
                logger.info(f"Loading from cache: {cache_path}")
                return self._load_pickle(cache_path)
        
        # Excel 파일 로드
        logger.info(f"Loading Excel file: {file_path}")
        start_time = time.time()
        
        try:
            df = pd.read_excel(file_path)
            load_time = time.time() - start_time
            logger.info(f"Excel loaded in {load_time:.2f} seconds")
            
            # 캐시 저장
            if use_cache:
                self._save_pickle(df, cache_path)
                
            return df
            
        except Exception as e:
            logger.error(f"Error loading Excel file: {e}")
            raise
    
    def _get_cache_path(self, file_path: Path) -> Path:
        """캐시 파일 경로 생성"""
        cache_name = f"{file_path.stem}.pkl"
        return self.cache_dir / cache_name
    
    def _load_pickle(self, pickle_path: Path) -> pd.DataFrame:
        """Pickle 파일 로드"""
        start_time = time.time()
        
        try:
            with open(pickle_path, 'rb') as f:
                df = pickle.load(f)
            
            load_time = time.time() - start_time
            logger.info(f"Pickle loaded in {load_time:.2f} seconds")
            return df
            
        except Exception as e:
            logger.error(f"Error loading pickle file: {e}")
            raise
    
    def _save_pickle(self, df: pd.DataFrame, pickle_path: Path):
        """데이터프레임을 Pickle로 저장"""
        try:
            with open(pickle_path, 'wb') as f:
                pickle.dump(df, f)
            logger.info(f"Cache saved to: {pickle_path}")
            
        except Exception as e:
            logger.error(f"Error saving pickle file: {e}")
            # 캐시 저장 실패는 치명적이지 않으므로 예외를 다시 발생시키지 않음
    
    def load_tag_data(self, file_path: Union[str, Path]) -> pd.DataFrame:
        """
        태그 데이터를 로드하고 기본 전처리를 수행합니다.
        
        Args:
            file_path: 태그 데이터 파일 경로
            
        Returns:
            pd.DataFrame: 전처리된 태그 데이터
        """
        df = self.load_excel(file_path)
        
        # 기본 전처리
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
        
        # 중복 제거
        df = df.drop_duplicates()
        
        logger.info(f"Loaded {len(df)} records from {file_path}")
        return df
    
    def load_multiple_files(self, file_paths: list) -> dict:
        """
        여러 파일을 동시에 로드합니다.
        
        Args:
            file_paths: 파일 경로 리스트
            
        Returns:
            dict: 파일명을 키로 하는 데이터프레임 딕셔너리
        """
        data_dict = {}
        
        for file_path in file_paths:
            file_path = Path(file_path)
            try:
                df = self.load_excel(file_path)
                data_dict[file_path.stem] = df
                
            except Exception as e:
                logger.error(f"Failed to load {file_path}: {e}")
                
        return data_dict


# 사용 예시
if __name__ == "__main__":
    loader = DataLoader()
    
    # 태그 데이터 로드
    tag_data = loader.load_tag_data("data/tag_data_24.6.xlsx")
    print(f"Tag data shape: {tag_data.shape}")
    print(f"Columns: {tag_data.columns.tolist()}")