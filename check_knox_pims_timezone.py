"""Knox PIMS 시간대 확인"""
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from src.data_processing.pickle_manager import PickleManager

# Pickle 매니저 초기화
pickle_manager = PickleManager()

# Knox PIMS 데이터 로드
print("Knox PIMS 데이터 로드 중...")
knox_pims_df = pickle_manager.load_pickle('knox_pims_data')

if knox_pims_df is not None:
    print(f"\n데이터 shape: {knox_pims_df.shape}")
    print(f"\n컬럼 목록:")
    for col in knox_pims_df.columns:
        print(f"  - {col}")
    
    # 시간 관련 컬럼 찾기
    time_columns = [col for col in knox_pims_df.columns if any(keyword in col.lower() for keyword in ['시간', '일시', 'time', 'date', 'gmt'])]
    
    print(f"\n시간 관련 컬럼:")
    for col in time_columns:
        print(f"  - {col}")
    
    # 샘플 데이터 확인
    print(f"\n샘플 데이터 (첫 3행):")
    if time_columns:
        print(knox_pims_df[time_columns].head(3))
    
    # GMT 관련 컬럼 상세 확인
    gmt_columns = [col for col in knox_pims_df.columns if 'GMT' in col.upper()]
    if gmt_columns:
        print(f"\nGMT 관련 컬럼 상세:")
        for col in gmt_columns:
            print(f"\n{col}:")
            print(f"  - 데이터 타입: {knox_pims_df[col].dtype}")
            print(f"  - 샘플 값:")
            print(knox_pims_df[col].dropna().head(3))
else:
    print("Knox PIMS 데이터를 찾을 수 없습니다.")