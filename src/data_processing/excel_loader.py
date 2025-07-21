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
        
    def load_excel_file(self, file_path: Union[str, Path], sheet_name: str = None, 
                       auto_merge_sheets: bool = True) -> pd.DataFrame:
        """
        엑셀 파일을 로드합니다.
        
        Args:
            file_path: 엑셀 파일 경로
            sheet_name: 시트명 (None이면 모든 시트를 자동으로 병합)
            auto_merge_sheets: 여러 시트를 자동으로 병합할지 여부
            
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
            sheet_names = excel_file.sheet_names
            self.logger.info(f"시트 목록: {sheet_names}")
            
            # 시트 이름이 지정되지 않았고, 여러 시트가 있으며, 자동 병합이 활성화된 경우
            if sheet_name is None and len(sheet_names) > 1 and auto_merge_sheets:
                # 태깅 데이터의 경우 Sheet1, Sheet2를 자동으로 병합
                if any('sheet' in name.lower() for name in sheet_names):
                    self.logger.info("여러 시트 감지 - 자동 병합 모드")
                    return self._load_and_merge_sheets(file_path, sheet_names, file_size)
            
            # 단일 시트 로딩
            if sheet_name is None:
                sheet_name = sheet_names[0]
            
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
    
    def _load_and_merge_sheets(self, file_path: Path, sheet_names: List[str], file_size: float) -> pd.DataFrame:
        """여러 시트를 읽어서 병합"""
        self.logger.info(f"{len(sheet_names)}개의 시트를 병합합니다...")
        
        all_dfs = []
        total_rows = 0
        
        # Sheet1, Sheet2 등의 패턴을 가진 시트들만 필터링
        sheets_to_merge = []
        for sheet in sheet_names:
            if 'sheet' in sheet.lower() or sheet.startswith('Sheet'):
                sheets_to_merge.append(sheet)
        
        # 시트 이름 순서대로 정렬 (Sheet1, Sheet2, ...)
        sheets_to_merge.sort()
        
        self.logger.info(f"병합할 시트: {sheets_to_merge}")
        
        for idx, sheet in enumerate(sheets_to_merge):
            try:
                self.logger.info(f"[{idx+1}/{len(sheets_to_merge)}] {sheet} 시트 로딩 중...")
                
                # 각 시트 로드
                if file_size > 100:
                    df_sheet = self._load_large_file(file_path, sheet)
                else:
                    df_sheet = pd.read_excel(file_path, sheet_name=sheet)
                
                rows_in_sheet = len(df_sheet)
                self.logger.info(f"{sheet}: {rows_in_sheet:,}행 로드됨")
                
                # 첫 번째 시트가 아닌 경우, 컬럼이 일치하는지 확인
                if idx > 0 and len(all_dfs) > 0:
                    if not df_sheet.columns.equals(all_dfs[0].columns):
                        self.logger.warning(f"{sheet} 시트의 컬럼이 첫 번째 시트와 다릅니다. 공통 컬럼만 사용합니다.")
                        # 공통 컬럼만 선택
                        common_columns = list(set(all_dfs[0].columns) & set(df_sheet.columns))
                        df_sheet = df_sheet[common_columns]
                        if idx == 1:  # 첫 번째 시트도 공통 컬럼만 선택
                            all_dfs[0] = all_dfs[0][common_columns]
                
                all_dfs.append(df_sheet)
                total_rows += rows_in_sheet
                
            except Exception as e:
                self.logger.error(f"{sheet} 시트 로딩 실패: {e}")
                continue
        
        if not all_dfs:
            raise ValueError("병합할 수 있는 시트가 없습니다.")
        
        # 모든 시트 병합
        self.logger.info("시트 병합 중...")
        combined_df = pd.concat(all_dfs, ignore_index=True)
        
        # 중복 제거 옵션 (필요한 경우)
        # combined_df = combined_df.drop_duplicates()
        
        self.logger.info(f"병합 완료: 총 {len(combined_df):,}행 (원본 {total_rows:,}행)")
        
        # 메모리 최적화
        if file_size > 100:
            combined_df = self._optimize_dtypes(combined_df)
        
        return combined_df
    
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