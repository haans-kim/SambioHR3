"""
장비 사용 데이터에서 O 태그 빠르게 생성 (간소화 버전)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import pickle
import gzip
import logging
from datetime import datetime
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_o_tags_fast(equipment_df):
    """빠른 O 태그 생성 (30분 단위로 그룹화)"""
    logger.info("O 태그 생성 중...")
    
    # 타임스탬프를 30분 단위로 반올림
    equipment_df['timestamp_30min'] = equipment_df['timestamp'].dt.floor('30min')
    
    # 사원별, 30분 단위별로 그룹화
    grouped = equipment_df.groupby(['employee_id', 'timestamp_30min']).agg({
        'system_type': lambda x: list(x.unique()),
        'timestamp': ['min', 'max', 'count']
    }).reset_index()
    
    # 컬럼명 정리
    grouped.columns = ['employee_id', 'timestamp', 'system_types', 'start_time', 'end_time', 'action_count']
    
    # O 태그 데이터 생성
    o_tags = []
    for _, row in grouped.iterrows():
        # 3개 이상의 액션이 있거나 여러 시스템을 사용한 경우
        if row['action_count'] >= 3 or len(row['system_types']) > 1:
            duration = (row['end_time'] - row['start_time']).total_seconds() / 60
            
            o_tag = {
                'employee_id': row['employee_id'],
                'timestamp': row['timestamp'],
                'tag_code': 'O',
                'source': 'equipment_data',
                'equipment_types': row['system_types'],
                'duration_minutes': max(duration, 30),  # 최소 30분
                'action_count': row['action_count'],
                'confidence': 1.0
            }
            o_tags.append(o_tag)
    
    return pd.DataFrame(o_tags)

def main():
    # 통합 장비 데이터 로드
    equipment_file = 'data/pickles/equipment_data_merged_v20250726_120101.pkl.gz'
    
    logger.info(f"장비 데이터 로드 중: {equipment_file}")
    with gzip.open(equipment_file, 'rb') as f:
        equipment_df = pickle.load(f)
    
    logger.info(f"로드 완료: {len(equipment_df):,}개 레코드")
    
    # O 태그 생성 (빠른 버전)
    o_tags_df = create_o_tags_fast(equipment_df)
    
    if len(o_tags_df) > 0:
        # 타임스탬프 생성
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Pickle 파일로 저장
        output_file = f'data/pickles/o_tags_equipment_v{timestamp}.pkl.gz'
        with gzip.open(output_file, 'wb') as f:
            pickle.dump(o_tags_df, f)
        
        logger.info(f"O 태그 데이터 저장 완료: {output_file}")
        
        # 통계 출력
        logger.info(f"\n=== O 태그 생성 통계 ===")
        logger.info(f"총 O 태그 수: {len(o_tags_df):,}개")
        logger.info(f"대상 사원 수: {o_tags_df['employee_id'].nunique():,}명")
        logger.info(f"평균 지속 시간: {o_tags_df['duration_minutes'].mean():.1f}분")
        logger.info(f"평균 작업 수: {o_tags_df['action_count'].mean():.1f}회")
        
        # 날짜별 분포
        o_tags_df['date'] = o_tags_df['timestamp'].dt.date
        date_dist = o_tags_df.groupby('date').size()
        logger.info(f"\n날짜별 O 태그 분포:")
        for date, count in date_dist.head(10).items():
            logger.info(f"  {date}: {count:,}개")
    else:
        logger.warning("생성된 O 태그가 없습니다.")

if __name__ == "__main__":
    main()