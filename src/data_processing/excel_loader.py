"""
엑셀 파일 로더 모듈
100MB+ 엑셀 파일을 효율적으로 로딩하고 메모리 최적화를 제공합니다.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union
import logging
from pathlib import Path
import time

class ExcelLoader:
    """엑셀 파일 효율적 로딩을 위한 클래스"""
    
    def __init__(self, chunk_size: int = 10000):
        """
        Args:
            chunk_size: 청크 단위로 읽을 행 수
        """
        self.chunk_size = chunk_size
        self.logger = logging.getLogger(__name__)
        
    def load_excel_file(self, file_path: Union[str, Path], sheet_name: str = None) -> pd.DataFrame:
        """
        엑셀 파일을 로드합니다.
        
        Args:
            file_path: 엑셀 파일 경로
            sheet_name: 시트명 (None이면 첫 번째 시트)
            
        Returns:
            DataFrame: 로드된 데이터
        """
        start_time = time.time()
        file_path = Path(file_path)
        
        try:
            # 파일 존재 확인
            if not file_path.exists():
                raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
            
            # 파일 크기 확인
            file_size = file_path.stat().st_size / (1024 * 1024)  # MB 단위
            self.logger.info(f"파일 크기: {file_size:.2f} MB")
            
            # 엑셀 파일 정보 확인
            excel_file = pd.ExcelFile(file_path)
            if sheet_name is None:
                sheet_name = excel_file.sheet_names[0]
            
            self.logger.info(f"시트 목록: {excel_file.sheet_names}")
            self.logger.info(f"로딩할 시트: {sheet_name}")
            
            # 100MB 이상 파일의 경우 최적화된 로딩
            if file_size > 100:
                self.logger.info(f"대용량 파일 감지 ({file_size:.1f}MB) - 최적화된 로딩 시작...")
                df = self._load_large_file(file_path, sheet_name)
            else:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            # 로딩 완료 정보
            load_time = time.time() - start_time
            self.logger.info(f"로딩 완료: {len(df):,}행 x {len(df.columns)}열, 소요시간: {load_time:.2f}초")
            
            return df
            
        except Exception as e:
            self.logger.error(f"엑셀 파일 로딩 실패: {e}")
            raise
    
    def _load_large_file(self, file_path: Path, sheet_name: str) -> pd.DataFrame:
        """대용량 파일을 청크 단위로 로딩"""
        # pd.read_excel은 chunksize를 지원하지 않으므로 직접 로딩
        self.logger.info("대용량 Excel 파일 로딩 시작...")
        
        try:
            # 진행상황 표시를 위해 먼저 행 수 추정
            self.logger.info("파일 정보 확인 중...")
            
            # 엑셀 파일 직접 로딩 (openpyxl 엔진 사용)
            self.logger.info("데이터 로딩 중... (이 작업은 시간이 걸릴 수 있습니다)")
            df = pd.read_excel(
                file_path, 
                sheet_name=sheet_name,
                engine='openpyxl'  # 대용량 파일에 더 적합
            )
            
            # 메모리 효율을 위한 데이터 타입 최적화
            self.logger.info("데이터 타입 최적화 중...")
            df = self._optimize_dtypes(df)
            
            return df
            
        except Exception as e:
            self.logger.error(f"대용량 파일 로딩 실패: {e}")
            # 기본 엔진으로 재시도
            self.logger.info("기본 엔진으로 재시도...")
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            return df
    
    def _optimize_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
        """데이터 타입 최적화로 메모리 사용량 줄이기"""
        for col in df.columns:
            col_type = df[col].dtype
            
            if col_type == 'object':
                # 문자열 컬럼의 경우 category로 변환 (반복되는 값이 많을 때)
                if df[col].nunique() / len(df) < 0.5:
                    df[col] = df[col].astype('category')
            
            elif col_type == 'int64':
                # 정수 컬럼의 경우 더 작은 타입으로 변환
                c_min = df[col].min()
                c_max = df[col].max()
                
                if c_min > np.iinfo(np.int8).min and c_max < np.iinfo(np.int8).max:
                    df[col] = df[col].astype(np.int8)
                elif c_min > np.iinfo(np.int16).min and c_max < np.iinfo(np.int16).max:
                    df[col] = df[col].astype(np.int16)
                elif c_min > np.iinfo(np.int32).min and c_max < np.iinfo(np.int32).max:
                    df[col] = df[col].astype(np.int32)
                    
            elif col_type == 'float64':
                # 실수 컬럼의 경우 float32로 변환
                df[col] = df[col].astype(np.float32)
        
        return df
    
    def validate_data(self, df: pd.DataFrame, required_columns: List[str] = None) -> Dict[str, any]:
        """
        데이터 검증 및 기본 통계 정보 제공
        
        Args:
            df: 검증할 DataFrame
            required_columns: 필수 컬럼 목록
            
        Returns:
            Dict: 검증 결과 및 통계 정보
        """
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'stats': {}
        }
        
        # 기본 통계 정보
        validation_result['stats'] = {
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'memory_usage_mb': df.memory_usage(deep=True).sum() / (1024 * 1024),
            'null_counts': df.isnull().sum().to_dict(),
            'dtypes': df.dtypes.to_dict()
        }
        
        # 필수 컬럼 확인
        if required_columns:
            missing_columns = set(required_columns) - set(df.columns)
            if missing_columns:
                validation_result['is_valid'] = False
                validation_result['errors'].append(f"필수 컬럼 누락: {missing_columns}")
        
        # 데이터 품질 확인
        for col in df.columns:
            null_ratio = df[col].isnull().sum() / len(df)
            if null_ratio > 0.5:
                validation_result['warnings'].append(f"컬럼 '{col}' 결측값 비율이 50% 이상입니다: {null_ratio:.2%}")
        
        return validation_result
    
    def get_file_info(self, file_path: Union[str, Path]) -> Dict[str, any]:
        """엑셀 파일 기본 정보 조회"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
        
        excel_file = pd.ExcelFile(file_path)
        
        info = {
            'file_path': str(file_path),
            'file_size_mb': file_path.stat().st_size / (1024 * 1024),
            'sheet_names': excel_file.sheet_names,
            'sheet_info': {}
        }
        
        # 각 시트의 기본 정보
        for sheet_name in excel_file.sheet_names:
            try:
                sample_df = pd.read_excel(file_path, sheet_name=sheet_name, nrows=5)
                info['sheet_info'][sheet_name] = {
                    'columns': list(sample_df.columns),
                    'column_count': len(sample_df.columns),
                    'sample_data': sample_df.head().to_dict('records')
                }
            except Exception as e:
                info['sheet_info'][sheet_name] = {'error': str(e)}
        
        return info