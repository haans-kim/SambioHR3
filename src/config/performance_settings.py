"""
성능 최적화 설정
"""

# 데이터 처리 설정
MAX_NODES_DISPLAY = 100  # 네트워크 시각화 시 최대 노드 수
INTERACTION_TIME_SLOT = 30  # 상호작용 시간 단위 (분)
PARALLEL_WORKERS = 4  # 병렬 처리 워커 수

# 캐싱 설정
CACHE_EXPIRY_HOURS = 24  # 캐시 유효 시간
USE_MEMORY_CACHE = True  # 메모리 캐싱 사용 여부

# 쿼리 최적화
BATCH_SIZE = 10000  # 배치 처리 크기
USE_INDEX = True  # 인덱스 사용 여부

# 시각화 설정
PLOT_DPI = 100  # 플롯 해상도 (낮을수록 빠름)
ANIMATION_FRAMES = 10  # 애니메이션 프레임 수

# 네트워크 분석 설정
MIN_INTERACTION_COUNT = 2  # 최소 상호작용 횟수
MAX_GRAPH_DENSITY = 0.8  # 최대 그래프 밀도