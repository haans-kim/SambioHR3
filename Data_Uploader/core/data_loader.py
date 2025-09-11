#!/usr/bin/env python3
"""
독립적인 TagData 로드 시스템
Data_Uploader 전용 버전 - 루트 DB 사용
"""

import pandas as pd
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
import argparse
import time
from pathlib import Path
import sqlite3
import sys
import gzip
import pickle

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ExcelLoader:
    """Excel 파일 로더"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def load_excel_file(self, file_path: Path, auto_merge_sheets: bool = True) -> pd.DataFrame:
        """Excel 파일 로드 및 시트 자동 병합"""
        self.logger.info(f"파일 크기: {file_path.stat().st_size / (1024*1024):.2f} MB")
        
        try:
            # Excel 파일의 시트 목록 확인
            sheet_names = pd.ExcelFile(file_path).sheet_names
            self.logger.info(f"시트 목록: {sheet_names}")
            
            if len(sheet_names) == 1:
                # 단일 시트
                self.logger.info("단일 시트 모드")
                return pd.read_excel(file_path, sheet_name=0)
            
            elif auto_merge_sheets:
                # 다중 시트 자동 병합
                self.logger.info("여러 시트 감지 - 자동 병합 모드")
                return self._merge_multiple_sheets(file_path, sheet_names)
            
            else:
                # 첫 번째 시트만 로드
                return pd.read_excel(file_path, sheet_name=0)
                
        except Exception as e:
            self.logger.error(f"Excel 파일 로드 실패: {e}")
            raise
    
    def _merge_multiple_sheets(self, file_path: Path, sheet_names: List[str]) -> pd.DataFrame:
        """여러 시트를 하나로 병합"""
        self.logger.info(f"{len(sheet_names)}개의 시트를 병합합니다...")
        self.logger.info(f"병합할 시트: {sheet_names}")
        
        dfs = []
        original_total = 0
        
        for i, sheet_name in enumerate(sheet_names):
            self.logger.info(f"[{i+1}/{len(sheet_names)}] {sheet_name} 시트 로딩 중...")
            
            # 대용량 파일 처리를 위한 청크 읽기
            try:
                df = self._load_large_excel_sheet(file_path, sheet_name)
                dfs.append(df)
                original_total += len(df)
                self.logger.info(f"{sheet_name}: {len(df):,}행 로드됨")
                
            except Exception as e:
                self.logger.error(f"{sheet_name} 시트 로드 실패: {e}")
                continue
        
        if not dfs:
            raise ValueError("로드 가능한 시트가 없습니다")
        
        # 시트 병합
        self.logger.info("시트 병합 중...")
        combined_df = pd.concat(dfs, ignore_index=True)
        
        self.logger.info(f"병합 완료: 총 {len(combined_df):,}행 (원본 {original_total:,}행)")
        
        return combined_df
    
    def _load_large_excel_sheet(self, file_path: Path, sheet_name: str) -> pd.DataFrame:
        """대용량 Excel 시트 로드"""
        self.logger.info("대용량 Excel 파일 로딩 시작...")
        
        try:
            self.logger.info("파일 정보 확인 중...")
            self.logger.info("데이터 로딩 중... (이 작업은 시간이 걸릴 수 있습니다)")
            
            # 메모리 효율적 로딩
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            self.logger.info("데이터 타입 최적화 중...")
            df = self._optimize_datatypes(df)
            
            return df
            
        except Exception as e:
            self.logger.error(f"대용량 파일 로드 실패: {e}")
            raise
    
    def _optimize_datatypes(self, df: pd.DataFrame) -> pd.DataFrame:
        """데이터 타입 최적화로 메모리 사용량 감소"""
        for col in df.columns:
            if df[col].dtype == 'object':
                try:
                    # 숫자로 변환 가능한지 시도
                    df[col] = pd.to_numeric(df[col], errors='ignore')
                except:
                    pass
            elif df[col].dtype == 'int64':
                # int64를 int32로 다운캐스팅 (가능한 경우)
                if df[col].min() >= -2147483648 and df[col].max() <= 2147483647:
                    df[col] = df[col].astype('int32')
        
        return df


class PickleManager:
    """Pickle 파일 관리자"""
    
    def __init__(self, base_path: str = "data"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)
    
    def save_dataframe(self, df: pd.DataFrame, name: str, version: str = None, description: str = None) -> Path:
        """DataFrame을 압축된 pickle 파일로 저장"""
        if version is None:
            version = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        filename = f"{name}_v{version}.pkl.gz"
        file_path = self.base_path / filename
        
        try:
            with gzip.open(file_path, 'wb') as f:
                pickle.dump(df, f)
            
            size_mb = file_path.stat().st_size / (1024 * 1024)
            self.logger.info(f"DataFrame 저장 완료: {file_path} ({size_mb:.2f} MB)")
            
            return file_path
            
        except Exception as e:
            self.logger.error(f"DataFrame 저장 실패: {e}")
            raise
    
    def load_dataframe(self, name: str, version: str = None) -> Optional[pd.DataFrame]:
        """압축된 pickle 파일에서 DataFrame 로드"""
        try:
            if version:
                filename = f"{name}_v{version}.pkl.gz"
                file_path = self.base_path / filename
            else:
                # 가장 최신 버전 찾기
                pattern = f"{name}_v*.pkl.gz"
                files = list(self.base_path.glob(pattern))
                if not files:
                    self.logger.warning(f"{name}에 대한 pickle 파일을 찾을 수 없습니다")
                    return None
                
                # 가장 최신 파일 선택
                file_path = max(files, key=lambda x: x.stat().st_mtime)
            
            if not file_path.exists():
                self.logger.warning(f"파일이 존재하지 않습니다: {file_path}")
                return None
            
            with gzip.open(file_path, 'rb') as f:
                df = pickle.load(f)
            
            self.logger.info(f"DataFrame 로드 완료: {file_path} ({len(df):,}행)")
            return df
            
        except Exception as e:
            self.logger.error(f"DataFrame 로드 실패: {e}")
            return None
    
    def list_pickle_files(self, name: str = None) -> List[Dict[str, Any]]:
        """pickle 파일 목록 조회"""
        pattern = f"{name}_v*.pkl.gz" if name else "*.pkl.gz"
        files = []
        
        for file_path in self.base_path.glob(pattern):
            try:
                stat = file_path.stat()
                file_info = {
                    'name': file_path.stem.split('_v')[0],
                    'version': file_path.stem.split('_v')[1].replace('.pkl', ''),
                    'file_path': file_path,
                    'size_mb': stat.st_size / (1024 * 1024),
                    'created_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'rows': self._get_row_count(file_path)
                }
                files.append(file_info)
            except Exception as e:
                self.logger.warning(f"파일 정보 수집 실패: {file_path} - {e}")
        
        # 생성 시간 순 정렬 (최신 먼저)
        files.sort(key=lambda x: x['created_at'], reverse=True)
        return files
    
    def _get_row_count(self, file_path: Path) -> int:
        """파일을 열지 않고 행 수 추정 (빠른 조회용)"""
        try:
            with gzip.open(file_path, 'rb') as f:
                df = pickle.load(f)
                return len(df)
        except:
            return 0


class DatabaseManager:
    """단순화된 데이터베이스 관리자"""
    
    def __init__(self, db_path: str = "sambio_human.db"):
        self.db_path = Path(db_path)
        self.logger = logging.getLogger(__name__)
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        """데이터베이스 파일 존재 확인 및 테이블 생성"""
        if not self.db_path.exists():
            self._create_tables()
    
    def _create_tables(self):
        """필요한 테이블 생성"""
        with sqlite3.connect(self.db_path) as conn:
            # tag_data 테이블 생성
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tag_data (
                    사번 TEXT,
                    성명 TEXT,
                    TAG_TYPE TEXT,
                    TAG_CD TEXT,
                    ENTE_DT INTEGER,
                    ENTE_TM TEXT,
                    TAG_NM TEXT,
                    ACL_ZONE TEXT,
                    PART TEXT,
                    IO_TXN_CL TEXT,
                    CONTROL_DEV_NO TEXT,
                    LOC_CD TEXT,
                    LOC_NM TEXT,
                    CONTROL_DEV_GRP_NM TEXT,
                    CONTROL_DEV_NM TEXT
                )
            """)
            conn.commit()
    
    def dataframe_to_table(self, df: pd.DataFrame, table_name: str, if_exists: str = 'replace', batch_size: int = 5000):
        """DataFrame을 데이터베이스 테이블에 저장 (배치 처리)"""
        total_rows = len(df)
        self.logger.info(f"데이터베이스 삽입 시작: {total_rows:,}행")
        
        start_time = time.time()
        processed_rows = 0
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                if if_exists == 'replace':
                    # 기존 데이터 삭제
                    conn.execute(f"DELETE FROM {table_name}")
                    conn.commit()
                
                # 배치 단위로 삽입
                for start_idx in range(0, total_rows, batch_size):
                    end_idx = min(start_idx + batch_size, total_rows)
                    batch_df = df.iloc[start_idx:end_idx]
                    
                    batch_df.to_sql(table_name, conn, if_exists='append', index=False)
                    processed_rows += len(batch_df)
                    
                    # 진행률 표시 (10% 단위)
                    progress = (processed_rows / total_rows) * 100
                    if processed_rows % (batch_size * 4) == 0 or end_idx == total_rows:
                        elapsed = time.time() - start_time
                        self.logger.info(f"진행률: {progress:.1f}% ({processed_rows:,}/{total_rows:,}행, {elapsed:.1f}초)")
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"데이터베이스 삽입 실패: {e}")
            raise
        
        elapsed = time.time() - start_time
        self.logger.info(f"DataFrame 삽입 완료: {processed_rows:,}행 → {table_name}, 소요시간: {elapsed:.2f}초")
    
    def get_table_stats(self, table_name: str) -> Dict[str, Any]:
        """테이블 통계 정보 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 총 레코드 수
                total_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                
                # 날짜 범위 (ENTE_DT 컬럼이 있는 경우)
                try:
                    date_stats = conn.execute(f"""
                        SELECT MIN(ENTE_DT) as min_date, MAX(ENTE_DT) as max_date 
                        FROM {table_name}
                    """).fetchone()
                    min_date, max_date = date_stats
                except:
                    min_date, max_date = None, None
                
                # 월별 분포 (ENTE_DT 컬럼이 있는 경우)
                monthly_dist = {}
                if min_date and max_date:
                    try:
                        monthly_data = conn.execute(f"""
                            SELECT SUBSTR(CAST(ENTE_DT AS TEXT), 1, 6) as year_month, COUNT(*) as count
                            FROM {table_name}
                            GROUP BY SUBSTR(CAST(ENTE_DT AS TEXT), 1, 6)
                            ORDER BY year_month
                        """).fetchall()
                        monthly_dist = {ym: count for ym, count in monthly_data}
                    except:
                        pass
                
                return {
                    'total_records': total_count,
                    'min_date': min_date,
                    'max_date': max_date,
                    'monthly_distribution': monthly_dist
                }
                
        except Exception as e:
            self.logger.error(f"테이블 통계 조회 실패: {e}")
            return {}


class TagDataLoader:
    """TagData 로드를 위한 체계적인 클래스"""
    
    def __init__(self, db_path: str = "sambio_human.db", pickle_path: str = "data"):
        self.db_manager = DatabaseManager(db_path)
        self.pickle_manager = PickleManager(pickle_path)
        self.excel_loader = ExcelLoader()
        self.logger = logging.getLogger(__name__)
    
    def show_status(self):
        """현재 시스템 상태 표시"""
        print("=" * 60)
        print("🗄️  SAMBIO TagData 로드 시스템 현황")
        print("=" * 60)
        print()
        
        # Excel 파일 조회
        raw_path = Path("raw")
        if raw_path.exists():
            excel_files = list(raw_path.glob("*.xlsx"))
            if excel_files:
                print("📁 사용 가능한 Excel 파일:")
                for i, file_path in enumerate(excel_files[:10], 1):
                    stat = file_path.stat()
                    size_mb = stat.st_size / (1024 * 1024)
                    created = datetime.fromtimestamp(stat.st_mtime)
                    print(f"  {i}. {file_path.name}")
                    print(f"     크기: {size_mb:.2f}MB, 생성일: {created.strftime('%Y-%m-%d %H:%M')}")
                    print(f"     경로: {file_path}")
                print()
        
        # Pickle 파일 조회
        pickle_files = self.pickle_manager.list_pickle_files("tag_data")
        if pickle_files:
            print("📦 사용 가능한 Pickle 파일:")
            for i, file_info in enumerate(pickle_files[:5], 1):
                print(f"  {i}. {file_info['name']}_v{file_info['version']}.pkl.gz")
                print(f"     크기: {file_info['size_mb']:.2f}MB, 생성일: {file_info['created_at'][:10]}")
                print(f"     데이터: {file_info['rows']:,}건")
                if file_info['rows'] > 0:
                    # 데이터 분석
                    df = self.pickle_manager.load_dataframe(file_info['name'], file_info['version'])
                    if df is not None and 'ENTE_DT' in df.columns:
                        min_date = df['ENTE_DT'].min()
                        max_date = df['ENTE_DT'].max()
                        monthly_counts = df.groupby(df['ENTE_DT'].astype(str).str[:6])['ENTE_DT'].count()
                        print(f"     기간: {min_date}~{max_date}")
                        print(f"     월별: {dict(monthly_counts)}")
                print()
        
        # 데이터베이스 상태
        db_stats = self.db_manager.get_table_stats("tag_data")
        if db_stats.get('total_records', 0) > 0:
            print("🗃️  현재 데이터베이스 상태:")
            print(f"  총 레코드: {db_stats['total_records']:,}건")
            if db_stats.get('monthly_distribution'):
                print("  월별 분포:")
                for ym, count in db_stats['monthly_distribution'].items():
                    year, month = ym[:4], ym[4:]
                    min_date = db_stats.get('min_date', 0)
                    max_date = db_stats.get('max_date', 0)
                    if str(min_date).startswith(ym):
                        date_range = f"({str(min_date)[:8]}~{str(max_date)[:8]})"
                    else:
                        date_range = ""
                    print(f"    {ym}: {count:,}건 ({year}년 {month}월) {date_range}")
        else:
            print("🗃️  데이터베이스: 데이터 없음")
        
        print("=" * 60)
    
    def load_excel_to_db(self, excel_path: Path, save_pickle: bool = True, replace_existing: bool = False) -> bool:
        """Excel 파일을 직접 DB로 로드 (3단계 프로세스)"""
        self.logger.info(f"Excel 파일 통합 로드 시작: {excel_path}")
        
        try:
            # Step 1: Excel 파일 로딩
            self.logger.info("📊 Step 1/3: Excel 파일 로딩 중...")
            raw_data = self.excel_loader.load_excel_file(excel_path, auto_merge_sheets=True)
            self.logger.info(f"Excel 로드 완료: {len(raw_data):,}행 x {len(raw_data.columns):,}열")
            
            # Step 2: Pickle 파일 저장 (옵션)
            if save_pickle:
                self.logger.info("💾 Step 2/3: Pickle 파일 저장 중...")
                version = datetime.now().strftime('%Y%m%d_%H%M%S')
                self.pickle_manager.save_dataframe(
                    raw_data,
                    name="tag_data",
                    version=version,
                    description=f"Excel import from {excel_path.name}"
                )
                self.logger.info(f"Pickle 저장 완료: tag_data_v{version}.pkl.gz")
            
            # Step 3: 데이터베이스 저장
            self.logger.info("🗄️ Step 3/3: 데이터베이스 저장 중...")
            
            # 날짜 범위 확인
            if 'ENTE_DT' in raw_data.columns:
                min_date = raw_data['ENTE_DT'].min()
                max_date = raw_data['ENTE_DT'].max()
                self.logger.info(f"데이터 날짜 범위: {min_date} ~ {max_date}")
            
            # DB에 저장
            if_exists = 'replace' if replace_existing else 'append'
            self.db_manager.dataframe_to_table(raw_data, "tag_data", if_exists=if_exists)
            
            self.logger.info("로드 완료: 모든 단계 성공")
            return True
            
        except Exception as e:
            self.logger.error(f"Excel 로드 실패: {e}")
            return False
    
    def load_tag_data(self, pickle_path: Path, replace_existing: bool = False) -> bool:
        """Pickle 파일에서 TagData 로드"""
        self.logger.info(f"TagData 로드 시작: {pickle_path}")
        
        try:
            # 파일명에서 name 추출
            name = pickle_path.stem.split('_v')[0]
            version = pickle_path.stem.split('_v')[1].replace('.pkl', '')
            
            # Pickle 파일 로드
            df = self.pickle_manager.load_dataframe(name, version)
            if df is None:
                self.logger.error("데이터 로드 실패")
                return False
            
            # 데이터 정보 표시
            date_range = {}
            if 'ENTE_DT' in df.columns:
                date_range = {
                    'min_date': df['ENTE_DT'].min(),
                    'max_date': df['ENTE_DT'].max()
                }
            
            self.logger.info(f"데이터 정보: {len(df):,}건, 날짜범위: {date_range}")
            
            # 데이터베이스에 삽입
            self.logger.info("데이터베이스에 삽입 중...")
            if_exists = 'replace' if replace_existing else 'append'
            self.db_manager.dataframe_to_table(df, "tag_data", if_exists=if_exists)
            
            self.logger.info(f"로드 완료: {len(df):,}건 삽입")
            return True
            
        except Exception as e:
            self.logger.error(f"TagData 로드 실패: {e}")
            return False


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="TagData 로드 시스템")
    parser.add_argument("--status", action="store_true", help="현재 상태 표시")
    parser.add_argument("--load-latest", action="store_true", help="최신 pickle 파일 로드")
    parser.add_argument("--load-file", help="특정 pickle 파일 로드")
    parser.add_argument("--load-excel", help="Excel 파일에서 로드")
    parser.add_argument("--replace", action="store_true", help="기존 데이터 교체")
    parser.add_argument("--no-pickle", action="store_true", help="Pickle 저장 건너뛰기")
    
    args = parser.parse_args()
    
    # 현재 디렉토리 기준으로 경로 설정
    current_dir = Path(__file__).parent.parent
    db_path = current_dir / "sambio_human.db"  # 루트에 DB 생성
    pickle_path = current_dir / "data"  # data 폴더에 pickle 저장
    
    loader = TagDataLoader(str(db_path), str(pickle_path))
    
    if args.status:
        loader.show_status()
        return 0
    
    if args.load_latest:
        files = loader.pickle_manager.list_pickle_files("tag_data")
        if files:
            latest_file = files[0]['file_path']
            logger.info(f"최신 파일 로드: {latest_file}")
            success = loader.load_tag_data(latest_file, replace_existing=args.replace)
            return 0 if success else 1
        else:
            logger.error("사용 가능한 pickle 파일이 없습니다")
            return 1
    
    if args.load_file:
        file_path = pickle_path / args.load_file
        if file_path.exists():
            success = loader.load_tag_data(file_path, replace_existing=args.replace)
            return 0 if success else 1
        else:
            logger.error(f"파일을 찾을 수 없습니다: {file_path}")
            return 1
    
    if args.load_excel:
        excel_path = Path(args.load_excel)
        if not excel_path.exists():
            # raw 폴더에서도 찾아보기
            excel_path = current_dir / "raw" / excel_path.name
        
        if excel_path.exists():
            save_pickle = not args.no_pickle
            success = loader.load_excel_to_db(
                excel_path, 
                save_pickle=save_pickle,
                replace_existing=args.replace
            )
            return 0 if success else 1
        else:
            logger.error(f"Excel 파일을 찾을 수 없습니다: {args.load_excel}")
            return 1
    
    # 기본: 상태 표시
    loader.show_status()
    return 0

if __name__ == "__main__":
    exit(main())