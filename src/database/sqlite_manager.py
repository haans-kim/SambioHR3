import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from pathlib import Path
import logging
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from .models import Base, Employee, DailyWorkSummary, OrgSummary, ProcessedTagData

logger = logging.getLogger(__name__)


class SQLiteManager:
    """SQLite 데이터베이스 관리 클래스"""
    
    def __init__(self, db_path: str = "hrm_analytics.db"):
        """
        Args:
            db_path: SQLite 데이터베이스 파일 경로
        """
        self.db_path = Path(db_path)
        self.engine = None
        self.SessionLocal = None
        self._initialize_database()
    
    def _initialize_database(self):
        """데이터베이스 초기화"""
        try:
            # SQLAlchemy 엔진 생성
            self.engine = create_engine(
                f'sqlite:///{self.db_path}',
                echo=False,  # SQL 로그 출력 여부
                connect_args={'check_same_thread': False}  # SQLite 멀티스레드 지원
            )
            
            # 세션 팩토리 생성
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            
            # 테이블 생성
            Base.metadata.create_all(bind=self.engine)
            
            logger.info(f"Database initialized at: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    @contextmanager
    def get_session(self) -> Session:
        """데이터베이스 세션 컨텍스트 매니저"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Session error: {e}")
            raise
        finally:
            session.close()
    
    def insert_employee(self, employee_data: Dict[str, Any]) -> bool:
        """직원 정보 삽입"""
        try:
            with self.get_session() as session:
                employee = Employee(**employee_data)
                session.add(employee)
                logger.info(f"Employee {employee_data['employee_id']} inserted")
                return True
        except SQLAlchemyError as e:
            logger.error(f"Failed to insert employee: {e}")
            return False
    
    def bulk_insert_employees(self, employees_data: List[Dict[str, Any]]) -> int:
        """직원 정보 대량 삽입"""
        inserted_count = 0
        try:
            with self.get_session() as session:
                for emp_data in employees_data:
                    # 기존 직원 확인
                    existing = session.query(Employee).filter_by(
                        employee_id=emp_data['employee_id']
                    ).first()
                    
                    if not existing:
                        employee = Employee(**emp_data)
                        session.add(employee)
                        inserted_count += 1
                
                logger.info(f"Bulk inserted {inserted_count} employees")
                return inserted_count
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to bulk insert employees: {e}")
            return 0
    
    def insert_daily_summary(self, summary_data: Dict[str, Any]) -> bool:
        """일일 근무 요약 삽입"""
        try:
            with self.get_session() as session:
                # 기존 데이터 확인 (중복 방지)
                existing = session.query(DailyWorkSummary).filter_by(
                    employee_id=summary_data['employee_id'],
                    date=summary_data['date']
                ).first()
                
                if existing:
                    # 업데이트
                    for key, value in summary_data.items():
                        setattr(existing, key, value)
                    logger.info(f"Updated daily summary for {summary_data['employee_id']} on {summary_data['date']}")
                else:
                    # 신규 삽입
                    summary = DailyWorkSummary(**summary_data)
                    session.add(summary)
                    logger.info(f"Inserted daily summary for {summary_data['employee_id']} on {summary_data['date']}")
                
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to insert daily summary: {e}")
            return False
    
    def get_employee_summary(self, employee_id: str, start_date=None, end_date=None) -> List[DailyWorkSummary]:
        """직원의 일일 근무 요약 조회"""
        try:
            with self.get_session() as session:
                query = session.query(DailyWorkSummary).filter_by(employee_id=employee_id)
                
                if start_date:
                    query = query.filter(DailyWorkSummary.date >= start_date)
                if end_date:
                    query = query.filter(DailyWorkSummary.date <= end_date)
                
                return query.order_by(DailyWorkSummary.date).all()
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get employee summary: {e}")
            return []
    
    def get_org_summary(self, org_id: str, date) -> Optional[OrgSummary]:
        """조직 요약 데이터 조회"""
        try:
            with self.get_session() as session:
                return session.query(OrgSummary).filter_by(
                    org_id=org_id,
                    date=date
                ).first()
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get org summary: {e}")
            return None
    
    def insert_processed_tag_data(self, tag_data: List[Dict[str, Any]]) -> int:
        """전처리된 태그 데이터 대량 삽입"""
        inserted_count = 0
        try:
            with self.get_session() as session:
                for data in tag_data:
                    tag_record = ProcessedTagData(**data)
                    session.add(tag_record)
                    inserted_count += 1
                
                # 대량 삽입 시 주기적으로 커밋
                if inserted_count % 1000 == 0:
                    session.commit()
                
                logger.info(f"Inserted {inserted_count} processed tag records")
                return inserted_count
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to insert processed tag data: {e}")
            return 0
    
    def execute_raw_query(self, query: str) -> List[tuple]:
        """원시 SQL 쿼리 실행"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(query)
                return result.fetchall()
        except Exception as e:
            logger.error(f"Failed to execute raw query: {e}")
            return []
    
    def get_database_stats(self) -> Dict[str, int]:
        """데이터베이스 통계 정보 조회"""
        stats = {}
        try:
            with self.get_session() as session:
                stats['employees'] = session.query(Employee).count()
                stats['daily_summaries'] = session.query(DailyWorkSummary).count()
                stats['org_summaries'] = session.query(OrgSummary).count()
                stats['processed_tags'] = session.query(ProcessedTagData).count()
                
                # 파일 크기
                if self.db_path.exists():
                    stats['db_size_mb'] = self.db_path.stat().st_size / 1024 / 1024
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return stats
    
    def backup_database(self, backup_path: str):
        """데이터베이스 백업"""
        try:
            backup_path = Path(backup_path)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            # SQLite 백업
            src_conn = sqlite3.connect(str(self.db_path))
            dst_conn = sqlite3.connect(str(backup_path))
            
            with dst_conn:
                src_conn.backup(dst_conn)
            
            src_conn.close()
            dst_conn.close()
            
            logger.info(f"Database backed up to: {backup_path}")
            
        except Exception as e:
            logger.error(f"Failed to backup database: {e}")
            raise


# 사용 예시
if __name__ == "__main__":
    # 데이터베이스 매니저 초기화
    db_manager = SQLiteManager("test_hrm.db")
    
    # 직원 정보 삽입
    employee_data = {
        'employee_id': 'E001',
        'name': '홍길동',
        'department': 'IT',
        'position': '대리'
    }
    db_manager.insert_employee(employee_data)
    
    # 데이터베이스 통계
    stats = db_manager.get_database_stats()
    print(f"Database stats: {stats}")