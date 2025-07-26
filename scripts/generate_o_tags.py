"""
장비 사용 데이터에서 O 태그 생성
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import pickle
import gzip
import logging
from datetime import datetime
from src.data.equipment_processors import create_o_tags_from_equipment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # 통합 장비 데이터 로드
    equipment_file = 'data/pickles/equipment_data_merged_v20250726_120101.pkl.gz'
    
    logger.info(f"장비 데이터 로드 중: {equipment_file}")
    with gzip.open(equipment_file, 'rb') as f:
        equipment_df = pickle.load(f)
    
    logger.info(f"로드 완료: {len(equipment_df):,}개 레코드")
    
    # O 태그 생성
    logger.info("O 태그 생성 시작...")
    o_tags = create_o_tags_from_equipment(equipment_df)
    
    # DataFrame으로 변환
    o_tags_df = pd.DataFrame(o_tags)
    
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
        
        # 시스템별 O 태그 분포
        logger.info(f"\n시스템별 O 태그 분포:")
        system_dist = {}
        for _, row in o_tags_df.iterrows():
            for system in row['equipment_types']:
                system_dist[system] = system_dist.get(system, 0) + 1
        
        for system, count in sorted(system_dist.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {system}: {count:,}개")
        
        # 샘플 출력
        logger.info(f"\nO 태그 샘플 (처음 5개):")
        for i, row in o_tags_df.head().iterrows():
            logger.info(f"  {row['employee_id']} - {row['timestamp']} - "
                       f"{row['duration_minutes']:.0f}분 - {row['equipment_types']}")
    else:
        logger.warning("생성된 O 태그가 없습니다.")

if __name__ == "__main__":
    main()