"""
기존 위치 데이터를 태그로 매핑하는 스크립트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import pandas as pd
import logging
from src.tag_system.tag_mapper import TagMapper
from src.database.tag_schema import LocationTagMapping
from collections import Counter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_url():
    """데이터베이스 URL 반환"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'sambio_human.db')
    return f'sqlite:///{db_path}'

def get_unique_locations():
    """데이터베이스에서 고유한 위치 정보 추출"""
    engine = create_engine(get_db_url())
    
    # tag_data 테이블에서 고유한 위치 정보 추출
    query = """
    SELECT DISTINCT 
        DR_NO as location_code,
        DR_NM as location_name,
        COUNT(*) as usage_count
    FROM tag_data
    WHERE DR_NO IS NOT NULL
    GROUP BY DR_NO, DR_NM
    ORDER BY usage_count DESC
    """
    
    with engine.connect() as conn:
        locations = pd.read_sql(text(query), conn)
    logger.info(f"총 {len(locations)}개의 고유 위치 발견")
    
    return locations

def map_and_save_locations():
    """위치 정보를 태그로 매핑하고 저장"""
    # 데이터베이스 세션 생성
    engine = create_engine(get_db_url())
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # TagMapper 인스턴스 생성
        mapper = TagMapper(session)
        
        # 고유 위치 정보 가져오기
        locations = get_unique_locations()
        
        # 태그 매핑
        logger.info("위치-태그 매핑 시작...")
        locations = mapper.batch_map_locations(locations)
        
        # 매핑 통계
        tag_counts = Counter(locations['tag_code'])
        logger.info("\n태그 매핑 통계:")
        for tag, count in sorted(tag_counts.items()):
            percentage = (count / len(locations)) * 100
            logger.info(f"  {tag}: {count}개 ({percentage:.1f}%)")
        
        # 매핑 결과 저장
        logger.info("\n데이터베이스에 매핑 결과 저장 중...")
        for _, row in locations.iterrows():
            existing = session.query(LocationTagMapping).filter_by(
                location_code=row['location_code']
            ).first()
            
            if existing:
                existing.tag_code = row['tag_code']
                existing.location_name = row.get('location_name', '')
                existing.mapping_confidence = 1.0
            else:
                mapping = LocationTagMapping(
                    location_code=row['location_code'],
                    location_name=row.get('location_name', ''),
                    tag_code=row['tag_code'],
                    mapping_confidence=1.0,
                    mapping_rule=f"자동 매핑 (사용빈도: {row['usage_count']})"
                )
                session.add(mapping)
        
        session.commit()
        logger.info(f"{len(locations)}개 위치-태그 매핑 저장 완료")
        
        # 매핑 결과 샘플 출력
        logger.info("\n매핑 결과 샘플 (상위 20개):")
        sample = locations.head(20)
        for _, row in sample.iterrows():
            logger.info(f"  {row['location_code']:20} | {row['location_name']:30} -> {row['tag_code']}")
        
        # CSV로 저장 (검토용)
        output_path = os.path.join(os.path.dirname(__file__), 'location_tag_mapping.csv')
        locations.to_csv(output_path, index=False, encoding='utf-8-sig')
        logger.info(f"\n매핑 결과를 CSV로 저장: {output_path}")
        
    except Exception as e:
        session.rollback()
        logger.error(f"매핑 중 오류 발생: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    map_and_save_locations()