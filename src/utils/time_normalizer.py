"""
시간 정규화 및 야간 근무 처리 시스템
UTC 기반 내부 처리와 야간 근무자 특수 케이스 처리
"""

import pytz
from datetime import datetime, time, timedelta, date
from typing import Optional, Tuple, List, Dict, Union
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ShiftType(Enum):
    """근무 유형"""
    DAY = "day"        # 주간 근무 (08:00-20:30)
    NIGHT = "night"    # 야간 근무 (20:00-08:30)
    OFFICE = "office"  # 사무직 (자율/탄력)
    

class MealType(Enum):
    """식사 유형"""
    BREAKFAST = "breakfast"  # 조식 06:30-09:00
    LUNCH = "lunch"         # 중식 11:20-13:20
    DINNER = "dinner"       # 석식 17:00-20:00
    MIDNIGHT = "midnight"   # 야식 23:30-01:00


class TimeNormalizer:
    """시간 정규화 및 야간 근무 처리"""
    
    def __init__(self, timezone: str = 'Asia/Seoul'):
        self.timezone = pytz.timezone(timezone)
        self.utc = pytz.UTC
        
        # 식사 시간대 정의 (로컬 시간 기준)
        self.meal_windows = {
            MealType.BREAKFAST: (time(6, 30), time(9, 0)),
            MealType.LUNCH: (time(11, 20), time(13, 20)),
            MealType.DINNER: (time(17, 0), time(20, 0)),
            MealType.MIDNIGHT: [(time(23, 30), time(23, 59)), 
                               (time(0, 0), time(1, 0))]  # 자정 넘는 케이스
        }
        
        # 교대 시간 정의
        self.shift_times = {
            ShiftType.DAY: {
                'start': time(8, 0),
                'end': time(20, 30),
                'entry_window': (time(7, 0), time(9, 0)),
                'exit_window': (time(19, 30), time(21, 30))
            },
            ShiftType.NIGHT: {
                'start': time(20, 0),
                'end': time(8, 30),
                'entry_window': (time(19, 0), time(21, 0)),
                'exit_window': (time(7, 30), time(9, 30))
            }
        }
    
    def normalize_to_utc(self, local_time: datetime) -> datetime:
        """로컬 시간을 UTC로 변환"""
        if local_time.tzinfo is None:
            # naive datetime인 경우 로컬 타임존 적용
            local_time = self.timezone.localize(local_time)
        return local_time.astimezone(self.utc)
    
    def utc_to_local(self, utc_time: datetime) -> datetime:
        """UTC를 로컬 시간으로 변환"""
        if utc_time.tzinfo is None:
            utc_time = self.utc.localize(utc_time)
        return utc_time.astimezone(self.timezone)
    
    def get_work_date(self, timestamp: datetime, shift_type: ShiftType) -> date:
        """
        근무 날짜 결정
        - 주간 근무: 해당 날짜
        - 야간 근무: 오전 시간(12시 이전)은 전날 근무로 간주
        """
        local_time = timestamp if timestamp.tzinfo else self.timezone.localize(timestamp)
        
        if shift_type == ShiftType.NIGHT and local_time.hour < 12:
            # 야간 근무자의 오전 시간은 전날 근무
            return (local_time - timedelta(days=1)).date()
        
        return local_time.date()
    
    def detect_shift_type(self, first_tag_time: datetime) -> ShiftType:
        """
        첫 태그 시간으로 근무 유형 자동 감지
        - 18시 이후 또는 6시 이전 첫 태그: 야간 근무
        - 그 외: 주간 근무
        """
        local_time = first_tag_time if first_tag_time.tzinfo else self.timezone.localize(first_tag_time)
        hour = local_time.hour
        
        if hour >= 18 or hour <= 6:  # 6시도 야간 근무에 포함
            return ShiftType.NIGHT
        elif 6 < hour < 18:
            return ShiftType.DAY
        else:
            return ShiftType.OFFICE
    
    def is_in_meal_window(self, timestamp: datetime, meal_type: MealType) -> bool:
        """식사 시간대 판별 (자정 넘는 경우 처리)"""
        local_time = timestamp if timestamp.tzinfo else self.timezone.localize(timestamp)
        current_time = local_time.time()
        
        windows = self.meal_windows[meal_type]
        
        # 단일 시간대
        if isinstance(windows, tuple):
            start, end = windows
            if start <= end:
                return start <= current_time <= end
            else:
                # 자정을 넘는 경우 (실제로는 발생하지 않음)
                return current_time >= start or current_time <= end
        
        # 다중 시간대 (야식의 경우)
        else:
            for start, end in windows:
                if start <= current_time <= end:
                    return True
            return False
    
    def get_current_meal_type(self, timestamp: datetime) -> Optional[MealType]:
        """현재 시간의 식사 유형 반환"""
        for meal_type in MealType:
            if self.is_in_meal_window(timestamp, meal_type):
                return meal_type
        return None
    
    def is_shift_change_time(self, timestamp: datetime) -> Tuple[bool, Optional[str]]:
        """
        교대 시간 여부 확인
        Returns: (is_shift_change, shift_direction)
        shift_direction: 'day_to_night', 'night_to_day', None
        """
        local_time = timestamp if timestamp.tzinfo else self.timezone.localize(timestamp)
        current_time = local_time.time()
        
        # 주간 → 야간 교대 (20:00-20:30)
        if time(20, 0) <= current_time <= time(20, 30):
            return True, 'day_to_night'
        
        # 야간 → 주간 교대 (08:00-08:30)
        elif time(8, 0) <= current_time <= time(8, 30):
            return True, 'night_to_day'
        
        return False, None
    
    def get_normalized_time_range(
        self, 
        date: date, 
        shift_type: ShiftType
    ) -> Tuple[datetime, datetime]:
        """
        특정 날짜의 근무 시간 범위 반환 (UTC)
        
        - 주간: 당일 05:00 ~ 당일 23:00 (KST)
        - 야간: 전날 17:00 ~ 당일 12:00 (KST)
        """
        if shift_type == ShiftType.DAY:
            # 주간 근무: 당일 05:00 ~ 23:00 KST
            start = datetime.combine(date, time(5, 0))
            end = datetime.combine(date, time(23, 0))
        elif shift_type == ShiftType.NIGHT:
            # 야간 근무: 전날 17:00 ~ 당일 12:00 KST
            start = datetime.combine(date - timedelta(days=1), time(17, 0))
            end = datetime.combine(date, time(12, 0))
        else:  # OFFICE
            # 사무직: 당일 00:00 ~ 23:59 KST
            start = datetime.combine(date, time(0, 0))
            end = datetime.combine(date, time(23, 59, 59))
        
        # 로컬 시간을 UTC로 변환
        start_utc = self.normalize_to_utc(self.timezone.localize(start))
        end_utc = self.normalize_to_utc(self.timezone.localize(end))
        
        return start_utc, end_utc
    
    def calculate_time_difference(
        self, 
        time1: datetime, 
        time2: datetime,
        handle_midnight: bool = True
    ) -> timedelta:
        """
        두 시간의 차이 계산 (자정 처리 포함)
        
        Args:
            time1: 이전 시간
            time2: 이후 시간
            handle_midnight: 자정 넘는 경우 처리 여부
        """
        # UTC로 정규화
        time1_utc = self.normalize_to_utc(time1) if time1.tzinfo != self.utc else time1
        time2_utc = self.normalize_to_utc(time2) if time2.tzinfo != self.utc else time2
        
        diff = time2_utc - time1_utc
        
        if handle_midnight and diff.total_seconds() < 0:
            # 음수인 경우 (자정을 넘었을 가능성)
            # 24시간을 더해서 재계산
            diff += timedelta(days=1)
        
        return diff
    
    def is_work_time(
        self, 
        timestamp: datetime, 
        shift_type: ShiftType,
        include_overtime: bool = True
    ) -> bool:
        """근무 시간 여부 확인"""
        local_time = timestamp if timestamp.tzinfo else self.timezone.localize(timestamp)
        current_time = local_time.time()
        
        shift_info = self.shift_times[shift_type]
        
        if shift_type == ShiftType.DAY:
            # 주간: 단순 비교
            if include_overtime:
                return time(6, 0) <= current_time <= time(22, 0)
            else:
                return shift_info['start'] <= current_time <= shift_info['end']
        
        elif shift_type == ShiftType.NIGHT:
            # 야간: 자정을 넘는 경우 처리
            if include_overtime:
                return (current_time >= time(18, 0) or 
                       current_time <= time(10, 0))
            else:
                return (current_time >= shift_info['start'] or 
                       current_time <= shift_info['end'])
        
        else:  # OFFICE
            # 사무직: 유연근무
            return time(6, 0) <= current_time <= time(22, 0)
    
    def classify_entry_exit(
        self, 
        timestamp: datetime, 
        shift_type: ShiftType,
        is_entry_gate: bool
    ) -> str:
        """
        출입 분류
        
        Args:
            timestamp: 태그 시간
            shift_type: 근무 유형
            is_entry_gate: True=입문(T2), False=출문(T3)
        """
        local_time = timestamp if timestamp.tzinfo else self.timezone.localize(timestamp)
        current_time = local_time.time()
        
        shift_info = self.shift_times[shift_type]
        
        if is_entry_gate:  # 입문 (T2)
            entry_start, entry_end = shift_info['entry_window']
            if shift_type == ShiftType.NIGHT:
                # 야간 입문: 19:00-21:00
                if entry_start <= current_time <= entry_end:
                    return "출입(IN)"
            else:
                # 주간 입문: 07:00-09:00
                if entry_start <= current_time <= entry_end:
                    return "출입(IN)"
        else:  # 출문 (T3)
            exit_start, exit_end = shift_info['exit_window']
            if shift_type == ShiftType.NIGHT:
                # 야간 출문: 07:30-09:30
                if exit_start <= current_time <= exit_end:
                    return "출입(OUT)"
            else:
                # 주간 출문: 19:30-21:30
                if exit_start <= current_time <= exit_end:
                    return "출입(OUT)"
        
        # 시간대가 맞지 않으면 경유로 처리
        return "경유"
    
    def get_time_weight(
        self, 
        timestamp: datetime, 
        state: str
    ) -> float:
        """
        시간대별 상태 가중치 반환
        특정 시간대에 특정 상태일 확률을 조정
        """
        local_time = timestamp if timestamp.tzinfo else self.timezone.localize(timestamp)
        hour = local_time.hour
        
        weights = {
            '업무': {
                (9, 11): 1.2,    # 오전 집중 시간
                (14, 16): 1.1,   # 오후 집중 시간
                (11, 13): 0.8,   # 점심 시간대
                (17, 19): 0.9,   # 퇴근 시간대
            },
            '식사': {
                (6, 9): 1.5,     # 조식
                (11, 14): 1.5,   # 중식
                (17, 20): 1.5,   # 석식
                (23, 24): 1.5,   # 야식
                (0, 1): 1.5,     # 야식 (자정 후)
            },
            '회의': {
                (8, 9): 1.3,     # 아침 회의
                (10, 11): 1.2,   # 오전 회의
                (14, 16): 1.2,   # 오후 회의
                (20, 21): 1.3,   # 교대 인수인계
            },
            '휴게': {
                (12, 13): 1.2,   # 점심 후
                (15, 16): 1.1,   # 오후 휴식
                (0, 6): 0.7,     # 심야 (휴게 가능성 낮음)
            }
        }
        
        # 해당 상태의 가중치 확인
        if state in weights:
            for (start, end), weight in weights[state].items():
                if start <= hour < end or (start > end and (hour >= start or hour < end)):
                    return weight
        
        return 1.0  # 기본 가중치
    
    def format_duration(self, duration: timedelta) -> str:
        """시간 차이를 읽기 쉬운 형식으로 변환"""
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        if hours > 0:
            return f"{hours}시간 {minutes}분"
        elif minutes > 0:
            return f"{minutes}분 {seconds}초"
        else:
            return f"{seconds}초"
    
    def get_meal_name(self, meal_type: Optional[MealType]) -> str:
        """식사 유형의 한글명 반환"""
        if meal_type is None:
            return "해당없음"
        
        meal_names = {
            MealType.BREAKFAST: "조식",
            MealType.LUNCH: "중식",
            MealType.DINNER: "석식",
            MealType.MIDNIGHT: "야식"
        }
        
        return meal_names.get(meal_type, "알수없음")


# 사용 예시를 위한 헬퍼 함수
def create_time_normalizer(timezone: str = 'Asia/Seoul') -> TimeNormalizer:
    """TimeNormalizer 인스턴스 생성"""
    return TimeNormalizer(timezone)


def get_work_date_for_employee(
    employee_id: str,
    timestamp: datetime,
    first_tag_time: Optional[datetime] = None
) -> date:
    """
    직원의 근무 날짜 계산
    first_tag_time이 없으면 timestamp로 근무 유형 추정
    """
    normalizer = TimeNormalizer()
    
    if first_tag_time:
        shift_type = normalizer.detect_shift_type(first_tag_time)
    else:
        shift_type = normalizer.detect_shift_type(timestamp)
    
    return normalizer.get_work_date(timestamp, shift_type)