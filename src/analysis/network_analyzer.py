"""
Network analysis module for employee movement patterns.
Analyzes movement between buildings and visualizes on facility map.
"""

import pandas as pd
import numpy as np
import networkx as nx
import matplotlib
matplotlib.use('Agg')  # 백엔드 설정
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path
import platform
import os

# 한글 폰트 설정
import matplotlib.font_manager as fm

def find_korean_font():
    """macOS에서 사용 가능한 한글 폰트 찾기"""
    # macOS 시스템 폰트 디렉토리
    font_dirs = [
        '/System/Library/Fonts/',
        '/Library/Fonts/',
        os.path.expanduser('~/Library/Fonts/')
    ]
    
    # 한글 폰트 후보
    korean_fonts = [
        'AppleSDGothicNeo.ttc',  # macOS 기본 한글 폰트
        'AppleGothic.ttf',
        'NanumGothic.ttf',
        'NanumBarunGothic.ttf',
        'MalgunGothic.ttf'
    ]
    
    for font_dir in font_dirs:
        for font_file in korean_fonts:
            font_path = os.path.join(font_dir, font_file)
            if os.path.exists(font_path):
                return font_path
    
    # Supplemental 폰트 확인
    supplemental_path = '/System/Library/Fonts/Supplemental/'
    if os.path.exists(supplemental_path):
        for font_file in os.listdir(supplemental_path):
            if 'Gothic' in font_file or 'Nanum' in font_file:
                return os.path.join(supplemental_path, font_file)
    
    return None

# 한글 폰트 설정
if platform.system() == 'Darwin':  # macOS
    # 직접 AppleGothic 폰트 경로 지정
    font_path = '/System/Library/Fonts/Supplemental/AppleGothic.ttf'
    if os.path.exists(font_path):
        from matplotlib import font_manager
        font_manager.fontManager.addfont(font_path)
        font_prop = font_manager.FontProperties(fname=font_path)
        font_name = font_prop.get_name()
        plt.rcParams['font.family'] = font_name
        plt.rcParams['axes.unicode_minus'] = False
        print(f"Using Korean font: {font_name} from {font_path}")
    else:
        # 폴백: 다른 방법 시도
        font_path = find_korean_font()
        if font_path:
            from matplotlib import font_manager
            font_manager.fontManager.addfont(font_path)
            font_prop = font_manager.FontProperties(fname=font_path)
            plt.rcParams['font.family'] = font_prop.get_name()
            plt.rcParams['axes.unicode_minus'] = False
            print(f"Using Korean font: {font_path}")
elif platform.system() == 'Windows':
    plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False
else:  # Linux
    plt.rcParams['font.family'] = 'DejaVu Sans'
    plt.rcParams['axes.unicode_minus'] = False

class BuildingMapper:
    """Maps tag locations to buildings and provides coordinates."""
    
    # Building coordinates as percentages of image dimensions
    # 실제 이미지의 건물 위치에 맞게 조정 (백분율로 표시)
    BUILDING_COORDS_PCT = {
        'P1': (0.30, 0.55),   # P1 건물 중앙
        'P2': (0.30, 0.30),   # P2 건물 중앙 (위쪽으로 조정)
        'P3': (0.78, 0.15),   # P3 건물 중앙 (우상단)
        'P4': (0.78, 0.45),   # P4 건물 중앙 (우측)
        'P3_GATE': (0.80, 0.15),  # P3-정문 (P3 우측)
        'P4_GATE': (0.88, 0.85),  # P4-정문 (우하단, 위치 조정)
        'MAIN_GATE': (0.20, 0.90), # 정문동 (좌하단, 왼쪽으로 이동)
        'P1_GATE': (0.30, 0.65),  # P1-정문 (P1 아래)
        'P2_GATE': (0.30, 0.20),  # P2-정문 (P2 위)
        'P5_GATE': (0.95, 0.75),  # P5-정문 (P5 우측)
        'P5': (0.88, 0.75),   # P5 건물 (우하단)
        'BP': (0.45, 0.50),   # BP 건물 (중앙)
        'GATE': (0.20, 0.90), # 정문동 (호환성 위해, MAIN_GATE와 동일)
        'HARMONY': (0.55, 0.15), # Harmony동 (상단 중앙)
        '연구동': (0.25, 0.75),  # 연구동 (좌하단)
        'UTIL': (0.92, 0.20),    # Util동 (우상단)
        'COMMUNITY': (0.65, 0.80), # 커뮤니티동 (하단)
    }
    
    # Tag location to building mapping patterns
    # 더 넓은 패턴 매칭을 위해 수정
    TAG_TO_BUILDING_PATTERNS = {
        'P1': ['P1', '1동', '1F', '1층', 'P1_', 'P-1'],
        'P2': ['P2', '2동', '2F', '2층', 'P2_', 'P-2'],
        'P3': ['P3', '3동', '3F', '3층', 'P3_', 'P-3'],
        'P4': ['P4', '4동', '4F', '4층', 'P4_', 'P-4'],
        'P4_GATE': ['P4_스피드게이트', 'P4 스피드게이트', 'P4_SPEED', 'P4_게이트', 'P4-GATE', 'P4_GATE', 'P4-게이트', 'P4 GATE', 'P4_생산동_2층브릿지', 'P4_브릿지', 'P4_BRIDGE'],
        'P5': ['P5', '5동', '5F', '5층', 'P5_', 'P-5', '임시식당'],
        'BP': ['BP', 'B동', '본관', 'B-P', 'BP2_2F', '바이오프라자'],
        'GATE': ['정문', '게이트', 'GATE', '출입구', '출입', '입구'],
        'HARMONY': ['HARMONY', 'Harmony', 'harmony', '하모니'],
        '연구동': ['연구동', '연구', 'RESEARCH', 'R동'],
        'UTIL': ['UTIL', 'Util', 'util', '유틸'],
        'COMMUNITY': ['COMMUNITY', 'Community', '커뮤니티', '투썸'],
    }
    
    @classmethod
    def get_building_from_location(cls, location: str) -> Optional[str]:
        """Extract building code from location string."""
        if not location:
            return None
            
        location_upper = location.upper()
        
        import re
        
        # 디버깅: P4_생산동_2층브릿지 확인
        if 'P4_생산동' in location and '2층브릿지' in location:
            print(f"DEBUG: P4 2층브릿지 발견: {location}")
            return 'P4_GATE'
        
        # 정문 체크를 먼저 수행 - 정문이 포함된 경우 체크
        if '정문' in location:
            # P3 정문 패턴 - SPEED GATE 포함 처리
            if 'P3' in location:
                return 'P3_GATE'
            # P4 정문 패턴 - SPEED GATE 포함 처리
            elif 'P4' in location:
                return 'P4_GATE'
            # P2 정문 패턴
            elif 'P2' in location:
                return 'P2_GATE'
            # P1 정문 패턴
            elif 'P1' in location:
                return 'P1_GATE'
            # P5 정문 패턴
            elif 'P5' in location:
                return 'P5_GATE'
            # 정문동 패턴
            elif '정문동' in location:
                return 'MAIN_GATE'
            # P 건물이 명시되지 않은 정문은 정문동으로
            else:
                return 'MAIN_GATE'
        
        # P4 스피드 게이트 체크 - 다양한 패턴 인식 (정문이 아닌 경우)
        if 'P4' in location_upper:
            # SPEED GATE는 공백이 있으므로 별도 확인
            if 'SPEED' in location_upper and 'GATE' in location_upper:
                return 'P4_GATE'
            elif any(keyword in location_upper for keyword in ['스피드게이트', '스피드 게이트', '-GATE', '_GATE', '브릿지', 'BRIDGE', '2층브릿지']):
                return 'P4_GATE'
        elif 'P4-GATE' in location_upper or 'P4_GATE' in location_upper:
            return 'P4_GATE'
        elif 'P4_생산동' in location and ('SPEED' in location_upper and 'GATE' in location_upper):
            return 'P4_GATE'
        
        # P + 숫자 패턴을 찾기 (가장 구체적인 패턴)
        # P4_생산동, P3_생산동, P2_DP동, P1-BP2 등의 패턴 매칭
        # 단, SPEED GATE나 브릿지가 포함된 경우는 제외 (위에서 이미 처리)
        if not any(keyword in location_upper for keyword in ['SPEED GATE', '브릿지', 'BRIDGE']):
            p_building_pattern = re.search(r'P(\d)[\s\-_]', location_upper)
            if p_building_pattern:
                building_num = p_building_pattern.group(1)
                building_code = f'P{building_num}'
                if building_code in cls.BUILDING_COORDS_PCT:
                    # P1-BP2 같은 경우 BP가 포함되어 있으면 P 건물로 인식
                    if '-BP' in location_upper:
                        return building_code
                    # 일반적인 P 건물
                    return building_code
        
        # BP 체크 (P 건물 패턴이 없는 경우) - BP2_2F도 BP로 매핑
        if 'BP' in location_upper or 'B-P' in location_upper or '바이오프라자' in location_upper:
            return 'BP'
        
        # 가상 이동 경로 처리
        if 'MOVEMENT_TO_BP' in location_upper:
            return 'BP'
        elif 'BP_CAFETERIA' in location_upper:
            return 'BP'
        
        # 특정 건물 체크
        if 'HARMONY' in location_upper or '하모니' in location:
            return 'HARMONY'
        elif '연구동' in location or 'RESEARCH' in location_upper:
            return '연구동'
        elif 'UTIL' in location_upper or '유틸' in location:
            return 'UTIL'
        elif 'COMMUNITY' in location_upper or '커뮤니티' in location or '투썸' in location:
            return 'COMMUNITY'
        
        # H동 체크
        if 'H동' in location_upper or 'H-' in location_upper:
            return 'H'
        
        # W1, W2 등은 현재 매핑이 없으므로 None 반환
        return None
    
    @classmethod
    def get_coordinates(cls, building: str, img_width: int = 1, img_height: int = 1) -> Optional[Tuple[float, float]]:
        """Get coordinates for a building scaled to image dimensions."""
        pct_coords = cls.BUILDING_COORDS_PCT.get(building)
        if pct_coords:
            return (pct_coords[0] * img_width, pct_coords[1] * img_height)
        return None


class NetworkAnalyzer:
    """Analyzes employee movement networks between buildings."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.mapper = BuildingMapper()
        
    def get_employee_movements(self, employee_id: str, start_date: str, end_date: str, include_meal_data: bool = True) -> pd.DataFrame:
        """Get movement data for an employee within date range."""
        # 먼저 individual_dashboard에서 사용하는 daily_tag_data 메서드 사용
        # 이것이 실제 태그 데이터를 가져오는 방법인 것으로 보임
        try:
            # 식사 데이터 로드하여 BP 이동 추가
            from pathlib import Path
            import sys
            # src 경로 추가
            src_path = Path(__file__).parent.parent
            if str(src_path) not in sys.path:
                sys.path.append(str(src_path))
            
            from data_processing import PickleManager
            pickle_manager = PickleManager()
            
            # 태그 데이터 가져오기 (pickle에서)
            tag_data = pickle_manager.load_dataframe(name='tag_data')
            df = pd.DataFrame()
            
            if tag_data is not None and not tag_data.empty:
                # 사번 처리
                if ' - ' in str(employee_id):
                    employee_id = employee_id.split(' - ')[0].strip()
                
                # 날짜 필터링
                start_dt = pd.to_datetime(start_date)
                end_dt = pd.to_datetime(end_date)
                
                # ENTE_DT를 날짜로 변환
                tag_data['date'] = pd.to_datetime(tag_data['ENTE_DT'].astype(str), format='%Y%m%d', errors='coerce')
                
                # 사번과 날짜로 필터링
                try:
                    emp_id_int = int(employee_id)
                    tag_data['사번'] = pd.to_numeric(tag_data['사번'], errors='coerce')
                    filtered_data = tag_data[
                        (tag_data['사번'] == emp_id_int) & 
                        (tag_data['date'] >= start_dt) & 
                        (tag_data['date'] <= end_dt)
                    ].copy()
                except:
                    tag_data['사번'] = tag_data['사번'].astype(str)
                    filtered_data = tag_data[
                        (tag_data['사번'] == str(employee_id)) & 
                        (tag_data['date'] >= start_dt) & 
                        (tag_data['date'] <= end_dt)
                    ].copy()
                
                if not filtered_data.empty:
                    # timestamp 생성
                    filtered_data['time_str'] = filtered_data['출입시각'].astype(str).str.zfill(6)
                    filtered_data['timestamp'] = pd.to_datetime(
                        filtered_data['ENTE_DT'].astype(str) + ' ' + filtered_data['time_str'],
                        format='%Y%m%d %H%M%S',
                        errors='coerce'
                    )
                    
                    # 필요한 컬럼만 선택
                    df = filtered_data[['timestamp', 'DR_NM', 'DR_NO', 'INOUT_GB']].copy()
                    df.columns = ['timestamp', 'tag_location', 'gate_name', 'work_area_type']
                    df['work_area_type'] = 'Y'  # 기본값
            
            # 식사 데이터 추가
            meal_movements = pd.DataFrame()
            
            if include_meal_data:
                # 식사 데이터 가져오기
                meal_data = pickle_manager.load_dataframe(name='meal_data')
                
                if meal_data is not None and not meal_data.empty:
                    # 날짜 필터링
                    date_column = 'meal_datetime' if 'meal_datetime' in meal_data.columns else '취식일시'
                    if date_column in meal_data.columns:
                        if not pd.api.types.is_datetime64_any_dtype(meal_data[date_column]):
                            meal_data[date_column] = pd.to_datetime(meal_data[date_column])
                        
                        # 사번과 날짜로 필터링
                        emp_id_column = 'employee_id' if 'employee_id' in meal_data.columns else '사번'
                        
                        # 날짜 범위로 필터링
                        start_dt = pd.to_datetime(start_date)
                        end_dt = pd.to_datetime(end_date)
                        
                        try:
                            emp_id_int = int(employee_id)
                            meal_data[emp_id_column] = pd.to_numeric(meal_data[emp_id_column], errors='coerce')
                            daily_meals = meal_data[
                                (meal_data[emp_id_column] == emp_id_int) & 
                                (meal_data[date_column] >= start_dt) & 
                                (meal_data[date_column] <= end_dt)
                            ].copy()
                        except:
                            meal_data[emp_id_column] = meal_data[emp_id_column].astype(str)
                            daily_meals = meal_data[
                                (meal_data[emp_id_column] == str(employee_id)) & 
                                (meal_data[date_column] >= start_dt) & 
                                (meal_data[date_column] <= end_dt)
                            ].copy()
                        
                        if not daily_meals.empty:
                            # 식당명으로 건물 매핑
                            restaurant_mapping = {
                                'SBL 2단지 임시 식당': 'P5_CAFETERIA',
                                'SBL 바이오프라자2 식당': 'BP2_2F',
                                'SBL 바이오프라자2 푸드코트': 'BP2_2F',
                                '삼성바이오로직스 커뮤니티동 투썸플레이스': 'COMMUNITY_CAFETERIA'
                            }
                            
                            # 식사 데이터를 이동 데이터로 변환
                            restaurant_column = '식당명' if '식당명' in daily_meals.columns else 'restaurant'
                            meal_movements = pd.DataFrame({
                                'timestamp': daily_meals[date_column],
                                'tag_location': daily_meals[restaurant_column].map(restaurant_mapping).fillna('BP2_2F'),
                                'gate_name': daily_meals[restaurant_column],
                                'work_area_type': 'N',
                                'is_meal': True
                            })
                            
                            # 식사 5분 전에 BP로 이동한 것으로 가상 태그 추가
                            virtual_movements = []
                            for _, meal in meal_movements.iterrows():
                                virtual_movements.append({
                                    'timestamp': meal['timestamp'] - pd.Timedelta(minutes=5),
                                    'tag_location': 'MOVEMENT_TO_BP',
                                    'gate_name': 'Virtual Movement',
                                    'work_area_type': 'N',
                                    'is_meal': False
                                })
                            
                            if virtual_movements:
                                virtual_df = pd.DataFrame(virtual_movements)
                                meal_movements = pd.concat([virtual_df, meal_movements], ignore_index=True)
                
        except Exception as e:
            print(f"Error loading data: {e}")
            df = pd.DataFrame()
            meal_movements = pd.DataFrame()
            
        # 데이터 병합
        if not df.empty and not meal_movements.empty:
            # 병합
            df = pd.concat([df, meal_movements], ignore_index=True)
            df = df.sort_values('timestamp').reset_index(drop=True)
        elif meal_movements.empty and df.empty:
            # 둘 다 비어있으면 빈 데이터프레임 반환
            df = pd.DataFrame()
        elif df.empty and not meal_movements.empty:
            # 태그 데이터만 비어있으면 식사 데이터만 사용
            df = meal_movements
            
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['building'] = df['tag_location'].apply(self.mapper.get_building_from_location)
            
            # 디버깅: 식사 관련 데이터 확인
            if 'is_meal' in df.columns:
                meal_data_in_df = df[df['is_meal'] == True]
            else:
                meal_data_in_df = pd.DataFrame()
            if not meal_data_in_df.empty:
                print(f"식사 데이터 확인:")
                print(f"  - 식사 기록 수: {len(meal_data_in_df)}")
                print(f"  - 태그 위치: {meal_data_in_df['tag_location'].unique()}")
                print(f"  - 매핑된 건물: {meal_data_in_df['building'].unique()}")
                
            # 전체 데이터 요약
            print(f"전체 이동 데이터: {len(df)}건")
            print(f"건물 매핑 현황: {df.groupby('building').size().to_dict()}")
            
            # 디버깅: 게이트 관련 데이터 확인
            gate_related = df[df['tag_location'].str.contains('정문|GATE|SPEED|스피드|게이트|브릿지', case=False, na=False)]
            if not gate_related.empty:
                print(f"게이트 관련 태그 발견: {len(gate_related)}건")
                print(f"게이트 태그 위치: {gate_related['tag_location'].unique()}")
                print(f"게이트 매핑 결과: {gate_related['building'].unique()}")
                
                # P4 게이트 구분
                p4_gate = gate_related[gate_related['building'] == 'P4_GATE']
                if not p4_gate.empty:
                    print(f"  - P4_GATE: {len(p4_gate)}건")
                    
                # P4 관련 태그 중 매핑 안된 것 확인
                p4_related = df[df['tag_location'].str.contains('P4', case=False, na=False)]
                p4_unmapped = p4_related[p4_related['building'].isna()]
                if not p4_unmapped.empty:
                    print(f"  - P4 태그 중 매핑 안됨: {p4_unmapped['tag_location'].unique()}")
            
            # 출퇴근 시간대 데이터 확인
            if not df.empty and 'timestamp' in df.columns:
                first_record = df.iloc[0]
                last_record = df.iloc[-1]
                print(f"첫 태그: {first_record['timestamp'].strftime('%H:%M')} - {first_record['tag_location']} -> {first_record['building']}")
                print(f"마지막 태그: {last_record['timestamp'].strftime('%H:%M')} - {last_record['tag_location']} -> {last_record['building']}")
            
        return df
    
    def analyze_movement_patterns(self, movements_df: pd.DataFrame) -> Dict:
        """Analyze movement patterns from tag data."""
        if movements_df.empty:
            return {}
            
        # Filter out rows without building mapping
        valid_movements = movements_df[movements_df['building'].notna()].copy()
        
        if valid_movements.empty:
            return {}
        
        # timestamp 컬럼이 datetime 형식인지 확인하고 변환
        if not pd.api.types.is_datetime64_any_dtype(valid_movements['timestamp']):
            valid_movements['timestamp'] = pd.to_datetime(valid_movements['timestamp'])
        
        # Calculate transitions
        transitions = []
        for i in range(1, len(valid_movements)):
            prev_row = valid_movements.iloc[i-1]
            curr_row = valid_movements.iloc[i]
            
            prev_building = prev_row['building']
            curr_building = curr_row['building']
            
            if prev_building != curr_building:
                try:
                    # 시간 차이 계산 - 각각의 값을 명시적으로 추출
                    curr_ts = curr_row['timestamp']
                    prev_ts = prev_row['timestamp']
                    
                    # pandas Series가 아닌 개별 값으로 처리
                    if isinstance(curr_ts, pd.Series):
                        curr_ts = curr_ts.iloc[0]
                    if isinstance(prev_ts, pd.Series):
                        prev_ts = prev_ts.iloc[0]
                    
                    # 시간 차이 계산
                    time_diff = curr_ts - prev_ts
                    
                    # timedelta 객체로 변환
                    if hasattr(time_diff, 'total_seconds'):
                        duration_minutes = time_diff.total_seconds() / 60
                    else:
                        # numpy timedelta64인 경우
                        duration_minutes = pd.Timedelta(time_diff).total_seconds() / 60
                        
                except Exception as e:
                    print(f"Duration calculation error: {e}")
                    # 오류 발생시 기본값 사용
                    duration_minutes = 5.0
                
                transitions.append({
                    'from': prev_building,
                    'to': curr_building,
                    'timestamp': curr_row['timestamp'],
                    'duration': duration_minutes
                })
        
        # Building visit statistics
        building_visits = valid_movements.groupby('building').agg({
            'timestamp': 'count',
            'building': 'first'
        }).rename(columns={'timestamp': 'visit_count'})
        
        # Calculate time spent in each building
        time_spent = {}
        for building in valid_movements['building'].unique():
            building_data = valid_movements[valid_movements['building'] == building]
            total_minutes = 0
            
            for i in range(len(building_data)):
                try:
                    if i + 1 < len(valid_movements):
                        # 다음 로그의 인덱스 찾기
                        current_idx = building_data.index[i]
                        remaining_indices = valid_movements.index[valid_movements.index > current_idx]
                        
                        if len(remaining_indices) > 0:
                            next_idx = remaining_indices[0]
                            
                            # 시간 값 추출
                            next_ts = valid_movements.loc[next_idx, 'timestamp']
                            curr_ts = building_data.iloc[i]['timestamp']
                            
                            # pandas Series가 아닌 개별 값으로 처리
                            if isinstance(next_ts, pd.Series):
                                next_ts = next_ts.iloc[0]
                            if isinstance(curr_ts, pd.Series):
                                curr_ts = curr_ts.iloc[0]
                            
                            # 시간 차이 계산
                            time_diff = next_ts - curr_ts
                            
                            # duration 계산
                            if hasattr(time_diff, 'total_seconds'):
                                duration = time_diff.total_seconds() / 60
                            else:
                                duration = pd.Timedelta(time_diff).total_seconds() / 60
                            
                            if duration < 480:  # Cap at 8 hours to avoid overnight gaps
                                total_minutes += duration
                except Exception as e:
                    print(f"Time spent calculation error: {e}")
                    # 오류 발생시 건너뛰기
                    continue
            
            time_spent[building] = total_minutes
        
        # Transition matrix
        if transitions:
            transition_df = pd.DataFrame(transitions)
            transition_matrix = pd.crosstab(
                transition_df['from'], 
                transition_df['to'], 
                values=transition_df['from'], 
                aggfunc='count'
            ).fillna(0)
        else:
            transition_matrix = pd.DataFrame()
        
        return {
            'transitions': transitions,
            'building_visits': building_visits.to_dict('index'),
            'time_spent': time_spent,
            'transition_matrix': transition_matrix,
            'total_transitions': len(transitions)
        }
    
    def create_network_graph(self, analysis_results: Dict, img_width: int, img_height: int) -> nx.DiGraph:
        """Create a directed graph from movement analysis."""
        G = nx.DiGraph()
        
        if not analysis_results or 'transitions' not in analysis_results:
            return G
        
        # Add nodes for each building
        for building, stats in analysis_results.get('building_visits', {}).items():
            coords = self.mapper.get_coordinates(building, img_width, img_height)
            if coords:
                G.add_node(
                    building,
                    pos=coords,
                    visits=stats.get('visit_count', 0),
                    time_spent=analysis_results['time_spent'].get(building, 0)
                )
        
        # Add edges for transitions
        edge_counts = {}
        for transition in analysis_results['transitions']:
            key = (transition['from'], transition['to'])
            edge_counts[key] = edge_counts.get(key, 0) + 1
        
        for (from_b, to_b), count in edge_counts.items():
            if from_b in G.nodes and to_b in G.nodes:
                G.add_edge(from_b, to_b, weight=count)
        
        return G
    
    def visualize_movement_network(
        self, 
        analysis_results: Dict,
        employee_name: str,
        date_range: str,
        facility_image_path: str,
        save_path: Optional[str] = None
    ) -> plt.Figure:
        """Visualize movement network on facility map."""
        # macOS에서 한글 폰트 명시적 설정
        if platform.system() == 'Darwin':
            font_path = '/System/Library/Fonts/Supplemental/AppleGothic.ttf'
            if os.path.exists(font_path):
                from matplotlib import font_manager
                font_prop = font_manager.FontProperties(fname=font_path)
                plt.rcParams['font.family'] = font_prop.get_name()
        
        plt.rcParams['axes.unicode_minus'] = False
        
        # Load and display facility map
        from PIL import Image
        img = Image.open(facility_image_path)
        
        # 이미지 비율 계산
        img_width, img_height = img.size
        aspect_ratio = img_width / img_height
        
        # Figure 생성 - 이미지 비율에 맞게 (aspect_ratio는 약 1.89)
        # 가로를 충분히 크게 설정
        fig_width = 24
        fig_height = fig_width / aspect_ratio
        fig = plt.figure(figsize=(fig_width, fig_height))
        ax = fig.add_subplot(111)
        
        # 이미지 표시 - aspect ratio 유지
        ax.imshow(img, alpha=0.7)
        
        # 좌표계를 0-1로 정규화
        ax.set_xlim(0, img_width)
        ax.set_ylim(img_height, 0)  # y축 반전
        
        # Create network graph
        G = self.create_network_graph(analysis_results, img_width, img_height)
        
        if len(G.nodes) == 0:
            ax.text(img_width/2, img_height/2, 'No Movement Data', ha='center', va='center', 
                   fontsize=20, color='red', weight='bold')
            plt.title(f'{employee_name} - Movement Path Analysis\n{date_range}', fontsize=16)
            return fig
        
        # Get node positions
        pos = nx.get_node_attributes(G, 'pos')
        
        # Draw nodes (buildings)
        node_sizes = []
        node_colors = []
        
        # 최대/최소 시간을 찾아서 정규화
        all_times = [G.nodes[node].get('time_spent', 0) for node in G.nodes()]
        max_time = max(all_times) if all_times else 1
        min_time = min(all_times) if all_times else 0
        
        for node in G.nodes():
            visits = G.nodes[node].get('visits', 1)
            time_spent = G.nodes[node].get('time_spent', 0)
            
            # Size based on time spent - 선형 비례
            # 최소 크기 500, 최대 크기 4000
            if max_time > min_time:
                normalized_time = (time_spent - min_time) / (max_time - min_time)
                node_size = 500 + normalized_time * 3500
            else:
                node_size = 1500
            
            node_sizes.append(node_size)
            
            # Color based on time spent (heat map)
            if time_spent > 300:  # > 5 hours
                node_colors.append('#ff4444')
            elif time_spent > 180:  # > 3 hours
                node_colors.append('#ff8844')
            elif time_spent > 60:  # > 1 hour
                node_colors.append('#ffaa44')
            else:
                node_colors.append('#44ff44')
        
        nx.draw_networkx_nodes(
            G, pos, 
            node_size=node_sizes,
            node_color=node_colors,
            alpha=0.8,
            ax=ax
        )
        
        # Draw edges (movements)
        edges = G.edges()
        if edges:
            # Get edge weights for line width
            edge_weights = [G[u][v]['weight'] for u, v in edges]
            max_weight = max(edge_weights) if edge_weights else 1
            
            # Normalize edge widths
            edge_widths = [1 + (w / max_weight) * 5 for w in edge_weights]
            
            # Draw edges with arrows
            nx.draw_networkx_edges(
                G, pos,
                edge_color='blue',
                width=edge_widths,
                alpha=0.6,
                arrows=True,
                arrowsize=20,
                arrowstyle='->',
                connectionstyle='arc3,rad=0.1',
                ax=ax
            )
        
        # Draw labels - offset below nodes
        labels = {}
        label_pos = {}
        for node in G.nodes():
            visits = G.nodes[node].get('visits', 0)
            time_spent = G.nodes[node].get('time_spent', 0)
            labels[node] = f"{node}\nVisits:{visits}\n{int(time_spent)}min"
            
            # Offset label position above the node
            node_x, node_y = pos[node]
            label_pos[node] = (node_x, node_y - 80)  # Offset above node
        
        nx.draw_networkx_labels(
            G, label_pos, labels,
            font_size=12,
            font_weight='bold',
            bbox=dict(boxstyle="round,pad=0.6", facecolor="white", alpha=0.9, edgecolor='gray', linewidth=1),
            ax=ax
        )
        
        # Add statistics
        stats_text = "Total Transitions: {}".format(analysis_results.get('total_transitions', 0))
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
               fontsize=12, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # Add legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#ff4444', label='5hr+'),
            Patch(facecolor='#ff8844', label='3-5hr'),
            Patch(facecolor='#ffaa44', label='1-3hr'),
            Patch(facecolor='#44ff44', label='<1hr')
        ]
        ax.legend(handles=legend_elements, loc='upper right', title='Stay Time')
        
        plt.title(f'{employee_name} - Movement Path Analysis\n{date_range}', fontsize=16)
        ax.axis('off')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        return fig
    
    def get_frequent_paths(self, analysis_results: Dict, top_n: int = 5) -> List[Dict]:
        """Get most frequent movement paths."""
        if not analysis_results or 'transitions' not in analysis_results:
            return []
        
        # Count path frequencies
        path_counts = {}
        transitions = analysis_results['transitions']
        
        for i in range(len(transitions) - 1):
            path = f"{transitions[i]['from']} → {transitions[i]['to']}"
            path_counts[path] = path_counts.get(path, 0) + 1
        
        # Sort by frequency
        sorted_paths = sorted(
            path_counts.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:top_n]
        
        return [
            {'path': path, 'count': count}
            for path, count in sorted_paths
        ]