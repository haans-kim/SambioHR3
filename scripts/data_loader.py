#!/usr/bin/env python3
"""
체계적인 TagData 로드 시스템
2~5월 데이터를 포함한 모든 월별 데이터를 효율적으로 로드
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
from src.database import get_database_manager
from src.data_processing import PickleManager
from src.data_processing.excel_loader import ExcelLoader
from src.data_processing.data_transformer import DataTransformer
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
import argparse
import time

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TagDataLoader:
    """TagData 로드를 위한 체계적인 클래스"""
    
    def __init__(self):
        self.db_manager = get_database_manager()
        self.pickle_manager = PickleManager()
        self.excel_loader = ExcelLoader()
        self.data_transformer = DataTransformer()
        self.logger = logging.getLogger(__name__)
    
    def get_available_tag_data_files(self) -> List[Dict[str, Any]]:
        """사용 가능한 tag_data pickle 파일들 조회"""
        files = []
        for file_path in self.pickle_manager.base_path.glob('tag_data_*.pkl.gz'):
            try:
                # 파일명에서 버전 정보 추출
                version = file_path.stem.split('_v')[1].replace('.pkl', '')
                
                # 파일 정보 수집
                file_info = {
                    'file_path': file_path,
                    'version': version,
                    'file_name': file_path.name,
                    'created_date': datetime.fromtimestamp(file_path.stat().st_mtime),
                    'size_mb': file_path.stat().st_size / (1024 * 1024)
                }
                files.append(file_info)
            except Exception as e:
                self.logger.warning(f"파일 정보 수집 실패: {file_path} - {e}")
        
        # 생성 날짜 순으로 정렬
        files.sort(key=lambda x: x['created_date'], reverse=True)
        return files
    
    def analyze_pickle_data(self, file_path: Path) -> Dict[str, Any]:
        """Pickle 파일의 데이터 내용 분석"""
        try:
            # Pickle 파일 로드 (파일명 기반)
            file_name = file_path.stem.split('_v')[0]  # 'tag_data'
            data = self.pickle_manager.load_dataframe(file_name)
            
            analysis = {
                'total_records': len(data),
                'columns': list(data.columns),
                'date_range': None,
                'monthly_distribution': None
            }
            
            # 날짜 범위 분석 (ENTE_DT 컬럼이 있는 경우)
            if 'ENTE_DT' in data.columns:
                date_range = data['ENTE_DT'].agg(['min', 'max'])
                analysis['date_range'] = {
                    'min_date': int(date_range['min']),
                    'max_date': int(date_range['max'])
                }
                
                # 월별 분포
                monthly_counts = data.groupby(
                    data['ENTE_DT'].astype(str).str[:6]
                )['ENTE_DT'].count()
                analysis['monthly_distribution'] = monthly_counts.to_dict()
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"데이터 분석 실패: {file_path} - {e}")
            return None
    
    def check_existing_data(self, year_month: str) -> Dict[str, Any]:
        """DB에 특정 년월 데이터가 이미 있는지 확인"""
        try:
            start_date = int(f"{year_month}01")
            end_date = int(f"{year_month}31")
            
            result = self.db_manager.execute_query(
                "SELECT COUNT(*) as count FROM tag_data WHERE ENTE_DT >= :start_date AND ENTE_DT <= :end_date",
                {'start_date': start_date, 'end_date': end_date}
            )
            
            count = result[0]['count'] if result else 0
            
            if count > 0:
                # 날짜 범위 확인
                date_result = self.db_manager.execute_query(
                    "SELECT MIN(ENTE_DT) as min_date, MAX(ENTE_DT) as max_date FROM tag_data WHERE ENTE_DT >= :start_date AND ENTE_DT <= :end_date",
                    {'start_date': start_date, 'end_date': end_date}
                )
                
                return {
                    'exists': True,
                    'count': count,
                    'min_date': date_result[0]['min_date'] if date_result else None,
                    'max_date': date_result[0]['max_date'] if date_result else None
                }
            else:
                return {'exists': False, 'count': 0}
                
        except Exception as e:
            self.logger.error(f"기존 데이터 확인 실패: {e}")
            return {'exists': False, 'count': 0}
    
    def load_tag_data(self, file_path: Path, replace_existing: bool = False) -> bool:
        """TagData를 데이터베이스에 로드"""
        try:
            self.logger.info(f"TagData 로드 시작: {file_path}")
            
            # 데이터 분석
            analysis = self.analyze_pickle_data(file_path)
            if not analysis:
                self.logger.error("데이터 분석 실패")
                return False
            
            self.logger.info(f"데이터 정보: {analysis['total_records']:,}건, "
                           f"날짜범위: {analysis['date_range']}")
            
            # 데이터 로드
            file_name = file_path.stem.split('_v')[0]
            data = self.pickle_manager.load_dataframe(file_name)
            
            # 월별로 기존 데이터 확인 및 처리
            if analysis['monthly_distribution']:
                for year_month, count in analysis['monthly_distribution'].items():
                    existing = self.check_existing_data(year_month)
                    
                    if existing['exists']:
                        if replace_existing:
                            self.logger.info(f"{year_month} 기존 데이터 삭제 중... ({existing['count']:,}건)")
                            start_date = int(f"{year_month}01")
                            end_date = int(f"{year_month}31")
                            self.db_manager.execute_query(
                                "DELETE FROM tag_data WHERE ENTE_DT >= :start_date AND ENTE_DT <= :end_date",
                                {'start_date': start_date, 'end_date': end_date}
                            )
                        else:
                            self.logger.warning(f"{year_month} 데이터가 이미 존재합니다 ({existing['count']:,}건). "
                                              "덮어쓰려면 --replace 옵션을 사용하세요.")
                            continue
            
            # 기존 DB 스키마와 호환되도록 원본 컬럼만 필터링
            original_columns = [
                'ENTE_DT', 'DAY_GB', 'DAY_NM', 'NAME', '사번', 'CENTER', 'BU', 'TEAM', 
                'GROUP_A', 'PART', '출입시각', 'DR_NO', 'DR_NM', 'DR_GB', 'INOUT_GB'
            ]
            db_data = data[original_columns].copy()
            
            # 데이터베이스에 삽입
            self.logger.info("데이터베이스에 삽입 중...")
            inserted_count = self.db_manager.dataframe_to_table(
                db_data, 'tag_data', if_exists='append', batch_size=5000
            )
            
            self.logger.info(f"로드 완료: {inserted_count:,}건 삽입")
            return True
            
        except Exception as e:
            self.logger.error(f"데이터 로드 실패: {e}", exc_info=True)
            return False
    
    def load_excel_to_db(self, excel_path: Path, save_pickle: bool = True, 
                        replace_existing: bool = False) -> bool:
        """Excel 파일을 직접 데이터베이스에 로드 (Excel → Pickle → DB 통합 프로세스)"""
        try:
            start_time = time.time()
            self.logger.info(f"Excel 파일 통합 로드 시작: {excel_path}")
            
            # 1. Excel 파일 존재 확인
            if not excel_path.exists():
                self.logger.error(f"Excel 파일을 찾을 수 없습니다: {excel_path}")
                return False
            
            # 2. Excel 파일 로드
            self.logger.info("📊 Step 1/3: Excel 파일 로딩 중...")
            raw_data = self.excel_loader.load_excel_file(excel_path)
            self.logger.info(f"Excel 로드 완료: {len(raw_data):,}행 x {len(raw_data.columns)}열")
            
            # 3. Pickle 파일 저장 (옵션)
            if save_pickle:
                self.logger.info("💾 Step 2/3: Pickle 파일 저장 중...")
                version = datetime.now().strftime("%Y%m%d_%H%M%S")
                pickle_path = self.pickle_manager.save_dataframe(
                    raw_data, 
                    'tag_data', 
                    version=version,
                    description=f"From {excel_path.name}"
                )
                self.logger.info(f"Pickle 저장 완료: {pickle_path}")
            
            # 4. 데이터베이스에 로드
            self.logger.info("🗄️ Step 3/3: 데이터베이스 저장 중...")
            
            # 날짜 범위 분석
            if 'ENTE_DT' in raw_data.columns:
                date_range = raw_data['ENTE_DT'].agg(['min', 'max'])
                min_date, max_date = int(date_range['min']), int(date_range['max'])
                self.logger.info(f"데이터 날짜 범위: {min_date} ~ {max_date}")
                
                # 월별 분포 확인
                monthly_counts = raw_data.groupby(
                    raw_data['ENTE_DT'].astype(str).str[:6]
                )['ENTE_DT'].count()
                
                # 기존 데이터 확인 및 처리
                for year_month, count in monthly_counts.items():
                    existing = self.check_existing_data(year_month)
                    
                    if existing['exists']:
                        if replace_existing:
                            self.logger.info(f"{year_month} 기존 데이터 삭제 중... ({existing['count']:,}건)")
                            start_date = int(f"{year_month}01")
                            end_date = int(f"{year_month}31")
                            self.db_manager.execute_query(
                                "DELETE FROM tag_data WHERE ENTE_DT >= :start_date AND ENTE_DT <= :end_date",
                                {'start_date': start_date, 'end_date': end_date}
                            )
                        else:
                            self.logger.warning(f"{year_month} 데이터가 이미 존재합니다 ({existing['count']:,}건). "
                                              "덮어쓰려면 --replace 옵션을 사용하세요.")
                            return False
            
            # 데이터베이스에 삽입 (원본 데이터 그대로)
            inserted_count = self.db_manager.dataframe_to_table(
                raw_data, 'tag_data', if_exists='append', batch_size=5000
            )
            
            total_time = time.time() - start_time
            self.logger.info(f"🎉 Excel → DB 통합 로드 완료!")
            self.logger.info(f"   📁 파일: {excel_path.name}")
            self.logger.info(f"   📊 레코드: {inserted_count:,}건")
            self.logger.info(f"   ⏱️ 소요시간: {total_time:.2f}초")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Excel 통합 로드 실패: {e}", exc_info=True)
            return False
    
    def show_status(self):
        """현재 시스템 상태 표시"""
        print("\n" + "="*60)
        print("🗄️  SAMBIO TagData 로드 시스템 현황")
        print("="*60)
        
        # 1. 사용 가능한 pickle 파일들
        # 1. Excel 파일들 (data/raw 폴더)
        print("\n📁 사용 가능한 Excel 파일:")
        raw_data_path = Path("data/raw")
        if raw_data_path.exists():
            excel_files = list(raw_data_path.glob("*.xlsx")) + list(raw_data_path.glob("*.xls"))
            if excel_files:
                for i, excel_file in enumerate(excel_files, 1):
                    file_size = excel_file.stat().st_size / (1024 * 1024)
                    created_date = datetime.fromtimestamp(excel_file.stat().st_mtime)
                    print(f"  {i}. {excel_file.name}")
                    print(f"     크기: {file_size:.2f}MB, 생성일: {created_date.strftime('%Y-%m-%d %H:%M')}")
                    print(f"     경로: {excel_file}")
                    print()
            else:
                print("  Excel 파일이 없습니다.")
        else:
            print("  data/raw 폴더가 없습니다.")
        
        print("\n📦 사용 가능한 Pickle 파일:")
        files = self.get_available_tag_data_files()
        
        if files:
            for i, file_info in enumerate(files, 1):
                analysis = self.analyze_pickle_data(file_info['file_path'])
                print(f"  {i}. {file_info['file_name']}")
                print(f"     크기: {file_info['size_mb']:.2f}MB, 생성일: {file_info['created_date'].strftime('%Y-%m-%d %H:%M')}")
                
                if analysis and analysis['date_range']:
                    print(f"     데이터: {analysis['total_records']:,}건, "
                          f"기간: {analysis['date_range']['min_date']}~{analysis['date_range']['max_date']}")
                    if analysis['monthly_distribution']:
                        months = ", ".join([f"{month}({count:,}건)" 
                                          for month, count in analysis['monthly_distribution'].items()])
                        print(f"     월별: {months}")
                print()
        else:
            print("  Pickle 파일이 없습니다.")
        
        # 2. 현재 DB 상태
        print("🗃️  현재 데이터베이스 상태:")
        try:
            total_result = self.db_manager.execute_query("SELECT COUNT(*) as count FROM tag_data")
            total_count = total_result[0]['count'] if total_result else 0
            
            monthly_result = self.db_manager.execute_query("""
                SELECT 
                    SUBSTR(CAST(ENTE_DT AS TEXT), 1, 6) as year_month,
                    COUNT(*) as count,
                    MIN(ENTE_DT) as min_date,
                    MAX(ENTE_DT) as max_date
                FROM tag_data 
                GROUP BY SUBSTR(CAST(ENTE_DT AS TEXT), 1, 6)
                ORDER BY year_month
            """)
            
            print(f"  총 레코드: {total_count:,}건")
            print("  월별 분포:")
            for row in monthly_result:
                print(f"    {row['year_month']}: {row['count']:,}건 "
                      f"({row['min_date']}~{row['max_date']})")
            
        except Exception as e:
            print(f"  DB 상태 확인 실패: {e}")
        
        print("\n" + "="*60)

def main():
    parser = argparse.ArgumentParser(description='TagData 로드 시스템 (Excel → Pickle → DB 통합)')
    parser.add_argument('--status', action='store_true', help='현재 상태 표시')
    parser.add_argument('--load-latest', action='store_true', help='최신 pickle 파일 로드')
    parser.add_argument('--load-file', type=str, help='특정 pickle 파일 로드 (파일명)')
    parser.add_argument('--load-excel', type=str, help='Excel 파일 직접 로드 (경로)')
    parser.add_argument('--replace', action='store_true', help='기존 데이터 덮어쓰기')
    parser.add_argument('--no-pickle', action='store_true', help='Pickle 파일 저장 안 함 (Excel 로드 시)')
    
    args = parser.parse_args()
    
    loader = TagDataLoader()
    
    if args.status:
        loader.show_status()
        return 0
    
    if args.load_latest:
        files = loader.get_available_tag_data_files()
        if files:
            latest_file = files[0]['file_path']
            logger.info(f"최신 파일 로드: {latest_file}")
            success = loader.load_tag_data(latest_file, replace_existing=args.replace)
            return 0 if success else 1
        else:
            logger.error("사용 가능한 pickle 파일이 없습니다")
            return 1
    
    if args.load_file:
        file_path = Path("data/pickles") / args.load_file
        if file_path.exists():
            success = loader.load_tag_data(file_path, replace_existing=args.replace)
            return 0 if success else 1
        else:
            logger.error(f"파일을 찾을 수 없습니다: {file_path}")
            return 1
    
    if args.load_excel:
        excel_path = Path(args.load_excel)
        if not excel_path.exists():
            # data/raw 폴더에서도 찾아보기
            excel_path = Path("data/raw") / excel_path.name
        
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