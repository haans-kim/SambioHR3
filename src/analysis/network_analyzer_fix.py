"""
네트워크 분석기 GATE 버그 수정 패치
기존 get_building_from_location 함수의 로직 개선
"""

import re
from typing import Optional

class BuildingMapperFix:
    """건물 매핑 로직 수정"""
    
    @staticmethod
    def get_building_from_location(location: str, building_coords: dict) -> Optional[str]:
        """
        위치 문자열에서 건물 코드 추출 (GATE 처리 개선)
        
        주요 수정사항:
        1. GATE 관련 패턴을 더 정확하게 매칭
        2. 스피드게이트와 정문 구분 명확화
        3. 매핑 실패 케이스 로깅
        """
        if not location:
            return None
            
        location_upper = location.upper()
        location_lower = location.lower()
        
        # 1. 특수 케이스 먼저 처리
        # P4 2층브릿지 -> P4_GATE
        if 'P4' in location and ('2층브릿지' in location or '브릿지' in location_lower):
            return 'P4_GATE'
        
        # 2. 스피드게이트 패턴 (P3, P4 등)
        # "P4_생산동_SPEED GATE_OUT" 같은 패턴
        speed_gate_pattern = re.search(r'P(\d).*SPEED\s*GATE', location_upper)
        if speed_gate_pattern:
            building_num = speed_gate_pattern.group(1)
            return f'P{building_num}_GATE'
        
        # "P4 스피드게이트", "P4-스피드게이트" 같은 패턴
        if '스피드게이트' in location_lower or '스피드 게이트' in location_lower:
            p_pattern = re.search(r'P(\d)', location_upper)
            if p_pattern:
                building_num = p_pattern.group(1)
                return f'P{building_num}_GATE'
        
        # 3. 정문 패턴 처리
        if '정문' in location:
            # "P3 정문", "P4_정문" 등
            p_pattern = re.search(r'P(\d)', location_upper)
            if p_pattern:
                building_num = p_pattern.group(1)
                return f'P{building_num}_GATE'
            
            # "정문동" -> MAIN_GATE
            elif '정문동' in location:
                return 'MAIN_GATE'
            
            # 단독 "정문" -> MAIN_GATE
            else:
                return 'MAIN_GATE'
        
        # 4. GATE 키워드가 포함된 경우
        if 'GATE' in location_upper or '게이트' in location:
            # P 건물과 연관된 경우
            p_pattern = re.search(r'P(\d)', location_upper)
            if p_pattern:
                building_num = p_pattern.group(1)
                return f'P{building_num}_GATE'
            
            # 연관 건물이 없으면 MAIN_GATE
            else:
                return 'MAIN_GATE'
        
        # 5. BP 체크 (BP2_2F 같은 패턴을 P2로 오인하지 않도록 먼저 체크)
        if 'BP' in location_upper or 'B-P' in location_upper or '바이오플라자' in location_upper:
            return 'BP'
        
        # 6. 일반 P 건물 패턴 (GATE가 아닌 경우)
        # 이미 GATE 관련은 위에서 처리했으므로 일반 건물만
        p_building_pattern = re.search(r'P(\d)(?:[\s\-_]|$)', location_upper)
        if p_building_pattern:
            building_num = p_building_pattern.group(1)
            building_code = f'P{building_num}'
            
            # 좌표가 존재하는 건물인지 확인
            if building_code in building_coords:
                return building_code
        
        # 7. 기타 건물들
        if 'HARMONY' in location_upper or '하모니' in location:
            return 'HARMONY'
        elif '연구동' in location or 'RESEARCH' in location_upper:
            return '연구동'
        elif 'UTIL' in location_upper or '유틸' in location:
            return 'UTIL'
        elif '생산관리동' in location or '생산관리' in location:
            return '생산관리동'
        
        # 7. 매핑 실패 - 로깅
        # 실제 사용시에는 logger를 사용
        # logger.warning(f"건물 매핑 실패: {location}")
        
        return None


def patch_network_analyzer():
    """
    NetworkAnalyzer의 get_building_from_location 메서드를 패치
    
    사용법:
    from network_analyzer_fix import patch_network_analyzer
    patch_network_analyzer()
    """
    try:
        from src.analysis.network_analyzer import NetworkAnalyzer, BuildingMapper
        
        # 기존 메서드 백업
        BuildingMapper._original_get_building_from_location = BuildingMapper.get_building_from_location
        
        # 새 메서드로 교체
        @classmethod
        def new_get_building_from_location(cls, location: str) -> Optional[str]:
            return BuildingMapperFix.get_building_from_location(
                location, 
                cls.BUILDING_COORDS_PCT
            )
        
        BuildingMapper.get_building_from_location = new_get_building_from_location
        
        print("NetworkAnalyzer GATE 버그 패치 적용 완료")
        return True
        
    except Exception as e:
        print(f"패치 적용 실패: {e}")
        return False


# 테스트 케이스
def test_gate_mapping():
    """GATE 매핑 테스트"""
    test_cases = [
        # (입력, 기대값)
        ("P4_생산동_SPEED GATE_OUT", "P4_GATE"),
        ("P4 스피드게이트", "P4_GATE"),
        ("P4-스피드게이트", "P4_GATE"),
        ("P3 정문", "P3_GATE"),
        ("P4_정문", "P4_GATE"),
        ("정문동", "MAIN_GATE"),
        ("정문", "MAIN_GATE"),
        ("P4_생산동_2층브릿지", "P4_GATE"),
        ("P4 GATE", "P4_GATE"),
        ("P4_생산동_1F", "P4"),  # 일반 P4 건물
        ("BP2_2F", "BP"),
        ("바이오플라자", "BP"),
    ]
    
    # 더미 좌표 (테스트용)
    dummy_coords = {
        'P1': None, 'P2': None, 'P3': None, 'P4': None, 'P5': None,
        'P1_GATE': None, 'P2_GATE': None, 'P3_GATE': None, 
        'P4_GATE': None, 'P5_GATE': None, 'MAIN_GATE': None,
        'BP': None, 'HARMONY': None, '연구동': None
    }
    
    print("GATE 매핑 테스트 시작...")
    failed = 0
    
    for location, expected in test_cases:
        result = BuildingMapperFix.get_building_from_location(location, dummy_coords)
        if result != expected:
            print(f"❌ FAIL: '{location}' -> '{result}' (expected: '{expected}')")
            failed += 1
        else:
            print(f"✅ PASS: '{location}' -> '{result}'")
    
    print(f"\n테스트 완료: {len(test_cases) - failed}/{len(test_cases)} 성공")
    return failed == 0


if __name__ == "__main__":
    # 테스트 실행
    test_gate_mapping()