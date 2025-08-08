"""
최적화된 배치 처리 프로세서
NumPy 기반 벡터화 연산과 효율적인 데이터 구조 사용
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from datetime import date, datetime, timedelta
import pickle
import logging
from dataclasses import dataclass
from multiprocessing import Pool, shared_memory
import psycopg2
from psycopg2 import pool as pg_pool
import sqlite3
import redis
import time
import hashlib


@dataclass
class OptimizedDataStructure:
    """최적화된 데이터 구조"""
    # NumPy 배열로 저장 (메모리 효율성 + 빠른 접근)
    employee_ids: np.ndarray  # shape: (n_employees,)
    dates: np.ndarray         # shape: (n_dates,)
    tag_matrix: np.ndarray    # shape: (n_employees, n_dates, n_tags)
    meal_matrix: np.ndarray   # shape: (n_employees, n_dates, n_meals)
    claim_matrix: np.ndarray  # shape: (n_employees, n_dates, n_features)
    
    # 인덱스 매핑 (O(1) 접근)
    emp_id_to_idx: Dict[str, int]
    date_to_idx: Dict[date, int]
    tag_to_idx: Dict[str, int]


class OptimizedBatchProcessor:
    """최적화된 배치 처리 프로세서"""
    
    def __init__(self, 
                 db_type: str = 'sqlite',  # 'sqlite', 'postgresql', 'hybrid'
                 cache_type: str = 'memory',  # 'memory', 'redis', 'shared_memory'
                 num_workers: int = 12):
        """
        Args:
            db_type: 데이터베이스 타입
            cache_type: 캐시 타입
            num_workers: 워커 프로세스 수
        """
        self.db_type = db_type
        self.cache_type = cache_type
        self.num_workers = num_workers
        
        # 로깅 설정
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # 데이터 구조 초기화
        self.data_structure = None
        
        # DB 연결 설정
        self._setup_database()
        
        # 캐시 설정
        self._setup_cache()
        
    def _setup_database(self):
        """데이터베이스 연결 설정"""
        if self.db_type == 'postgresql':
            # PostgreSQL 연결 풀 (병렬 쓰기 가능)
            try:
                self.pg_pool = pg_pool.ThreadedConnectionPool(
                    minconn=2,
                    maxconn=self.num_workers + 5,
                    host="localhost",
                    database="sambio_analytics",
                    user="sambio",
                    password="sambio123"
                )
                self.logger.info("PostgreSQL 연결 풀 생성 완료")
            except Exception as e:
                self.logger.warning(f"PostgreSQL 연결 실패, SQLite로 전환: {e}")
                self.db_type = 'sqlite'
                self._setup_sqlite()
            
        elif self.db_type == 'hybrid':
            # 읽기: SQLite, 쓰기: PostgreSQL
            self.sqlite_conn = sqlite3.connect('data/sambio_human.db', check_same_thread=False)
            self.sqlite_conn.row_factory = sqlite3.Row
            
            self.pg_pool = pg_pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=self.num_workers + 5,
                host="localhost",
                database="sambio_analytics",
                user="sambio",
                password="sambio123"
            )
            self.logger.info("Hybrid DB 설정 완료 (읽기: SQLite, 쓰기: PostgreSQL)")
            
        else:  # sqlite
            self._setup_sqlite()
    
    def _setup_sqlite(self):
        """SQLite 연결 설정"""
        self.sqlite_conn = sqlite3.connect('data/sambio_human.db', check_same_thread=False)
        self.sqlite_conn.row_factory = sqlite3.Row
        # WAL 모드 활성화 (병렬 읽기 개선)
        self.sqlite_conn.execute("PRAGMA journal_mode=WAL")
        self.sqlite_conn.execute("PRAGMA synchronous=NORMAL")
        self.logger.info("SQLite 연결 완료 (WAL 모드)")
    
    def _setup_cache(self):
        """캐시 설정"""
        if self.cache_type == 'redis':
            try:
                self.redis_client = redis.Redis(
                    host='localhost', 
                    port=6379, 
                    db=0,
                    decode_responses=False  # 바이너리 데이터 저장
                )
                # 연결 테스트
                self.redis_client.ping()
                self.logger.info("Redis 캐시 연결 완료")
            except Exception as e:
                self.logger.warning(f"Redis 연결 실패, 메모리 캐시로 전환: {e}")
                self.cache_type = 'memory'
                self.memory_cache = {}
            
        elif self.cache_type == 'shared_memory':
            # 공유 메모리는 load_data에서 설정
            self.shared_memory_blocks = {}
            self.logger.info("공유 메모리 캐시 준비")
            
        else:  # memory
            self.memory_cache = {}
            self.logger.info("메모리 캐시 준비")
    
    def load_and_prepare_data(self, target_date: date) -> OptimizedDataStructure:
        """
        데이터를 로드하고 최적화된 구조로 변환
        한 번만 로드하고 모든 워커가 공유
        """
        self.logger.info(f"데이터 로드 및 준비 시작: {target_date}")
        start_time = time.time()
        
        # 1. 필요한 데이터 로드 (한 번만!)
        if self.db_type == 'postgresql':
            conn = self.pg_pool.getconn()
        else:
            conn = self.sqlite_conn
        
        try:
            # 직원 목록
            employees_df = pd.read_sql_query(
                "SELECT DISTINCT employee_id FROM employees WHERE is_active = 1",
                conn
            )
            employee_ids = employees_df['employee_id'].values
            
            # 태그 데이터 (날짜 범위 제한)
            date_start = target_date - timedelta(days=1)  # 야간근무 고려
            date_end = target_date + timedelta(days=1)
            
            tag_query = f"""
                SELECT employee_id, tag_time, tag_location, tag_type
                FROM tag_data
                WHERE tag_time >= '{date_start}' AND tag_time < '{date_end}'
                ORDER BY employee_id, tag_time
            """
            tag_df = pd.read_sql_query(tag_query, conn)
            
            # 식사 데이터
            meal_query = f"""
                SELECT employee_id, meal_time, meal_type, location
                FROM meal_data
                WHERE meal_date >= '{date_start}' AND meal_date <= '{date_end}'
            """
            meal_df = pd.read_sql_query(meal_query, conn)
            
            # Claim 데이터
            claim_query = f"""
                SELECT employee_id, work_date, work_type, 
                       scheduled_hours, actual_hours
                FROM claim_data
                WHERE work_date = '{target_date}'
            """
            claim_df = pd.read_sql_query(claim_query, conn)
            
        finally:
            if self.db_type == 'postgresql':
                self.pg_pool.putconn(conn)
        
        # 2. NumPy 배열로 변환 (벡터화 연산용)
        n_employees = len(employee_ids)
        n_dates = 1  # 일단 하루치만
        n_tag_types = 20  # 태그 종류 수
        n_meal_types = 4  # 조식, 중식, 석식, 야식
        n_features = 10  # Claim 데이터 특징 수
        
        # 초기화
        tag_matrix = np.zeros((n_employees, n_dates, n_tag_types), dtype=np.float32)
        meal_matrix = np.zeros((n_employees, n_dates, n_meal_types), dtype=np.float32)
        claim_matrix = np.zeros((n_employees, n_dates, n_features), dtype=np.float32)
        
        # 인덱스 매핑 생성
        emp_id_to_idx = {emp_id: idx for idx, emp_id in enumerate(employee_ids)}
        date_to_idx = {target_date: 0}
        tag_types = tag_df['tag_type'].unique() if 'tag_type' in tag_df.columns else []
        tag_to_idx = {tag: idx for idx, tag in enumerate(tag_types[:n_tag_types])}
        
        # 3. 데이터 채우기 (벡터화된 연산)
        self.logger.info("데이터 매트릭스 생성 중...")
        
        # 태그 데이터 처리
        for _, row in tag_df.iterrows():
            emp_idx = emp_id_to_idx.get(row['employee_id'])
            if emp_idx is not None:
                tag_idx = tag_to_idx.get(row.get('tag_type', 'default'), 0)
                tag_matrix[emp_idx, 0, tag_idx] += 1  # 카운트 증가
        
        # 식사 데이터 처리
        meal_type_map = {'조식': 0, '중식': 1, '석식': 2, '야식': 3}
        for _, row in meal_df.iterrows():
            emp_idx = emp_id_to_idx.get(row['employee_id'])
            if emp_idx is not None:
                meal_idx = meal_type_map.get(row.get('meal_type', ''), 0)
                meal_matrix[emp_idx, 0, meal_idx] = 1  # 식사 여부
        
        # Claim 데이터 처리
        for _, row in claim_df.iterrows():
            emp_idx = emp_id_to_idx.get(row['employee_id'])
            if emp_idx is not None:
                claim_matrix[emp_idx, 0, 0] = row.get('scheduled_hours', 0)
                claim_matrix[emp_idx, 0, 1] = row.get('actual_hours', 0)
                # ... 추가 특징들
        
        # 4. 최적화된 구조 생성
        data_structure = OptimizedDataStructure(
            employee_ids=employee_ids,
            dates=np.array([target_date]),
            tag_matrix=tag_matrix,
            meal_matrix=meal_matrix,
            claim_matrix=claim_matrix,
            emp_id_to_idx=emp_id_to_idx,
            date_to_idx=date_to_idx,
            tag_to_idx=tag_to_idx
        )
        
        elapsed = time.time() - start_time
        self.logger.info(f"데이터 준비 완료: {elapsed:.2f}초")
        self.logger.info(f"  - 직원 수: {n_employees:,}")
        self.logger.info(f"  - 태그 데이터: {len(tag_df):,}건")
        self.logger.info(f"  - 메모리 사용: {(tag_matrix.nbytes + meal_matrix.nbytes + claim_matrix.nbytes) / 1024 / 1024:.1f}MB")
        
        # 5. 캐시에 저장
        self._cache_data(data_structure)
        self.data_structure = data_structure
        
        return data_structure
    
    def _cache_data(self, data_structure: OptimizedDataStructure):
        """데이터를 캐시에 저장"""
        if self.cache_type == 'redis':
            # Redis에 저장 (직렬화)
            for key, array in [
                ('tag_matrix', data_structure.tag_matrix),
                ('meal_matrix', data_structure.meal_matrix),
                ('claim_matrix', data_structure.claim_matrix)
            ]:
                self.redis_client.set(
                    key,
                    pickle.dumps(array),
                    ex=3600  # 1시간 TTL
                )
            self.logger.info("Redis에 데이터 캐싱 완료")
            
        elif self.cache_type == 'shared_memory':
            # 공유 메모리에 저장
            for key, array in [
                ('tag_matrix', data_structure.tag_matrix),
                ('meal_matrix', data_structure.meal_matrix),
                ('claim_matrix', data_structure.claim_matrix)
            ]:
                shm = shared_memory.SharedMemory(create=True, size=array.nbytes)
                shared_array = np.ndarray(array.shape, dtype=array.dtype, buffer=shm.buf)
                shared_array[:] = array[:]
                self.shared_memory_blocks[key] = shm
            self.logger.info("공유 메모리에 데이터 저장 완료")
            
        else:  # memory
            self.memory_cache['data'] = data_structure
            self.logger.info("메모리 캐시에 데이터 저장 완료")
    
    def analyze_employee_vectorized(self, emp_idx: int) -> Dict[str, Any]:
        """
        벡터화된 연산으로 직원 분석 (NumPy 활용)
        인스턴스 생성 없이 순수 연산만 수행
        """
        # 데이터 추출 (이미 메모리에 있음)
        tag_vector = self.data_structure.tag_matrix[emp_idx, 0, :]
        meal_vector = self.data_structure.meal_matrix[emp_idx, 0, :]
        claim_vector = self.data_structure.claim_matrix[emp_idx, 0, :]
        
        # 벡터화된 연산으로 분석 (예시)
        total_tags = np.sum(tag_vector)
        work_hours = claim_vector[1]  # actual_hours
        meal_count = np.sum(meal_vector)
        
        # 효율성 계산 (벡터 연산)
        if claim_vector[0] > 0:  # scheduled_hours
            efficiency = work_hours / claim_vector[0]
        else:
            efficiency = 0
        
        return {
            'employee_id': self.data_structure.employee_ids[emp_idx],
            'total_tags': int(total_tags),
            'work_hours': float(work_hours),
            'meal_count': int(meal_count),
            'efficiency': float(efficiency)
        }
    
    def batch_analyze_optimized(self, target_date: date) -> List[Dict[str, Any]]:
        """
        최적화된 배치 분석 실행
        """
        # 1. 데이터 로드 (한 번만!)
        data_structure = self.load_and_prepare_data(target_date)
        
        # 2. 병렬 처리
        with Pool(self.num_workers) as pool:
            # 직원 인덱스 리스트
            emp_indices = list(range(len(data_structure.employee_ids)))
            
            # 병렬 분석 실행
            results = pool.map(self.analyze_employee_vectorized, emp_indices)
        
        # 3. 결과 저장
        self._save_results_batch(results)
        
        return results
    
    def _save_results_batch(self, results: List[Dict[str, Any]]):
        """배치로 결과 저장"""
        if self.db_type == 'postgresql':
            # PostgreSQL COPY 명령 사용 (가장 빠름)
            conn = self.pg_pool.getconn()
            try:
                with conn.cursor() as cur:
                    # COPY 사용
                    from io import StringIO
                    buffer = StringIO()
                    
                    for r in results:
                        buffer.write(f"{r['employee_id']}\t")
                        buffer.write(f"{r['work_hours']}\t")
                        buffer.write(f"{r['efficiency']}\n")
                    
                    buffer.seek(0)
                    cur.copy_from(
                        buffer,
                        'analysis_results',
                        columns=['employee_id', 'work_hours', 'efficiency']
                    )
                    conn.commit()
                    
            finally:
                self.pg_pool.putconn(conn)
                
        else:  # SQLite
            # executemany 사용 (트랜잭션으로 묶어서 처리)
            with self.sqlite_conn:
                self.sqlite_conn.executemany(
                    """INSERT OR REPLACE INTO daily_analysis_results 
                       (employee_id, work_hours, efficiency) 
                       VALUES (?, ?, ?)""",
                    [(r['employee_id'], r['work_hours'], r['efficiency']) 
                     for r in results]
                )
            
        self.logger.info(f"{len(results)}건 저장 완료")


# 성능 비교 테스트
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', choices=['sqlite', 'postgresql', 'hybrid'], default='sqlite')
    parser.add_argument('--cache', choices=['memory', 'redis', 'shared_memory'], default='memory')
    parser.add_argument('--workers', type=int, default=12)
    parser.add_argument('--date', type=str, default='2025-06-15')
    
    args = parser.parse_args()
    
    # 프로세서 생성
    processor = OptimizedBatchProcessor(
        db_type=args.db,
        cache_type=args.cache,
        num_workers=args.workers
    )
    
    # 분석 실행
    target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
    
    start_time = time.time()
    results = processor.batch_analyze_optimized(target_date)
    elapsed = time.time() - start_time
    
    print(f"\n✅ 분석 완료")
    print(f"  - 처리 건수: {len(results):,}")
    print(f"  - 소요 시간: {elapsed:.2f}초")
    print(f"  - 처리 속도: {len(results)/elapsed:.1f}건/초")