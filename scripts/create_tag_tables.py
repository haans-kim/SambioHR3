"""
태그 시스템 관련 테이블 생성 스크립트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from src.database.tag_schema import Base, TagMaster, ActivityStates
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_url():
    """데이터베이스 URL 반환"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'sambio_human.db')
    return f'sqlite:///{db_path}'

def create_tables():
    """태그 관련 테이블 생성"""
    try:
        # 데이터베이스 연결
        engine = create_engine(get_db_url())
        
        # 테이블 생성
        Base.metadata.create_all(engine)
        logger.info("태그 관련 테이블 생성 완료")
        
        return True
        
    except Exception as e:
        logger.error(f"테이블 생성 중 오류 발생: {e}")
        return False

def insert_initial_data(engine):
    """초기 데이터 삽입"""
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # 태그 마스터 데이터
        tag_data = [
            # G 그룹 - 업무 관련
            {"tag_code": "G1", "tag_name": "주업무 공간", "tag_category": "G", 
             "description": "주업무 수행하는 공간 (타 유형으로 분류되지 않는 모든 대강 지점)"},
            {"tag_code": "G2", "tag_name": "작업 준비 공간", "tag_category": "G", 
             "description": "작업 전 준비 수행 공간 (락커, locker, 가우닝, gowning, 탈의, 경의, 파우더)"},
            {"tag_code": "G3", "tag_name": "회의/협업 공간", "tag_category": "G", 
             "description": "회의 등 협업이 주로 이루어지는 공식 공간 (회의, meeting)"},
            {"tag_code": "G4", "tag_name": "교육 공간", "tag_category": "G", 
             "description": "정기/비정기 교육이 이루어지는 공간 (교육, 강의, 감성, univ)"},
            
            # N 그룹 - 비업무 관련
            {"tag_code": "N1", "tag_name": "휴게 공간", "tag_category": "N", 
             "description": "휴식, 외부 등이 주로 이루어지는 공간 (휴게, 모성, 대기, 수면, 탐배)"},
            {"tag_code": "N2", "tag_name": "복지/편의시설", "tag_category": "N", 
             "description": "키워드 명령한 복지시설 또는 편의시설 (메디컬, 약국, 휘트니스, 마용실, 세탁소, 나눔)"},
            
            # T 그룹 - 이동 관련
            {"tag_code": "T1", "tag_name": "이동 공간", "tag_category": "T", 
             "description": "공간 간 연결을 위한 복도/계단 등 (복도, 브릿지, 계단, 연결통로)"},
            {"tag_code": "T2", "tag_name": "1선 입문", "tag_category": "T", 
             "description": "1선으로 지정된 태그 지점 입문"},
            {"tag_code": "T3", "tag_name": "1선 출문", "tag_category": "T", 
             "description": "1선으로 지정된 태그 지점 출문"},
            
            # M 그룹 - 식사 관련
            {"tag_code": "M1", "tag_name": "바이오플라자 식사", "tag_category": "M", 
             "description": "별도 빌딩 내 식당에서 식사"},
            {"tag_code": "M2", "tag_name": "바이오플라자 테이크아웃", "tag_category": "M", 
             "description": "별도 빌딩에서 음식 구매 (테이크아웃)"},
            
            # O 그룹 - 실제 업무
            {"tag_code": "O", "tag_name": "실제 업무 로그", "tag_category": "O", 
             "description": "기계조작, 컴퓨터 사용 등 실제 업무 활동 로그"}
        ]
        
        for tag in tag_data:
            if not session.query(TagMaster).filter_by(tag_code=tag['tag_code']).first():
                session.add(TagMaster(**tag))
        
        # 활동 상태 데이터
        state_data = [
            {"state_code": "WORK", "state_name": "업무", "state_category": "work",
             "description": "실제 업무 수행 상태", "color_code": "#4CAF50", "is_work_time": True, "display_order": 1},
            {"state_code": "WORK_CONFIRMED", "state_name": "업무(확실)", "state_category": "work",
             "description": "O 태그로 확정된 업무 상태", "color_code": "#2E7D32", "is_work_time": True, "display_order": 2},
            {"state_code": "PREPARATION", "state_name": "준비", "state_category": "work",
             "description": "업무 준비 또는 정리 상태", "color_code": "#81C784", "is_work_time": True, "display_order": 3},
            {"state_code": "MEETING", "state_name": "회의", "state_category": "work",
             "description": "회의 및 협업 상태", "color_code": "#2196F3", "is_work_time": True, "display_order": 4},
            {"state_code": "EDUCATION", "state_name": "교육", "state_category": "work",
             "description": "교육 참석 상태", "color_code": "#03A9F4", "is_work_time": True, "display_order": 5},
            {"state_code": "REST", "state_name": "휴게", "state_category": "rest",
             "description": "휴식 상태 (식사 제외)", "color_code": "#FFC107", "is_work_time": False, "display_order": 6},
            {"state_code": "MEAL", "state_name": "식사", "state_category": "meal",
             "description": "식사 상태", "color_code": "#FF9800", "is_work_time": False, "display_order": 7},
            {"state_code": "TRANSIT", "state_name": "경유", "state_category": "movement",
             "description": "단순 이동/통과", "color_code": "#9E9E9E", "is_work_time": False, "display_order": 8},
            {"state_code": "ENTRY", "state_name": "출입(IN)", "state_category": "movement",
             "description": "출근/입실", "color_code": "#4CAF50", "is_work_time": False, "display_order": 9},
            {"state_code": "EXIT", "state_name": "출입(OUT)", "state_category": "movement",
             "description": "퇴근/퇴실", "color_code": "#F44336", "is_work_time": False, "display_order": 10},
            {"state_code": "NON_WORK", "state_name": "비업무", "state_category": "rest",
             "description": "외출 및 기타 활동", "color_code": "#E91E63", "is_work_time": False, "display_order": 11}
        ]
        
        for state in state_data:
            if not session.query(ActivityStates).filter_by(state_code=state['state_code']).first():
                session.add(ActivityStates(**state))
        
        session.commit()
        logger.info("초기 데이터 삽입 완료")
        
    except Exception as e:
        session.rollback()
        logger.error(f"초기 데이터 삽입 중 오류: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    # 테이블 생성
    if create_tables():
        # 초기 데이터 삽입
        engine = create_engine(get_db_url())
        insert_initial_data(engine)
        logger.info("태그 시스템 초기화 완료")