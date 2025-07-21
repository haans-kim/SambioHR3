"""
Pickle 파일 관리 모듈
데이터프레임 직렬화/역직렬화, 버전 관리, 캐싱 전략을 제공합니다.
"""

import pickle
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Union
from pathlib import Path
import logging
import hashlib
import json
from datetime import datetime
import gzip
import warnings

class PickleManager:
    """Pickle 파일 관리를 위한 클래스"""
    
    def __init__(self, base_path: Union[str, Path] = "data/pickles"):
        """
        Args:
            base_path: pickle 파일 저장 기본 경로
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
        # 메타데이터 파일 경로
        self.metadata_file = self.base_path / "metadata.json"
        self.metadata = self._load_metadata()
    
    def save_dataframe(self, df: pd.DataFrame, name: str, version: str = None, 
                      compress: bool = True, description: str = None) -> str:
        """
        DataFrame을 pickle 파일로 저장
        
        Args:
            df: 저장할 DataFrame
            name: 파일명 (확장자 제외)
            version: 버전 정보 (없으면 자동 생성)
            compress: 압축 여부
            description: 파일 설명
            
        Returns:
            str: 저장된 파일 경로
        """
        if version is None:
            version = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 파일명 생성
        extension = ".pkl.gz" if compress else ".pkl"
        filename = f"{name}_v{version}{extension}"
        file_path = self.base_path / filename
        
        try:
            # 데이터 해시 생성 (중복 확인용)
            data_hash = self._generate_data_hash(df)
            
            # 기존 동일 데이터 확인
            existing_file = self._find_existing_data(name, data_hash)
            if existing_file:
                self.logger.info(f"동일한 데이터가 이미 존재: {existing_file}")
                return str(existing_file)
            
            # 저장 실행
            if compress:
                with gzip.open(file_path, 'wb') as f:
                    pickle.dump(df, f, protocol=pickle.HIGHEST_PROTOCOL)
            else:
                with open(file_path, 'wb') as f:
                    pickle.dump(df, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            # 메타데이터 업데이트
            self._update_metadata(name, version, file_path, df, data_hash, description)
            
            # 파일 크기 정보
            file_size = file_path.stat().st_size / (1024 * 1024)  # MB
            self.logger.info(f"DataFrame 저장 완료: {file_path} ({file_size:.2f} MB)")
            
            return str(file_path)
            
        except Exception as e:
            self.logger.error(f"DataFrame 저장 실패: {e}")
            raise
    
    def load_dataframe(self, name: str, version: str = None) -> pd.DataFrame:
        """
        pickle 파일에서 DataFrame 로드
        
        Args:
            name: 파일명
            version: 버전 (없으면 최신 버전)
            
        Returns:
            pd.DataFrame: 로드된 DataFrame
        """
        try:
            # 파일 경로 찾기
            file_path = self._find_file(name, version)
            
            if not file_path:
                raise FileNotFoundError(f"파일을 찾을 수 없습니다: {name} (version: {version})")
            
            # 로드 실행
            if file_path.suffix == '.gz':
                with gzip.open(file_path, 'rb') as f:
                    df = pickle.load(f)
            else:
                with open(file_path, 'rb') as f:
                    df = pickle.load(f)
            
            self.logger.info(f"DataFrame 로드 완료: {file_path} ({len(df):,}행 x {len(df.columns)}열)")
            
            return df
            
        except Exception as e:
            self.logger.error(f"DataFrame 로드 실패: {e}")
            raise
    
    def list_files(self, name: str = None) -> pd.DataFrame:
        """
        저장된 파일 목록 조회
        
        Args:
            name: 특정 파일명으로 필터링
            
        Returns:
            pd.DataFrame: 파일 목록과 메타데이터
        """
        if not self.metadata:
            return pd.DataFrame()
        
        files_data = []
        
        for file_info in self.metadata.values():
            if name is None or file_info['name'] == name:
                files_data.append({
                    'name': file_info['name'],
                    'version': file_info['version'],
                    'file_path': file_info['file_path'],
                    'rows': file_info['rows'],
                    'columns': file_info['columns'],
                    'size_mb': file_info['size_mb'],
                    'created_at': file_info['created_at'],
                    'description': file_info.get('description', '')
                })
        
        return pd.DataFrame(files_data)
    
    def list_pickle_files(self, name: str = None) -> list:
        """
        저장된 pickle 파일 목록을 리스트로 반환
        
        Args:
            name: 특정 파일명으로 필터링
            
        Returns:
            list: 파일 정보 딕셔너리 리스트
        """
        if not self.metadata:
            return []
        
        files_list = []
        
        for file_info in self.metadata.values():
            if name is None or file_info['name'] == name:
                files_list.append({
                    'name': file_info['name'],
                    'version': file_info['version'],
                    'file_path': file_info['file_path'],
                    'rows': file_info.get('rows', 0),
                    'columns': file_info.get('columns', 0),
                    'size_mb': file_info.get('size_mb', 0),
                    'created_at': file_info.get('created_at', ''),
                    'description': file_info.get('description', '')
                })
        
        # 최신 순으로 정렬
        files_list.sort(key=lambda x: x['created_at'], reverse=True)
        
        return files_list
    
    def delete_file(self, name: str, version: str = None) -> bool:
        """
        파일 삭제
        
        Args:
            name: 파일명
            version: 버전 (없으면 최신 버전)
            
        Returns:
            bool: 삭제 성공 여부
        """
        try:
            file_path = self._find_file(name, version)
            
            if not file_path:
                self.logger.warning(f"삭제할 파일을 찾을 수 없습니다: {name} (version: {version})")
                return False
            
            # 파일 삭제
            file_path.unlink()
            
            # 메타데이터에서 제거
            file_key = str(file_path)
            if file_key in self.metadata:
                del self.metadata[file_key]
                self._save_metadata()
            
            self.logger.info(f"파일 삭제 완료: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"파일 삭제 실패: {e}")
            return False
    
    def cleanup_old_versions(self, name: str, keep_versions: int = 3) -> int:
        """
        오래된 버전 파일 정리
        
        Args:
            name: 파일명
            keep_versions: 유지할 버전 수
            
        Returns:
            int: 삭제된 파일 수
        """
        file_list = self.list_files(name)
        
        if len(file_list) <= keep_versions:
            return 0
        
        # 최신 버전 기준으로 정렬
        file_list = file_list.sort_values('created_at', ascending=False)
        
        # 삭제할 파일 목록
        files_to_delete = file_list.iloc[keep_versions:]
        
        deleted_count = 0
        for _, file_info in files_to_delete.iterrows():
            if self.delete_file(file_info['name'], file_info['version']):
                deleted_count += 1
        
        self.logger.info(f"오래된 버전 정리 완료: {deleted_count}개 파일 삭제")
        return deleted_count
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 정보"""
        total_files = len(self.metadata)
        total_size = sum(info['size_mb'] for info in self.metadata.values())
        
        # 파일명별 통계
        name_stats = {}
        for info in self.metadata.values():
            name = info['name']
            if name not in name_stats:
                name_stats[name] = {'count': 0, 'size_mb': 0}
            name_stats[name]['count'] += 1
            name_stats[name]['size_mb'] += info['size_mb']
        
        return {
            'total_files': total_files,
            'total_size_mb': total_size,
            'cache_path': str(self.base_path),
            'name_stats': name_stats
        }
    
    def _generate_data_hash(self, df: pd.DataFrame) -> str:
        """데이터 해시 생성"""
        # DataFrame을 문자열로 변환하여 해시 생성
        data_str = df.to_string()
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def _find_existing_data(self, name: str, data_hash: str) -> Optional[Path]:
        """동일한 데이터가 이미 존재하는지 확인"""
        for info in self.metadata.values():
            if info['name'] == name and info.get('data_hash') == data_hash:
                return Path(info['file_path'])
        return None
    
    def _find_file(self, name: str, version: str = None) -> Optional[Path]:
        """파일 경로 찾기"""
        matching_files = []
        
        for info in self.metadata.values():
            if info['name'] == name:
                if version is None or info['version'] == version:
                    matching_files.append((info['created_at'], Path(info['file_path'])))
        
        if not matching_files:
            return None
        
        # 버전이 지정되지 않은 경우 최신 버전 반환
        if version is None:
            matching_files.sort(key=lambda x: x[0], reverse=True)
        
        return matching_files[0][1]
    
    def _load_metadata(self) -> Dict[str, Any]:
        """메타데이터 로드"""
        if not self.metadata_file.exists():
            return {}
        
        try:
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.warning(f"메타데이터 로드 실패: {e}")
            return {}
    
    def _save_metadata(self):
        """메타데이터 저장"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"메타데이터 저장 실패: {e}")
    
    def _update_metadata(self, name: str, version: str, file_path: Path, 
                        df: pd.DataFrame, data_hash: str, description: str = None):
        """메타데이터 업데이트"""
        file_key = str(file_path)
        
        self.metadata[file_key] = {
            'name': name,
            'version': version,
            'file_path': str(file_path),
            'rows': len(df),
            'columns': len(df.columns),
            'size_mb': file_path.stat().st_size / (1024 * 1024),
            'created_at': datetime.now().isoformat(),
            'data_hash': data_hash,
            'description': description or '',
            'dtypes': {str(k): str(v) for k, v in df.dtypes.to_dict().items()}
        }
        
        self._save_metadata()
    
    def export_data(self, name: str, version: str = None, 
                   export_format: str = 'csv', output_path: str = None) -> str:
        """
        pickle 데이터를 다른 형식으로 내보내기
        
        Args:
            name: 파일명
            version: 버전
            export_format: 내보낼 형식 ('csv', 'excel', 'json')
            output_path: 출력 경로
            
        Returns:
            str: 내보낸 파일 경로
        """
        df = self.load_dataframe(name, version)
        
        if output_path is None:
            output_path = self.base_path / f"{name}_v{version or 'latest'}.{export_format}"
        else:
            output_path = Path(output_path)
        
        try:
            if export_format == 'csv':
                df.to_csv(output_path, index=False, encoding='utf-8-sig')
            elif export_format == 'excel':
                df.to_excel(output_path, index=False)
            elif export_format == 'json':
                df.to_json(output_path, orient='records', force_ascii=False, indent=2)
            else:
                raise ValueError(f"지원하지 않는 형식: {export_format}")
            
            self.logger.info(f"데이터 내보내기 완료: {output_path}")
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"데이터 내보내기 실패: {e}")
            raise