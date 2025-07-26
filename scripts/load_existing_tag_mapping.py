"""
기존 태그 위치 마스터 데이터를 데이터베이스에 로드
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pickle
import gzip
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.tag_schema import LocationTagMapping
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_url():
    """데이터베이스 URL 반환"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'sambio_human.db')
    return f'sqlite:///{db_path}'

def load_tag_location_master():
    """기존 태그 위치 마스터 파일 로드"""
    file_path = 'data/pickles/tag_location_master_v20250721_171717.pkl.gz'
    
    logger.info(f"태그 위치 마스터 파일 로드 중: {file_path}")
    with gzip.open(file_path, 'rb') as f:
        data = pickle.load(f)
    
    logger.info(f"총 {len(data)}개 레코드 로드됨")
    logger.info(f"컬럼: {list(data.columns)}")
    
    # Tag_Code 분포 확인
    logger.info("\nTag_Code 분포:")
    tag_counts = data['Tag_Code'].value_counts()
    for tag, count in tag_counts.items():
        logger.info(f"  {tag}: {count}개")
    
    return data

def update_location_mappings(data):
    """데이터베이스에 위치-태그 매핑 업데이트"""
    engine = create_engine(get_db_url())
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # 기존 매핑 삭제
        session.query(LocationTagMapping).delete()
        
        # 새 매핑 추가
        unique_mappings = data.groupby(['위치', 'Tag_Code']).first().reset_index()
        
        for _, row in unique_mappings.iterrows():
            mapping = LocationTagMapping(
                location_code=row['위치'],
                location_name=row.get('게이트명', ''),
                tag_code=row['Tag_Code'],
                mapping_confidence=1.0,
                mapping_rule=f"기존 마스터 데이터 - {row.get('라벨링_활동', '')}"
            )
            session.add(mapping)
        
        session.commit()
        logger.info(f"\n{len(unique_mappings)}개 위치-태그 매핑 저장 완료")
        
        # M1, M2 태그 확인 (식사 관련)
        logger.info("\n식사 관련 태그 처리:")
        logger.info("기존 마스터에는 M1, M2 태그가 없음")
        logger.info("CAFETERIA 위치를 M1으로 추가 매핑 필요")
        
        # CAFETERIA 위치 찾기
        cafeteria_locations = data[data['게이트명'].str.contains('CAFETERIA|카페테리아|식당', case=False, na=False)]
        if len(cafeteria_locations) > 0:
            logger.info(f"\n{len(cafeteria_locations)}개 CAFETERIA 위치 발견")
            for _, row in cafeteria_locations.head(10).iterrows():
                logger.info(f"  {row['위치']} - {row['게이트명']}")
        
    except Exception as e:
        session.rollback()
        logger.error(f"매핑 업데이트 중 오류: {e}")
        raise
    finally:
        session.close()

def analyze_activity_labels(data):
    """라벨링_활동 분석"""
    logger.info("\n=== 라벨링_활동 분석 ===")
    
    # 고유한 활동 라벨 추출
    all_activities = []
    for activities in data['라벨링_활동'].dropna():
        activities_list = [a.strip() for a in activities.split(',')]
        all_activities.extend(activities_list)
    
    # 활동 빈도 계산
    from collections import Counter
    activity_counts = Counter(all_activities)
    
    logger.info("\n활동 라벨 빈도:")
    for activity, count in activity_counts.most_common():
        logger.info(f"  {activity}: {count}회")
    
    # Tag_Code별 주요 활동
    logger.info("\nTag_Code별 주요 활동:")
    for tag_code in sorted(data['Tag_Code'].unique()):
        tag_data = data[data['Tag_Code'] == tag_code]
        activities = []
        for act in tag_data['라벨링_활동'].dropna():
            activities.extend([a.strip() for a in act.split(',')])
        
        if activities:
            activity_counter = Counter(activities)
            top_activities = [f"{act}({cnt})" for act, cnt in activity_counter.most_common(3)]
            logger.info(f"  {tag_code}: {', '.join(top_activities)}")

if __name__ == "__main__":
    # 태그 위치 마스터 로드
    data = load_tag_location_master()
    
    # 활동 라벨 분석
    analyze_activity_labels(data)
    
    # 데이터베이스 업데이트
    update_location_mappings(data)
    
    logger.info("\n=== 기존 태그 매핑 로드 완료 ===")