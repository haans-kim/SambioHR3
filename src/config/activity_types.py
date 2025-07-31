"""
활동 타입 정의 및 분류 체계
확장 가능한 구조로 설계
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import time

@dataclass
class ActivityType:
    """활동 타입 정의"""
    code: str  # 활동 코드 (예: WORK, FOCUS_WORK)
    name_ko: str  # 한글명
    name_en: str  # 영문명
    category: str  # 대분류 (work, meal, movement, etc.)
    color: str  # 표시 색상
    priority: int  # 우선순위 (겹칠 때 어떤 것을 우선할지)
    keywords: List[str] = None  # 관련 키워드
    time_windows: List[Tuple[time, time]] = None  # 해당 활동이 일어날 수 있는 시간대
    location_patterns: List[str] = None  # 위치 패턴
    min_duration: int = 5  # 최소 지속시간(분)

# 활동 타입 정의
ACTIVITY_TYPES = {
    # 근무 관련
    'WORK': ActivityType(
        code='WORK',
        name_ko='근무',
        name_en='Work',
        category='work',
        color='#2E86AB',
        priority=50,
        keywords=['작업', '업무', 'WORK'],
        location_patterns=['WORK_AREA', '작업장']
    ),
    'FOCUSED_WORK': ActivityType(
        code='FOCUSED_WORK',
        name_ko='집중근무',
        name_en='Focused Work',
        category='work',
        color='#1565C0',  # 진한 파란색
        priority=60,
        keywords=['집중', 'FOCUS'],
        min_duration=30
    ),
    'EQUIPMENT_OPERATION': ActivityType(
        code='EQUIPMENT_OPERATION',
        name_ko='장비조작',
        name_en='Equipment Operation',
        category='work',
        color='#9C27B0',  # 보라색
        priority=55,
        keywords=['장비', '기계', 'EQUIPMENT', 'MACHINE'],
        location_patterns=['EQUIPMENT', '장비실']
    ),
    'O_TAG_WORK': ActivityType(
        code='O_TAG_WORK',
        name_ko='O태그작업',
        name_en='O Tag Work',
        category='work',
        color='#3F51B5',  # 남색
        priority=55,
        keywords=['O태그', 'O_TAG'],
        location_patterns=['O_TAG']
    ),
    'WORK_PREPARATION': ActivityType(
        code='WORK_PREPARATION',
        name_ko='작업준비',
        name_en='Work Preparation',
        category='work',
        color='#00BCD4',  # 청록색
        priority=45,
        keywords=['준비', 'PREP', 'SETUP'],
        location_patterns=['PREP_AREA', '준비실']
    ),
    'WORKING': ActivityType(
        code='WORKING',
        name_ko='작업중',
        name_en='Working',
        category='work',
        color='#2196F3',  # 파란색
        priority=52,
        keywords=['작업중', 'WORKING', 'IN_PROGRESS']
    ),
    
    # 회의
    'MEETING': ActivityType(
        code='MEETING',
        name_ko='회의',
        name_en='Meeting',
        category='meeting',
        color='#E91E63',  # 분홍색
        priority=70,
        keywords=['회의', 'MEETING', 'CONFERENCE'],
        location_patterns=['MEETING', '회의실', 'CONFERENCE']
    ),
    'G3_MEETING': ActivityType(
        code='G3_MEETING',
        name_ko='G3회의',
        name_en='G3 Meeting',
        category='meeting',
        color='#7B1FA2',  # 진한 보라색
        priority=80,
        keywords=['G3회의', 'Knox PIMS', 'PIMS'],
        location_patterns=['G3_KNOX_PIMS']
    ),
    
    # Knox/Equipment 시스템 작업
    'KNOX_APPROVAL': ActivityType(
        code='KNOX_APPROVAL',
        name_ko='결재업무',
        name_en='Knox Approval',
        category='work',
        color='#8E24AA',  # 보라색
        priority=70,
        keywords=['결재', 'APPROVAL', 'Knox결재'],
        location_patterns=['KNOX_APPROVAL']
    ),
    'KNOX_MAIL': ActivityType(
        code='KNOX_MAIL',
        name_ko='메일업무',
        name_en='Knox Mail',
        category='work',
        color='#AB47BC',  # 보라색
        priority=70,
        keywords=['메일', 'MAIL', 'Knox메일'],
        location_patterns=['KNOX_MAIL']
    ),
    'EAM_WORK': ActivityType(
        code='EAM_WORK',
        name_ko='안전설비',
        name_en='EAM Work',
        category='work',
        color='#009688',  # 청록색
        priority=55,
        keywords=['EAM', '안전설비', '설비점검'],
        location_patterns=['EAM']
    ),
    'LAMS_WORK': ActivityType(
        code='LAMS_WORK',
        name_ko='품질시스템',
        name_en='LAMS Work',
        category='work',
        color='#00ACC1',  # 밝은 청록색
        priority=55,
        keywords=['LAMS', '품질', '품질시스템'],
        location_patterns=['LAMS']
    ),
    'MES_WORK': ActivityType(
        code='MES_WORK',
        name_ko='생산시스템',
        name_en='MES Work',
        category='work',
        color='#00897B',  # 진한 청록색
        priority=55,
        keywords=['MES', '생산', '생산시스템'],
        location_patterns=['MES']
    ),
    
    # 이동
    'MOVEMENT': ActivityType(
        code='MOVEMENT',
        name_ko='이동',
        name_en='Movement',
        category='movement',
        color='#795548',  # 갈색
        priority=30,
        keywords=['이동', 'MOVE', 'CORRIDOR', '복도'],
        location_patterns=['CORRIDOR', '통로', 'GATE']
    ),
    'COMMUTE_IN': ActivityType(
        code='COMMUTE_IN',
        name_ko='출근',
        name_en='Commute In',
        category='movement',
        color='#4CAF50',  # 녹색
        priority=80,
        keywords=['출근', 'ENTRANCE', 'GATE_IN'],
        time_windows=[(time(6, 0), time(10, 0)), (time(18, 0), time(22, 0))],  # 주간/야간
        location_patterns=['MAIN_GATE', '정문', 'ENTRANCE']
    ),
    'COMMUTE_OUT': ActivityType(
        code='COMMUTE_OUT',
        name_ko='퇴근',
        name_en='Commute Out',
        category='movement',
        color='#F44336',  # 빨간색
        priority=80,
        keywords=['퇴근', 'EXIT', 'GATE_OUT'],
        time_windows=[(time(16, 0), time(20, 0)), (time(4, 0), time(8, 0))],  # 주간/야간
        location_patterns=['MAIN_GATE', '정문', 'EXIT']
    ),
    
    # 식사 (세분화)
    'BREAKFAST': ActivityType(
        code='BREAKFAST',
        name_ko='조식',
        name_en='Breakfast',
        category='meal',
        color='#FFD700',  # 금색
        priority=65,
        keywords=['조식', '아침', 'BREAKFAST'],
        time_windows=[(time(6, 30), time(9, 0))],
        location_patterns=['CAFETERIA', '식당', '구내식당'],
        min_duration=15
    ),
    'LUNCH': ActivityType(
        code='LUNCH',
        name_ko='중식',
        name_en='Lunch',
        category='meal',
        color='#FFC107',  # 황색
        priority=65,
        keywords=['중식', '점심', 'LUNCH'],
        time_windows=[(time(11, 20), time(13, 20))],
        location_patterns=['CAFETERIA', '식당', '구내식당'],
        min_duration=20
    ),
    'DINNER': ActivityType(
        code='DINNER',
        name_ko='석식',
        name_en='Dinner',
        category='meal',
        color='#FFB300',  # 진한 황색
        priority=65,
        keywords=['석식', '저녁', 'DINNER'],
        time_windows=[(time(17, 0), time(20, 0))],
        location_patterns=['CAFETERIA', '식당', '구내식당'],
        min_duration=20
    ),
    'MIDNIGHT_MEAL': ActivityType(
        code='MIDNIGHT_MEAL',
        name_ko='야식',
        name_en='Midnight Meal',
        category='meal',
        color='#FF9800',  # 주황색
        priority=65,
        keywords=['야식', '야간식사', 'MIDNIGHT'],
        time_windows=[(time(23, 30), time(1, 0))],
        location_patterns=['CAFETERIA', '식당', '구내식당'],
        min_duration=15
    ),
    
    # 휴식 및 기타
    'REST': ActivityType(
        code='REST',
        name_ko='휴식',
        name_en='Rest',
        category='rest',
        color='#4CAF50',
        priority=40,
        keywords=['휴식', '휴게', 'REST', 'BREAK'],
        location_patterns=['REST_AREA', '휴게실', 'LOUNGE']
    ),
    'FITNESS': ActivityType(
        code='FITNESS',
        name_ko='피트니스',
        name_en='Fitness',
        category='rest',
        color='#8BC34A',  # 연두색
        priority=50,
        keywords=['운동', '피트니스', 'FITNESS', 'GYM', '체력단련'],
        location_patterns=['FITNESS', 'GYM', '체력단련실', '운동실'],
        min_duration=20
    ),
    'NON_WORK': ActivityType(
        code='NON_WORK',
        name_ko='비근무',
        name_en='Non-Work',
        category='absence',
        color='#FF6B6B',  # 빨간색
        priority=85,
        keywords=['비근무', '외출', 'NON_WORK', 'OUT_OF_OFFICE'],
        min_duration=10
    ),
    'LEAVE': ActivityType(
        code='LEAVE',
        name_ko='연차',
        name_en='Leave',
        category='absence',
        color='#E0E0E0',
        priority=90,
        keywords=['연차', '휴가', 'LEAVE', 'VACATION']
    ),
    'IDLE': ActivityType(
        code='IDLE',
        name_ko='대기',
        name_en='Idle',
        category='other',
        color='#BDBDBD',
        priority=20,
        keywords=['대기', 'IDLE', 'WAIT']
    ),
    'UNKNOWN': ActivityType(
        code='UNKNOWN',
        name_ko='미분류',
        name_en='Unknown',
        category='other',
        color='#9E9E9E',
        priority=10
    )
}

# 카테고리별 색상 팔레트
CATEGORY_COLORS = {
    'work': '#2E86AB',      # 파란색 계열
    'meeting': '#A23B72',   # 보라색
    'movement': '#F18F01',  # 주황색
    'meal': '#C73E1D',      # 빨간색 계열
    'rest': '#4CAF50',      # 초록색
    'absence': '#E0E0E0',   # 회색
    'other': '#9E9E9E'      # 진한 회색
}

def get_activity_type(code: str) -> Optional[ActivityType]:
    """활동 코드로 ActivityType 객체 가져오기"""
    return ACTIVITY_TYPES.get(code)

def get_activity_color(code: str) -> str:
    """활동 코드로 색상 가져오기"""
    activity = get_activity_type(code)
    return activity.color if activity else '#9E9E9E'

def get_activity_name(code: str, lang: str = 'ko') -> str:
    """활동 코드로 이름 가져오기"""
    activity = get_activity_type(code)
    if not activity:
        return code
    return activity.name_ko if lang == 'ko' else activity.name_en

def get_activities_by_category(category: str) -> List[ActivityType]:
    """카테고리별 활동 목록 가져오기"""
    return [act for act in ACTIVITY_TYPES.values() if act.category == category]

def get_all_activity_codes() -> List[str]:
    """모든 활동 코드 목록"""
    return list(ACTIVITY_TYPES.keys())

def get_activity_mapping() -> Dict[str, str]:
    """활동 코드와 한글명 매핑"""
    return {code: act.name_ko for code, act in ACTIVITY_TYPES.items()}