"""
기존 태그 매핑의 문제점을 수정하고 M1, M2, O 태그 추가
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.database.tag_schema import LocationTagMapping, TagMaster
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_url():
    """데이터베이스 URL 반환"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'sambio_human.db')
    return f'sqlite:///{db_path}'

def add_missing_tags():
    """누락된 M1, M2, O 태그 추가"""
    engine = create_engine(get_db_url())
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # M1, M2, O 태그 확인 및 추가
        missing_tags = [
            {"tag_code": "M1", "tag_name": "바이오플라자 식사", "tag_category": "M", 
             "description": "별도 빌딩 내 식당에서 식사"},
            {"tag_code": "M2", "tag_name": "바이오플라자 테이크아웃", "tag_category": "M", 
             "description": "별도 빌딩에서 음식 구매 (테이크아웃)"},
            {"tag_code": "O", "tag_name": "실제 업무 로그", "tag_category": "O", 
             "description": "기계조작, 컴퓨터 사용 등 실제 업무 활동 로그"}
        ]
        
        for tag_data in missing_tags:
            existing = session.query(TagMaster).filter_by(tag_code=tag_data['tag_code']).first()
            if not existing:
                session.add(TagMaster(**tag_data))
                logger.info(f"태그 추가: {tag_data['tag_code']} - {tag_data['tag_name']}")
        
        session.commit()
        
    except Exception as e:
        session.rollback()
        logger.error(f"태그 추가 중 오류: {e}")
        raise
    finally:
        session.close()

def update_cafeteria_mappings():
    """CAFETERIA 관련 위치를 M1 태그로 업데이트"""
    engine = create_engine(get_db_url())
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # CAFETERIA 키워드가 포함된 위치 찾기
        cafeteria_keywords = ['CAFETERIA', '카페테리아', '식당', '바이오플라자']
        
        updated_count = 0
        for keyword in cafeteria_keywords:
            mappings = session.query(LocationTagMapping).filter(
                LocationTagMapping.location_name.like(f'%{keyword}%')
            ).all()
            
            for mapping in mappings:
                old_tag = mapping.tag_code
                mapping.tag_code = 'M1'
                mapping.mapping_rule = f"CAFETERIA 위치 - {keyword} 키워드 매칭"
                updated_count += 1
                logger.info(f"업데이트: {mapping.location_code} ({mapping.location_name}) : {old_tag} -> M1")
        
        session.commit()
        logger.info(f"\n총 {updated_count}개 CAFETERIA 위치를 M1 태그로 업데이트")
        
    except Exception as e:
        session.rollback()
        logger.error(f"CAFETERIA 매핑 업데이트 중 오류: {e}")
        raise
    finally:
        session.close()

def fix_activity_labels():
    """잘못된 활동 라벨 수정"""
    engine = create_engine(get_db_url())
    
    # 태그별 올바른 활동 정의
    tag_activities = {
        'G1': '업무',
        'G2': '준비',
        'G3': '회의',
        'G4': '교육',
        'N1': '휴게',
        'N2': '휴게',
        'T1': '경유',
        'T2': '출입(IN)',
        'T3': '출입(OUT)',
        'M1': '식사',
        'M2': '경유'
    }
    
    logger.info("\n=== 활동 라벨 수정 ===")
    
    with engine.connect() as conn:
        for tag_code, activity in tag_activities.items():
            query = text("""
                UPDATE location_tag_mapping
                SET mapping_rule = :activity
                WHERE tag_code = :tag_code
            """)
            
            result = conn.execute(query, {'activity': activity, 'tag_code': tag_code})
            conn.commit()
            logger.info(f"{tag_code} 태그의 활동을 '{activity}'로 수정 ({result.rowcount}개)")

def create_o_tag_sources():
    """O 태그 소스 테이블 생성 (ABC 활동 데이터 기반)"""
    engine = create_engine(get_db_url())
    
    # O 태그 소스 테이블 생성
    create_table_query = """
    CREATE TABLE IF NOT EXISTS o_tag_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_type VARCHAR(50) NOT NULL,
        source_table VARCHAR(100) NOT NULL,
        source_column VARCHAR(100),
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    
    with engine.connect() as conn:
        conn.execute(text(create_table_query))
        conn.commit()
        
        # O 태그 소스 추가
        sources = [
            ('abc_activity', 'abc_activity_data', 'activity_classification'),
            ('equipment_log', 'equipment_operation_log', 'operation_type'),
            ('system_access', 'system_access_log', 'access_type'),
            ('pc_login', 'pc_login_log', 'login_type')
        ]
        
        for source_type, table, column in sources:
            query = text("""
                INSERT OR IGNORE INTO o_tag_sources (source_type, source_table, source_column)
                VALUES (:source_type, :source_table, :source_column)
            """)
            conn.execute(query, {
                'source_type': source_type,
                'source_table': table,
                'source_column': column
            })
        conn.commit()
        
    logger.info("\nO 태그 소스 테이블 생성 완료")

def show_final_statistics():
    """최종 태그 매핑 통계"""
    engine = create_engine(get_db_url())
    
    with engine.connect() as conn:
        # 태그별 매핑 수
        query = text("""
            SELECT tag_code, COUNT(*) as count
            FROM location_tag_mapping
            GROUP BY tag_code
            ORDER BY count DESC
        """)
        
        result = conn.execute(query)
        
        logger.info("\n=== 최종 태그 매핑 통계 ===")
        total = 0
        for row in result:
            logger.info(f"  {row.tag_code}: {row.count}개")
            total += row.count
        logger.info(f"  총계: {total}개")
        
        # 태그 마스터 확인
        query = text("""
            SELECT tag_code, tag_name, tag_category
            FROM tag_master
            ORDER BY tag_category, tag_code
        """)
        
        result = conn.execute(query)
        
        logger.info("\n=== 태그 마스터 ===")
        for row in result:
            logger.info(f"  {row.tag_code} ({row.tag_category}): {row.tag_name}")

if __name__ == "__main__":
    # 누락된 태그 추가
    add_missing_tags()
    
    # CAFETERIA 위치 M1 태그로 업데이트
    update_cafeteria_mappings()
    
    # 활동 라벨 수정
    fix_activity_labels()
    
    # O 태그 소스 테이블 생성
    create_o_tag_sources()
    
    # 최종 통계
    show_final_statistics()
    
    logger.info("\n=== 태그 매핑 수정 완료 ===")