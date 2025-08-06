"""
데이터베이스 매니저 모듈
연결 관리, 쿼리 실행, 트랜잭션 처리, 대용량 데이터 배치 처리를 담당합니다.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager
import pandas as pd
import logging
from typing import List, Dict, Any, Optional, Union, Generator
from datetime import datetime
import json
import time

from .schema import Base, DatabaseSchema
from ..data_processing import PickleManager
from pathlib import Path

class DatabaseManager:
    """데이터베이스 관리를 위한 클래스"""
    
    def __init__(self, database_url: str = "sqlite:///data/sambio_human.db"):
        """
        Args:
            database_url: 데이터베이스 연결 URL
        """
        self.database_url = database_url
        # SQLite URL에서 경로 추출
        if database_url.startswith("sqlite:///"):
            self.db_path = database_url.replace("sqlite:///", "")
        else:
            self.db_path = "data/sambio_human.db"  # 기본값
        
        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.logger = logging.getLogger(__name__)
        # self.schema = DatabaseSchema(database_url)  # 스키마 초기화 비활성화
        
        # 데이터베이스 초기화 - 비활성화
        # self._initialize_database()
    
    def _initialize_database(self):
        """데이터베이스 초기화 및 pickle 파일 자동 로드"""
        try:
            # 테이블 생성 - 비활성화 (스키마 문제로 인해)
            # self.schema.create_tables()
            self.logger.info("데이터베이스 초기화 완료")
            
            # Pickle 파일 자동 로드 - 비활성화 (이미 pickle 데이터를 직접 사용중)
            # self._auto_load_pickle_data()
            
        except Exception as e:
            self.logger.error(f"데이터베이스 초기화 실패: {e}")
            raise
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        데이터베이스 세션 컨텍스트 매니저
        
        Usage:
            with db_manager.get_session() as session:
                # 세션 사용
                pass
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"세션 오류: {e}")
            raise
        finally:
            session.close()
    
    def execute_query(self, query: Union[str, text], params: Dict = None) -> List[Dict]:
        """
        SQL 쿼리 실행
        
        Args:
            query: 실행할 SQL 쿼리
            params: 쿼리 파라미터
            
        Returns:
            List[Dict]: 쿼리 결과
        """
        try:
            with self.engine.begin() as connection:  # begin()을 사용하면 자동 커밋됨
                if isinstance(query, str):
                    query = text(query)
                
                result = connection.execute(query, params or {})
                
                # SELECT 쿼리인 경우 결과 반환
                if result.returns_rows:
                    columns = result.keys()
                    return [dict(zip(columns, row)) for row in result.fetchall()]
                else:
                    # INSERT/UPDATE/DELETE의 경우 영향받은 행 수 반환
                    self.logger.debug(f"Query executed, rows affected: {result.rowcount}")
                    return []
                    
        except SQLAlchemyError as e:
            self.logger.error(f"쿼리 실행 실패: {e}")
            raise
    
    def bulk_insert(self, table_name: str, data: List[Dict], batch_size: int = 1000) -> int:
        """
        대용량 데이터 배치 삽입
        
        Args:
            table_name: 테이블명
            data: 삽입할 데이터 리스트
            batch_size: 배치 크기
            
        Returns:
            int: 삽입된 행 수
        """
        if not data:
            return 0
        
        total_inserted = 0
        start_time = time.time()
        
        try:
            with self.get_session() as session:
                # 테이블 클래스 가져오기
                table_class = self._get_table_class(table_name)
                
                if not table_class:
                    raise ValueError(f"테이블 클래스를 찾을 수 없습니다: {table_name}")
                
                # 배치 단위로 처리
                for i in range(0, len(data), batch_size):
                    batch_data = data[i:i + batch_size]
                    
                    # 모델 인스턴스 생성
                    instances = [table_class(**row) for row in batch_data]
                    
                    # 배치 삽입
                    session.bulk_save_objects(instances)
                    session.commit()
                    
                    total_inserted += len(batch_data)
                    
                    # 진행률 로그
                    progress = (i + len(batch_data)) / len(data) * 100
                    self.logger.info(f"배치 삽입 진행률: {progress:.1f}% ({total_inserted:,}/{len(data):,})")
                
                elapsed_time = time.time() - start_time
                self.logger.info(f"배치 삽입 완료: {total_inserted:,}행, 소요시간: {elapsed_time:.2f}초")
                
                return total_inserted
                
        except Exception as e:
            self.logger.error(f"배치 삽입 실패: {e}")
            raise
    
    def bulk_update(self, table_name: str, data: List[Dict], batch_size: int = 1000) -> int:
        """
        대용량 데이터 배치 업데이트
        
        Args:
            table_name: 테이블명
            data: 업데이트할 데이터 리스트 (id 포함)
            batch_size: 배치 크기
            
        Returns:
            int: 업데이트된 행 수
        """
        if not data:
            return 0
        
        total_updated = 0
        start_time = time.time()
        
        try:
            with self.get_session() as session:
                table_class = self._get_table_class(table_name)
                
                if not table_class:
                    raise ValueError(f"테이블 클래스를 찾을 수 없습니다: {table_name}")
                
                # 배치 단위로 처리
                for i in range(0, len(data), batch_size):
                    batch_data = data[i:i + batch_size]
                    
                    # 배치 업데이트
                    session.bulk_update_mappings(table_class, batch_data)
                    session.commit()
                    
                    total_updated += len(batch_data)
                    
                    # 진행률 로그
                    progress = (i + len(batch_data)) / len(data) * 100
                    self.logger.info(f"배치 업데이트 진행률: {progress:.1f}% ({total_updated:,}/{len(data):,})")
                
                elapsed_time = time.time() - start_time
                self.logger.info(f"배치 업데이트 완료: {total_updated:,}행, 소요시간: {elapsed_time:.2f}초")
                
                return total_updated
                
        except Exception as e:
            self.logger.error(f"배치 업데이트 실패: {e}")
            raise
    
    def dataframe_to_table(self, df: pd.DataFrame, table_name: str, 
                          if_exists: str = 'append', batch_size: int = 1000) -> int:
        """
        DataFrame을 테이블에 삽입
        
        Args:
            df: 삽입할 DataFrame
            table_name: 대상 테이블명
            if_exists: 'append', 'replace', 'fail'
            batch_size: 배치 크기
            
        Returns:
            int: 삽입된 행 수
        """
        if df.empty:
            return 0
        
        try:
            start_time = time.time()
            
            # DataFrame을 SQL 테이블로 삽입
            rows_inserted = df.to_sql(
                table_name, 
                self.engine, 
                if_exists=if_exists, 
                index=False, 
                chunksize=batch_size
            )
            
            elapsed_time = time.time() - start_time
            self.logger.info(f"DataFrame 삽입 완료: {len(df):,}행 → {table_name}, 소요시간: {elapsed_time:.2f}초")
            
            return len(df)
            
        except Exception as e:
            self.logger.error(f"DataFrame 삽입 실패: {e}")
            raise
    
    def table_to_dataframe(self, table_name: str, query: str = None, 
                          params: Dict = None) -> pd.DataFrame:
        """
        테이블을 DataFrame으로 조회
        
        Args:
            table_name: 조회할 테이블명
            query: 사용자 정의 쿼리 (없으면 전체 조회)
            params: 쿼리 파라미터
            
        Returns:
            pd.DataFrame: 조회 결과
        """
        try:
            if query is None:
                query = f"SELECT * FROM {table_name}"
            
            df = pd.read_sql_query(query, self.engine, params=params)
            
            self.logger.info(f"테이블 조회 완료: {table_name} ({len(df):,}행 x {len(df.columns)}열)")
            
            return df
            
        except Exception as e:
            self.logger.error(f"테이블 조회 실패: {e}")
            raise
    
    def get_table_stats(self, table_name: str) -> Dict[str, Any]:
        """테이블 통계 정보 조회"""
        try:
            stats = {}
            
            # 행 수
            count_query = f"SELECT COUNT(*) as count FROM {table_name}"
            result = self.execute_query(count_query)
            stats['row_count'] = result[0]['count'] if result else 0
            
            # 테이블 정보
            table_info = self.schema.get_table_info()
            if table_name in table_info:
                stats['columns'] = table_info[table_name]['columns']
                stats['column_count'] = table_info[table_name]['column_count']
            
            # 최신 데이터 날짜 (created_at 컬럼이 있는 경우)
            try:
                date_query = f"SELECT MAX(created_at) as max_date FROM {table_name}"
                result = self.execute_query(date_query)
                if result and result[0]['max_date']:
                    stats['latest_data'] = result[0]['max_date']
            except:
                pass
            
            return stats
            
        except Exception as e:
            self.logger.error(f"테이블 통계 조회 실패: {e}")
            raise
    
    def cleanup_old_data(self, table_name: str, date_column: str, 
                        days_to_keep: int = 30) -> int:
        """오래된 데이터 정리"""
        try:
            cutoff_date = datetime.now() - pd.Timedelta(days=days_to_keep)
            
            delete_query = f"""
            DELETE FROM {table_name} 
            WHERE {date_column} < '{cutoff_date}'
            """
            
            with self.get_session() as session:
                result = session.execute(text(delete_query))
                deleted_count = result.rowcount
                
                self.logger.info(f"오래된 데이터 정리 완료: {table_name} ({deleted_count:,}행 삭제)")
                
                return deleted_count
                
        except Exception as e:
            self.logger.error(f"데이터 정리 실패: {e}")
            raise
    
    def backup_table(self, table_name: str, backup_path: str = None) -> str:
        """테이블 백업"""
        try:
            if backup_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"data/backup/{table_name}_{timestamp}.csv"
            
            df = self.table_to_dataframe(table_name)
            df.to_csv(backup_path, index=False, encoding='utf-8-sig')
            
            self.logger.info(f"테이블 백업 완료: {table_name} → {backup_path}")
            
            return backup_path
            
        except Exception as e:
            self.logger.error(f"테이블 백업 실패: {e}")
            raise
    
    def restore_table(self, table_name: str, backup_path: str, 
                     if_exists: str = 'replace') -> int:
        """테이블 복원"""
        try:
            df = pd.read_csv(backup_path)
            rows_restored = self.dataframe_to_table(df, table_name, if_exists)
            
            self.logger.info(f"테이블 복원 완료: {backup_path} → {table_name} ({rows_restored:,}행)")
            
            return rows_restored
            
        except Exception as e:
            self.logger.error(f"테이블 복원 실패: {e}")
            raise
    
    def get_table_class(self, table_name: str):
        """테이블명으로 SQLAlchemy 클래스 찾기"""
        # claim_data, tag_logs, abc_activity_data는 pickle에서만 처리
        if table_name in ['claim_data', 'tag_logs', 'tag_data', 'abc_activity_data', 'abc_data']:
            return None
            
        from .schema import (
            DailyWorkData, ShiftWorkData, OrganizationSummary,
            AttendanceData, NonWorkTimeData,
            EmployeeInfo, TagLocationMaster, OrganizationMapping,
            HmmModelConfig, ProcessingLog, EquipmentLogs
        )
        
        table_mapping = {
            'daily_work_data': DailyWorkData,
            'shift_work_data': ShiftWorkData,
            'organization_summary': OrganizationSummary,
            'attendance_data': AttendanceData,
            'non_work_time_data': NonWorkTimeData,
            'employee_info': EmployeeInfo,
            'tag_location_master': TagLocationMaster,
            'organization_mapping': OrganizationMapping,
            'hmm_model_config': HmmModelConfig,
            'processing_log': ProcessingLog,
            'equipment_logs': EquipmentLogs
        }
        
        return table_mapping.get(table_name)
    
    def get_database_info(self) -> Dict[str, Any]:
        """데이터베이스 전체 정보 조회"""
        try:
            info = {
                'database_url': self.database_url,
                'total_tables': 0,
                'total_records': 0,
                'tables': {}
            }
            
            table_info = self.schema.get_table_info()
            
            for table_name in table_info.keys():
                try:
                    stats = self.get_table_stats(table_name)
                    info['tables'][table_name] = stats
                    info['total_records'] += stats.get('row_count', 0)
                except:
                    # 테이블 통계 조회 실패 시 기본값
                    info['tables'][table_name] = {'row_count': 0, 'error': True}
            
            info['total_tables'] = len(info['tables'])
            
            return info
            
        except Exception as e:
            self.logger.error(f"데이터베이스 정보 조회 실패: {e}")
            raise
    
    def close(self):
        """데이터베이스 연결 종료"""
        try:
            self.engine.dispose()
            self.logger.info("데이터베이스 연결 종료")
        except Exception as e:
            self.logger.error(f"데이터베이스 연결 종료 실패: {e}")
    
    def _auto_load_pickle_data(self):
        """Pickle 파일에서 데이터를 자동으로 로드하여 데이터베이스에 저장"""
        self.logger.info("Pickle 데이터 자동 로드 시작...")
        
        try:
            pickle_manager = PickleManager()
            
            # 데이터 유형과 테이블 매핑
            data_mappings = {
                "tag_data": "태깅 데이터",
                "tag_location_master": "태깅 지점 마스터",
                "claim_data": "근무시간 Claim 데이터",
                "attendance_data": "근태 사용 데이터",
                "non_work_time": "비근무시간 데이터",
                "abc_data": "ABC 활동 데이터",
                "meal_data": "식사 데이터",
                "organization_data": "조직현황 자료"
            }
            
            for table_name, display_name in data_mappings.items():
                try:
                    # 테이블이 비어있는지 확인
                    existing_count = self.get_table_row_count(table_name)
                    
                    if existing_count == 0:
                        # Pickle 파일 확인
                        pickle_files = pickle_manager.list_pickle_files(table_name)
                        
                        if pickle_files:
                            latest_pickle = pickle_files[0]
                            self.logger.info(f"{display_name} pickle 파일 발견: {latest_pickle['rows']:,}행")
                            
                            # 데이터 로드
                            df = pickle_manager.load_dataframe(
                                name=table_name,
                                version=latest_pickle['version']
                            )
                            
                            if df is not None and not df.empty:
                                # attendance_data의 경우 특별 처리
                                if table_name == 'attendance_data':
                                    df = self._process_attendance_data(df)
                                
                                # 데이터베이스에 저장
                                self.save_dataframe(df, table_name)
                                self.logger.info(f"{display_name} 자동 로드 완료: {len(df):,}행")
                        else:
                            self.logger.info(f"{display_name}에 대한 pickle 파일 없음")
                    else:
                        self.logger.info(f"{display_name} 이미 데이터 존재: {existing_count:,}행")
                        
                except Exception as e:
                    self.logger.warning(f"{display_name} 자동 로드 실패: {e}")
                    continue
            
            self.logger.info("Pickle 데이터 자동 로드 완료")
            
        except Exception as e:
            self.logger.error(f"Pickle 데이터 자동 로드 중 오류: {e}")
            # 오류가 발생해도 애플리케이션은 계속 실행되도록 함
    
    def get_table_row_count(self, table_name: str) -> int:
        """테이블의 행 수를 반환"""
        try:
            query = f"SELECT COUNT(*) as count FROM {table_name}"
            result = self.execute_query(query)
            return result[0]['count'] if result else 0
        except Exception as e:
            self.logger.warning(f"테이블 행 수 조회 실패 ({table_name}): {e}")
            return 0
    
    def _process_attendance_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """attendance_data의 datetime.time 타입을 처리"""
        df_copy = df.copy()
        
        # 첫 번째 행이 헤더인 경우 제거
        if len(df_copy) > 0 and 'Unnamed: 0' in df_copy.columns:
            if df_copy.iloc[0]['Unnamed: 0'] == '사번':
                df_copy = df_copy.iloc[1:].copy()
                df_copy.reset_index(drop=True, inplace=True)
        
        # 컬럼명 매핑
        column_mapping = {
            'Unnamed: 0': 'employee_id',
            '질의2': 'employee_name',
            'Unnamed: 2': 'department_name',
            'Unnamed: 3': 'position_name',
            'Unnamed: 4': 'attendance_code',
            'Unnamed: 5': 'attendance_name',
            'Unnamed: 6': 'start_date',
            'Unnamed: 7': 'end_date',
            'Unnamed: 8': 'attendance_days',
            'Unnamed: 9': 'start_time',
            'Unnamed: 10': 'end_time',
            'Unnamed: 11': 'attendance_hours',
            'Unnamed: 12': 'reason',
            'Unnamed: 13': 'reason_detail',
            'Unnamed: 14': 'destination',
            'Unnamed: 15': 'contact',
            'Unnamed: 16': 'contact_relation',
            'Unnamed: 17': 'created_date',
            'Unnamed: 18': 'approval_status',
            'Unnamed: 19': 'last_modifier',
            'Unnamed: 20': 'first_approver',
            'Unnamed: 21': 'second_approver',
            'Unnamed: 22': 'third_approver'
        }
        
        df_copy.rename(columns=column_mapping, inplace=True)
        
        # 디버깅: 변환 전 데이터 타입 확인
        self.logger.debug("attendance_data 컬럼 타입:")
        for col in df_copy.columns:
            if col in ['start_time', 'end_time']:
                sample_val = df_copy[col].dropna().iloc[0] if not df_copy[col].dropna().empty else None
                self.logger.debug(f"  {col}: {type(sample_val)}")
        
        # datetime.time 타입 컬럼을 문자열로 변환
        time_columns = ['start_time', 'end_time']
        for col in time_columns:
            if col in df_copy.columns:
                # 각 값을 개별적으로 처리
                converted_values = []
                for idx, val in enumerate(df_copy[col]):
                    try:
                        if pd.isna(val) or val is None or str(val).strip() == '':
                            converted_values.append(None)
                        elif hasattr(val, 'strftime'):
                            # datetime.time 객체인 경우
                            converted_values.append(val.strftime('%H:%M:%S'))
                        elif isinstance(val, str):
                            # 이미 문자열인 경우
                            converted_values.append(val)
                        else:
                            # 기타 타입은 문자열로 변환
                            converted_values.append(str(val))
                    except Exception as e:
                        self.logger.warning(f"{col} 컬럼의 {idx}번째 값 변환 실패: {type(val)} - {e}")
                        converted_values.append(None)
                df_copy[col] = converted_values
        
        # 날짜 컬럼 처리 (YYYYMMDD 형식을 YYYY-MM-DD로 변환)
        date_columns = ['start_date', 'end_date', 'created_date']
        for col in date_columns:
            if col in df_copy.columns:
                df_copy[col] = pd.to_datetime(df_copy[col], format='%Y%m%d', errors='coerce')
        
        # 숫자 타입 변환
        numeric_columns = ['attendance_days', 'attendance_hours']
        for col in numeric_columns:
            if col in df_copy.columns:
                df_copy[col] = pd.to_numeric(df_copy[col], errors='coerce')
        
        self.logger.info(f"attendance_data 처리 완료: {len(df_copy)}행")
        return df_copy
    
    def save_dataframe(self, df: pd.DataFrame, table_name: str, if_exists: str = 'replace'):
        """DataFrame을 데이터베이스에 저장"""
        try:
            # datetime.time 타입 컬럼을 문자열로 변환
            df_copy = df.copy()
            
            # 모든 object 타입 컬럼 검사
            for col in df_copy.columns:
                if df_copy[col].dtype == 'object':
                    # 각 값을 안전하게 변환
                    converted_values = []
                    has_time_objects = False
                    
                    for val in df_copy[col]:
                        if pd.isna(val) or val is None:
                            converted_values.append(None)
                        elif hasattr(val, 'strftime') and hasattr(val, 'hour'):
                            # datetime.time 또는 datetime 객체
                            has_time_objects = True
                            if hasattr(val, 'date'):
                                # datetime 객체
                                converted_values.append(val.strftime('%Y-%m-%d %H:%M:%S'))
                            else:
                                # time 객체
                                converted_values.append(val.strftime('%H:%M:%S'))
                        else:
                            converted_values.append(val)
                    
                    if has_time_objects:
                        self.logger.debug(f"{col} 컬럼의 시간 객체를 문자열로 변환")
                        df_copy[col] = converted_values
            
            # 데이터베이스에 저장
            df_copy.to_sql(table_name, self.engine, if_exists=if_exists, index=False)
            self.logger.info(f"{table_name} 테이블에 {len(df):,}행 저장 완료")
        except Exception as e:
            self.logger.error(f"{table_name} 테이블 저장 실패: {e}")
            # 더 자세한 디버깅 정보
            if 'parameter' in str(e):
                self.logger.error(f"데이터 타입 정보:")
                for col in df_copy.columns:
                    self.logger.error(f"  {col}: {df_copy[col].dtype}")
                    # object 타입인 경우 샘플 확인
                    if df_copy[col].dtype == 'object' and not df_copy[col].dropna().empty:
                        sample = df_copy[col].dropna().iloc[0]
                        self.logger.error(f"    샘플 값 타입: {type(sample)}")
            raise