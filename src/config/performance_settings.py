"""
성능 최적화 설정
Intel Mac과 Apple Silicon Mac의 성능 차이를 고려한 동적 설정
"""

import platform
import multiprocessing
import os

# 시스템 정보 감지
def is_apple_silicon():
    """Apple Silicon 여부 확인"""
    return platform.machine() in ['arm64', 'aarch64']

def get_cpu_count():
    """CPU 코어 수 확인"""
    return multiprocessing.cpu_count()

# Intel Mac vs Apple Silicon 최적화 설정
if is_apple_silicon():
    # Apple Silicon (M1/M2/M3/M4) 최적화
    MAX_NODES_DISPLAY = 200  # 더 많은 노드 처리 가능
    INTERACTION_TIME_SLOT = 30
    PARALLEL_WORKERS = get_cpu_count()  # 모든 코어 사용
    BATCH_SIZE = 50000  # 대용량 배치
    CHUNK_SIZE = 100000  # 대용량 청크
    COMPRESSION_LEVEL = 6  # 높은 압축률
    USE_PARALLEL = True
else:
    # Intel Mac 최적화 (보수적 설정)
    MAX_NODES_DISPLAY = 100
    INTERACTION_TIME_SLOT = 30
    PARALLEL_WORKERS = max(2, get_cpu_count() // 2)  # 절반 코어만 사용
    BATCH_SIZE = 10000  # 작은 배치
    CHUNK_SIZE = 10000  # 작은 청크
    COMPRESSION_LEVEL = 1  # 빠른 압축
    USE_PARALLEL = False

# 캐싱 설정
CACHE_EXPIRY_HOURS = 24
USE_MEMORY_CACHE = True

# 쿼리 최적화
USE_INDEX = True

# 시각화 설정
PLOT_DPI = 100 if is_apple_silicon() else 72  # Apple Silicon은 고해상도 가능
ANIMATION_FRAMES = 20 if is_apple_silicon() else 10

# 네트워크 분석 설정
MIN_INTERACTION_COUNT = 2
MAX_GRAPH_DENSITY = 0.8

# Pickle 설정
PICKLE_PROTOCOL = 5  # 최신 프로토콜 (Python 3.8+)
PICKLE_COMPRESSION = 'gzip' if is_apple_silicon() else 'lz4'  # Intel은 빠른 압축

# 환경 변수로 오버라이드 가능
if os.getenv('PERFORMANCE_MODE') == 'high':
    BATCH_SIZE = 100000
    CHUNK_SIZE = 200000
    PARALLEL_WORKERS = -1
elif os.getenv('PERFORMANCE_MODE') == 'low':
    BATCH_SIZE = 5000
    CHUNK_SIZE = 5000
    PARALLEL_WORKERS = 1
    USE_PARALLEL = False

# 시스템 정보 출력 (디버깅용)
if __name__ == "__main__":
    print(f"System: {platform.machine()}")
    print(f"CPU Count: {get_cpu_count()}")
    print(f"Apple Silicon: {is_apple_silicon()}")
    print(f"Batch Size: {BATCH_SIZE}")
    print(f"Parallel Workers: {PARALLEL_WORKERS}")