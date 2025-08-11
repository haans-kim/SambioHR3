"""
위치 정보를 태그 코드로 매핑하는 모듈
"""

import re
import logging
from typing import Dict, Optional, List, Tuple
from datetime import datetime
import pandas as pd
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class TagMapper:
    """위치 정보를 태그로 매핑하는 클래스"""
    
    def __init__(self, session: Session = None):
        self.session = session
        self.mapping_rules = self._initialize_mapping_rules()
        self.location_cache = {}
        
    def _initialize_mapping_rules(self) -> List[Tuple[str, str, List[str]]]:
        """매핑 규칙 초기화"""
        # (태그코드, 설명, 키워드 리스트)
        rules = [
            # G 그룹 - 업무 관련
            ("G2", "작업 준비 공간", ["락커", "locker", "가우닝", "gowning", "탈의", "경의", "파우더", "로커", "준비실"]),
            ("G3", "회의/협업 공간", ["회의", "meeting", "미팅", "컨퍼런스", "세미나", "협업"]),
            ("G4", "교육 공간", ["교육", "강의", "감성", "univ", "대학", "training", "트레이닝", "강당"]),
            
            # N 그룹 - 비업무 관련
            ("N1", "휴게 공간", ["휴게", "모성", "대기", "수면", "탐배", "흡연", "쉼터", "라운지", "로비"]),
            ("N2", "복지/편의시설", ["메디컬", "약국", "휘트니스", "피트니스", "마용실", "세탁소", "나눔", "헬스", "의무실", "편의점"]),
            
            # T 그룹 - 이동 관련
            ("T1", "이동 공간", ["복도", "브릿지", "계단", "연결통로", "통로", "엘리베이터", "홀", "corridor"]),
            ("T2", "1선 입문", ["입문", "입구", "게이트", "정문", "entrance", "main gate"]),
            ("T3", "1선 출문", ["출문", "출구", "exit", "후문"]),
            
            # M 그룹 - 식사 관련
            ("M1", "바이오플라자 식사", ["바이오플라자", "구내식당", "cafeteria", "카페테리아", "식당"]),
            ("M2", "바이오플라자 테이크아웃", ["테이크아웃", "take out", "포장", "매점"]),
            
            # G1은 기본값 - 다른 태그에 매핑되지 않는 모든 업무 공간
            ("G1", "주업무 공간", [])
        ]
        
        return rules
    
    def map_location_to_tag(self, location_code: str, location_name: str = None) -> str:
        """위치 정보를 태그 코드로 매핑"""
        # 캐시 확인
        cache_key = f"{location_code}_{location_name}"
        if cache_key in self.location_cache:
            return self.location_cache[cache_key]
        
        # 위치명이 없으면 위치코드 사용
        search_text = (location_name or location_code).lower()
        
        # 규칙 기반 매핑
        for tag_code, description, keywords in self.mapping_rules:
            if tag_code == "G1":  # G1은 기본값이므로 스킵
                continue
                
            for keyword in keywords:
                if keyword.lower() in search_text:
                    # Location mapped to tag - removed debug logging
                    self.location_cache[cache_key] = tag_code
                    return tag_code
        
        # 특수 패턴 확인
        tag = self._check_special_patterns(location_code, search_text)
        if tag:
            self.location_cache[cache_key] = tag
            return tag
        
        # 기본값은 G1 (주업무 공간)
        # Location mapped to default tag G1 - removed debug logging
        self.location_cache[cache_key] = "G1"
        return "G1"
    
    def _check_special_patterns(self, location_code: str, location_name: str) -> Optional[str]:
        """특수 패턴 확인"""
        # 1선 출입문 패턴
        if re.match(r'^(1선|1F|1ST)', location_code, re.IGNORECASE):
            if '입' in location_name or 'in' in location_name.lower():
                return "T2"
            elif '출' in location_name or 'out' in location_name.lower():
                return "T3"
        
        # 층간 이동 패턴
        if re.search(r'\dF|\d층', location_code) and ('이동' in location_name or '통로' in location_name):
            return "T1"
        
        # 회의실 패턴
        if re.search(r'(MR|CR|회의실)\d*', location_code, re.IGNORECASE):
            return "G3"
        
        # 휴게실 패턴
        if re.search(r'(휴게|REST|R&R)', location_code, re.IGNORECASE):
            return "N1"
        
        return None
    
    def batch_map_locations(self, locations: pd.DataFrame) -> pd.DataFrame:
        """DataFrame의 위치 정보를 일괄 매핑"""
        # 컬럼명 확인 및 조정
        if 'location_code' in locations.columns:
            dr_no_col = 'location_code'
            dr_nm_col = 'location_name'
        elif 'DR_NO' in locations.columns:
            dr_no_col = 'DR_NO'
            dr_nm_col = 'DR_NM'
        else:
            raise ValueError("DataFrame에 'DR_NO' 또는 'location_code' 컬럼이 필요합니다.")
        
        # 태그 매핑
        locations['tag_code'] = locations.apply(
            lambda row: self.map_location_to_tag(
                row[dr_no_col], 
                row.get(dr_nm_col, '')
            ), 
            axis=1
        )
        
        return locations
    
    def save_mappings_to_db(self, mappings: Dict[str, str], confidence: float = 1.0):
        """매핑 결과를 데이터베이스에 저장"""
        if not self.session:
            logger.error("데이터베이스 세션이 없습니다.")
            return
        
        from src.database.tag_schema import LocationTagMapping
        
        try:
            for location_code, tag_code in mappings.items():
                # 기존 매핑 확인
                existing = self.session.query(LocationTagMapping).filter_by(
                    location_code=location_code
                ).first()
                
                if existing:
                    existing.tag_code = tag_code
                    existing.mapping_confidence = confidence
                    existing.updated_at = datetime.utcnow()
                else:
                    mapping = LocationTagMapping(
                        location_code=location_code,
                        tag_code=tag_code,
                        mapping_confidence=confidence
                    )
                    self.session.add(mapping)
            
            self.session.commit()
            logger.info(f"{len(mappings)}개 위치-태그 매핑 저장 완료")
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"매핑 저장 중 오류: {e}")
            raise
    
    def get_o_tag_sources(self) -> List[str]:
        """O 태그 소스 정보 반환"""
        # O 태그는 실제 업무 수행 로그에서 추출
        return [
            "ABC_ACTIVITY_DATA",  # ABC 작업 데이터
            "EQUIPMENT_LOG",      # 장비 조작 로그
            "SYSTEM_ACCESS_LOG",  # 시스템 접근 로그
            "PC_LOGIN_LOG"        # PC 로그인 로그
        ]
    
    def map_activity_to_o_tag(self, activity_data: Dict) -> bool:
        """활동 데이터가 O 태그에 해당하는지 판단"""
        # ABC 활동 데이터가 있으면 O 태그
        if activity_data.get('activity_classification'):
            return True
        
        # 장비 조작 로그가 있으면 O 태그
        if activity_data.get('equipment_operation'):
            return True
        
        # PC 사용 로그가 있으면 O 태그
        if activity_data.get('pc_usage'):
            return True
        
        return False
    
    def get_mapping_statistics(self) -> Dict[str, int]:
        """매핑 통계 반환"""
        stats = {tag_code: 0 for tag_code, _, _ in self.mapping_rules}
        stats['G1'] = 0  # 기본값 추가
        
        for location, tag in self.location_cache.items():
            stats[tag] = stats.get(tag, 0) + 1
        
        return stats