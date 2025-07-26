"""
상태 전환 규칙을 데이터베이스에 초기화하는 스크립트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.tag_schema import StateTransitionRules
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_url():
    """데이터베이스 URL 반환"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'sambio_human.db')
    return f'sqlite:///{db_path}'

def initialize_transition_rules():
    """전환 규칙 초기화"""
    engine = create_engine(get_db_url())
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # 기존 규칙 삭제
        session.query(StateTransitionRules).delete()
        
        # 전환 규칙 정의
        rules = [
            # O 태그 관련 규칙 (최우선)
            {"from_tag": "O", "to_tag": "O", "to_state": "WORK_CONFIRMED", 
             "base_probability": 0.98, "priority": 1},
            {"from_tag": "G1", "to_tag": "O", "to_state": "WORK_CONFIRMED", 
             "base_probability": 0.98, "priority": 1},
            {"from_tag": "O", "to_tag": "G1", "to_state": "WORK", 
             "base_probability": 0.95, "priority": 2},
            {"from_tag": "O", "to_tag": "M1", "to_state": "MEAL", 
             "base_probability": 1.0, "priority": 1},
            {"from_tag": "O", "to_tag": "T2", "to_state": "EXIT", 
             "base_probability": 0.9, "priority": 3},
            {"from_tag": "O", "to_tag": "T3", "to_state": "EXIT", 
             "base_probability": 0.9, "priority": 3},
            {"from_tag": "M1", "to_tag": "O", "to_state": "WORK", 
             "base_probability": 0.9, "priority": 2},
            
            # M 태그 관련 규칙 (식사 100% 확실)
            {"from_tag": "T1", "to_tag": "M1", "to_state": "MEAL", 
             "base_probability": 1.0, "priority": 1},
            {"from_tag": "T1", "to_tag": "M2", "to_state": "TRANSIT", 
             "base_probability": 1.0, "priority": 1},
            {"from_tag": "M1", "to_tag": "T1", "to_state": "TRANSIT", 
             "base_probability": 1.0, "priority": 2},
            {"from_tag": "M2", "to_tag": "T1", "to_state": "TRANSIT", 
             "base_probability": 1.0, "priority": 2},
            {"from_tag": "M2", "to_tag": "N2", "to_state": "REST", 
             "base_probability": 0.8, "priority": 3},
            
            # 출퇴근 패턴
            {"from_tag": "T2", "to_tag": "G2", "to_state": "PREPARATION", 
             "base_probability": 0.9, "priority": 10,
             "time_condition": {"start": "07:00", "end": "09:00"}},
            {"from_tag": "T2", "to_tag": "G1", "to_state": "WORK", 
             "base_probability": 0.8, "priority": 15},
            {"from_tag": "G1", "to_tag": "T3", "to_state": "EXIT", 
             "base_probability": 0.8, "priority": 15},
            {"from_tag": "G2", "to_tag": "T3", "to_state": "EXIT", 
             "base_probability": 0.9, "priority": 10},
            {"from_tag": "G1", "to_tag": "G2", "to_state": "PREPARATION", 
             "base_probability": 0.8, "priority": 20,
             "time_condition": {"start": "19:30", "end": "21:00"}},
            
            # 회의/교육 패턴
            {"from_tag": "G1", "to_tag": "G3", "to_state": "MEETING", 
             "base_probability": 0.9, "priority": 20},
            {"from_tag": "G3", "to_tag": "G3", "to_state": "MEETING", 
             "base_probability": 0.95, "priority": 15,
             "duration_condition": {"min": 10, "max": 180}},
            {"from_tag": "G1", "to_tag": "G4", "to_state": "EDUCATION", 
             "base_probability": 0.9, "priority": 20},
            {"from_tag": "G4", "to_tag": "G4", "to_state": "EDUCATION", 
             "base_probability": 0.95, "priority": 15,
             "duration_condition": {"min": 30, "max": 480}},
            {"from_tag": "G3", "to_tag": "G1", "to_state": "WORK", 
             "base_probability": 0.85, "priority": 25},
            {"from_tag": "G4", "to_tag": "G1", "to_state": "WORK", 
             "base_probability": 0.85, "priority": 25},
            
            # 휴게 패턴
            {"from_tag": "G1", "to_tag": "N1", "to_state": "REST", 
             "base_probability": 0.8, "priority": 30},
            {"from_tag": "N1", "to_tag": "N1", "to_state": "REST", 
             "base_probability": 0.9, "priority": 25,
             "duration_condition": {"max": 120}},
            {"from_tag": "G1", "to_tag": "N2", "to_state": "REST", 
             "base_probability": 0.7, "priority": 35},
            {"from_tag": "N1", "to_tag": "G1", "to_state": "WORK", 
             "base_probability": 0.8, "priority": 30},
            {"from_tag": "N2", "to_tag": "G1", "to_state": "WORK", 
             "base_probability": 0.7, "priority": 35},
            
            # 이동 패턴
            {"from_tag": "T1", "to_tag": "T1", "to_state": "TRANSIT", 
             "base_probability": 0.7, "priority": 40,
             "duration_condition": {"max": 30}},
            {"from_tag": "G1", "to_tag": "T1", "to_state": "TRANSIT", 
             "base_probability": 0.8, "priority": 40},
            {"from_tag": "T1", "to_tag": "G1", "to_state": "WORK", 
             "base_probability": 0.7, "priority": 40},
            
            # 재입문 패턴 (점심 외출 등)
            {"from_tag": "T3", "to_tag": "T2", "to_state": "ENTRY", 
             "base_probability": 0.9, "priority": 20,
             "duration_condition": {"min": 30, "max": 120}},
            
            # 식사 시간대 특수 패턴
            {"from_tag": "G1", "to_tag": "T1", "to_state": "TRANSIT", 
             "base_probability": 0.9, "priority": 15,
             "time_condition": {"start": "11:00", "end": "11:30"}},
            {"from_tag": "G1", "to_tag": "T1", "to_state": "TRANSIT", 
             "base_probability": 0.9, "priority": 15,
             "time_condition": {"start": "17:00", "end": "17:30"}},
            
            # 교대 인수인계 패턴
            {"from_tag": "G1", "to_tag": "G3", "to_state": "MEETING", 
             "base_probability": 0.95, "priority": 5,
             "time_condition": {"start": "07:30", "end": "08:30"}},
            {"from_tag": "G1", "to_tag": "G3", "to_state": "MEETING", 
             "base_probability": 0.95, "priority": 5,
             "time_condition": {"start": "19:30", "end": "20:30"}},
        ]
        
        # 규칙 저장
        for rule_data in rules:
            rule = StateTransitionRules(**rule_data)
            session.add(rule)
        
        session.commit()
        logger.info(f"{len(rules)}개 전환 규칙 초기화 완료")
        
        # 규칙 통계 출력
        logger.info("\n전환 규칙 요약:")
        from_tags = {}
        to_states = {}
        
        for rule in rules:
            from_tag = rule['from_tag']
            to_state = rule['to_state']
            
            from_tags[from_tag] = from_tags.get(from_tag, 0) + 1
            to_states[to_state] = to_states.get(to_state, 0) + 1
        
        logger.info("From 태그별 규칙 수:")
        for tag, count in sorted(from_tags.items()):
            logger.info(f"  {tag}: {count}개")
        
        logger.info("\nTo 상태별 규칙 수:")
        for state, count in sorted(to_states.items()):
            logger.info(f"  {state}: {count}개")
        
    except Exception as e:
        session.rollback()
        logger.error(f"전환 규칙 초기화 중 오류: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    initialize_transition_rules()