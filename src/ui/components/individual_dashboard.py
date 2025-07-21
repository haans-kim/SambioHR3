"""
개인별 대시보드 컴포넌트
UI 참조자료를 반영한 개인 활동 요약 및 타임라인 시각화
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta, date
import logging
from pathlib import Path
from typing import List, Dict, Any
from .improved_gantt_chart import render_improved_gantt_chart
from .hmm_classifier import HMMActivityClassifier

from ...analysis import IndividualAnalyzer
from ...config.activity_types import (
    ACTIVITY_TYPES, get_activity_color, get_activity_name,
    get_activity_type, ActivityType
)

class IndividualDashboard:
    """개인별 대시보드 컴포넌트"""
    
    def __init__(self, individual_analyzer: IndividualAnalyzer):
        self.analyzer = individual_analyzer
        self.logger = logging.getLogger(__name__)
        
        # 색상 팔레트 (activity_types.py에서 가져옴)
        self.colors = {}
        for code, activity in ACTIVITY_TYPES.items():
            self.colors[code] = activity.color
        
        # 이전 버전과의 호환성을 위한 매핑
        self.colors.update({
            'work': '#2E86AB',
            'meeting': '#A23B72',
            'movement': '#F18F01',
            'meal': '#C73E1D',
            'breakfast': '#FF6B6B',
            'lunch': '#4ECDC4',
            'dinner': '#45B7D1',
            'midnight_meal': '#96CEB4',
            'rest': '#4CAF50',
            'low_confidence': '#E0E0E0'
        })
    
    def get_available_employees(self):
        """로드된 데이터에서 사용 가능한 직원 목록 가져오기"""
        try:
            # pickle 파일에서 직원 목록 가져오기
            from ...data_processing import PickleManager
            pickle_manager = PickleManager()
            
            # 태깅 데이터에서 직원 목록 추출
            tag_data = pickle_manager.load_dataframe(name='tag_data')
            if tag_data is not None and '사번' in tag_data.columns:
                employees = sorted(tag_data['사번'].unique().tolist())
                return employees[:100]  # 최대 100명까지만 표시
            
            # 다른 데이터 소스 시도
            claim_data = pickle_manager.load_dataframe(name='claim_data')
            if claim_data is not None and '사번' in claim_data.columns:
                employees = sorted(claim_data['사번'].unique().tolist())
                return employees[:100]
            
            return []
        except Exception as e:
            self.logger.warning(f"직원 목록 로드 실패: {e}")
            return []
    
    def get_available_date_range(self):
        """로드된 데이터에서 사용 가능한 날짜 범위 가져오기"""
        try:
            from ...data_processing import PickleManager
            pickle_manager = PickleManager()
            
            # 태깅 데이터에서 날짜 범위 추출
            tag_data = pickle_manager.load_dataframe(name='tag_data')
            if tag_data is not None and 'ENTE_DT' in tag_data.columns:
                # YYYYMMDD 형식을 date 객체로 변환
                tag_data['date'] = pd.to_datetime(tag_data['ENTE_DT'], format='%Y%m%d')
                min_date = tag_data['date'].min().date()
                max_date = tag_data['date'].max().date()
                return {'min_date': min_date, 'max_date': max_date}
            
            # 다른 데이터 소스 시도
            claim_data = pickle_manager.load_dataframe(name='claim_data')
            if claim_data is not None and '근무일' in claim_data.columns:
                claim_data['date'] = pd.to_datetime(claim_data['근무일'], format='%Y%m%d')
                min_date = claim_data['date'].min().date()
                max_date = claim_data['date'].max().date()
                return {'min_date': min_date, 'max_date': max_date}
            
            return None
        except Exception as e:
            self.logger.warning(f"날짜 범위 로드 실패: {e}")
            return None
    
    def get_daily_claim_data(self, employee_id: str, selected_date: date):
        """특정 직원의 특정 날짜 Claim 데이터 가져오기"""
        try:
            from ...data_processing import PickleManager
            pickle_manager = PickleManager()
            
            # Claim 데이터 로드
            claim_data = pickle_manager.load_dataframe(name='claim_data')
            if claim_data is None:
                return None
            
            # 날짜 형식 변환 (YYYYMMDD)
            date_str = selected_date.strftime('%Y%m%d')
            date_int = int(date_str)
            
            # 해당 직원과 날짜의 데이터 필터링
            daily_claim = claim_data[
                (claim_data['사번'] == employee_id) & 
                (claim_data['근무일'] == date_int)
            ]
            
            if daily_claim.empty:
                return None
            
            # 필요한 정보 추출
            claim_info = {
                'exists': True,
                'claim_start': daily_claim.iloc[0].get('시작', 'N/A'),
                'claim_end': daily_claim.iloc[0].get('종료', 'N/A'),
                'claim_hours': daily_claim.iloc[0].get('근무시간', 0),
                'claim_type': daily_claim.iloc[0].get('근무유형', 'N/A'),
                'overtime': daily_claim.iloc[0].get('초과근무', 0),
                'raw_claim': daily_claim.iloc[0].to_dict()
            }
            
            return claim_info
            
        except Exception as e:
            self.logger.warning(f"Claim 데이터 로드 실패: {e}")
            return None
    
    def get_tag_location_master(self):
        """태깅지점 마스터 데이터 가져오기"""
        try:
            from ...data_processing import PickleManager
            import gzip
            pickle_manager = PickleManager()
            
            # 직접 파일 경로로 로드 시도
            import glob
            pattern = str(pickle_manager.base_path / "tag_location_master_v*.pkl.gz")
            files = glob.glob(pattern)
            
            if files:
                # 가장 최신 파일 선택
                latest_file = sorted(files)[-1]
                self.logger.info(f"태깅지점 마스터 파일 직접 로드: {latest_file}")
                
                with gzip.open(latest_file, 'rb') as f:
                    tag_location_master = pd.read_pickle(f)
            else:
                self.logger.warning("태깅지점 마스터 파일을 찾을 수 없습니다.")
                return None
            
            if tag_location_master is not None:
                self.logger.info(f"태깅지점 마스터 데이터 로드 성공: {len(tag_location_master)}건")
                self.logger.info(f"마스터 데이터 컬럼: {tag_location_master.columns.tolist()}")
                
                # 컬럼명 확인 및 표준화
                # 가능한 컬럼명 변형들
                dr_no_variations = ['DR_NO', 'dr_no', 'Dr_No', 'DRNO', 'dr번호', 'DR번호', '기기번호']
                work_area_variations = ['근무구역여부', '근무구역', 'work_area', 'WORK_AREA']
                work_status_variations = ['근무', '근무상태', 'work_status', 'WORK_STATUS']
                label_variations = ['라벨링', '라벨', 'label', 'LABEL', '레이블']
                
                # 실제 컬럼명 찾기
                for col in dr_no_variations:
                    if col in tag_location_master.columns:
                        tag_location_master['DR_NO'] = tag_location_master[col]
                        break
                
                # 근무구역여부, 근무, 라벨링 컬럼은 이미 있으므로 추가 처리 불필요
                
                return tag_location_master
            else:
                self.logger.warning("태깅지점 마스터 데이터가 없습니다.")
                return None
                
        except Exception as e:
            self.logger.warning(f"태깅지점 마스터 데이터 로드 실패: {e}")
            return None
    
    def get_daily_tag_data(self, employee_id: str, selected_date: date):
        """특정 직원의 특정 날짜 태깅 데이터 가져오기"""
        try:
            from ...data_processing import PickleManager
            pickle_manager = PickleManager()
            
            # 태깅 데이터 로드
            tag_data = pickle_manager.load_dataframe(name='tag_data')
            if tag_data is None:
                return None
            
            # 날짜 형식 변환 (YYYYMMDD)
            date_str = selected_date.strftime('%Y%m%d')
            date_int = int(date_str)
            
            # 해당 직원과 날짜의 데이터 필터링
            daily_data = tag_data[
                (tag_data['사번'] == employee_id) & 
                (tag_data['ENTE_DT'] == date_int)
            ].copy()
            
            if daily_data.empty:
                return None
            
            # 시간순 정렬
            daily_data['time'] = daily_data['출입시각'].astype(str).str.zfill(6)
            daily_data['datetime'] = pd.to_datetime(
                daily_data['ENTE_DT'].astype(str) + ' ' + daily_data['time'],
                format='%Y%m%d %H%M%S'
            )
            daily_data = daily_data.sort_values('datetime')
            
            return daily_data
            
        except Exception as e:
            self.logger.error(f"일일 태그 데이터 로드 실패: {e}")
            return None
    
    def classify_activities(self, daily_data: pd.DataFrame):
        """활동 분류 수행 (HMM 기반)"""
        try:
            # 태깅지점 마스터 데이터 로드
            tag_location_master = self.get_tag_location_master()
            
            # 기본 활동 분류
            daily_data['activity_code'] = 'WORK'  # 기본값
            daily_data['work_area_type'] = 'Y'  # 기본값 (근무구역)
            daily_data['work_status'] = 'W'  # 기본값 (근무상태)
            daily_data['activity_label'] = 'YW'  # 기본값 (근무구역에서 근무중)
            daily_data['confidence'] = 80  # 기본 신뢰도
            
            # 태깅지점 마스터 데이터와 조인
            if tag_location_master is not None and 'DR_NO' in tag_location_master.columns:
                # DR_NO 데이터 타입 맞추기
                daily_data['DR_NO_str'] = daily_data['DR_NO'].astype(str).str.strip()
                
                # 마스터 데이터의 DR_NO가 숫자형이면 문자열로 변환
                if tag_location_master['DR_NO'].dtype in ['int64', 'float64']:
                    tag_location_master['DR_NO_str'] = tag_location_master['DR_NO'].astype(int).astype(str)
                else:
                    tag_location_master['DR_NO_str'] = tag_location_master['DR_NO'].astype(str).str.strip()
                
                # 조인 전 데이터 확인
                self.logger.info(f"조인 전 - daily_data DR_NO 샘플: {daily_data['DR_NO_str'].head().tolist()}")
                self.logger.info(f"조인 전 - master DR_NO 샘플: {tag_location_master['DR_NO_str'].head().tolist()}")
                
                # 조인할 컬럼 확인 (새로운 태그 코드 체계 적용)
                join_columns = ['DR_NO_str']
                if 'Tag_Code' in tag_location_master.columns:
                    join_columns.append('Tag_Code')
                if '공간구분_NM' in tag_location_master.columns:
                    join_columns.append('공간구분_NM')
                if '세부유형_NM' in tag_location_master.columns:
                    join_columns.append('세부유형_NM')
                if '라벨링_활동' in tag_location_master.columns:
                    join_columns.append('라벨링_활동')
                # 기존 컬럼들도 체크 (호환성)
                if '근무구역여부' in tag_location_master.columns:
                    join_columns.append('근무구역여부')
                if '근무' in tag_location_master.columns:
                    join_columns.append('근무')
                if '라벨링' in tag_location_master.columns:
                    join_columns.append('라벨링')
                
                # DR_NO_str로 조인
                daily_data = daily_data.merge(
                    tag_location_master[join_columns],
                    on='DR_NO_str',
                    how='left',
                    suffixes=('', '_master')
                )
                
                # 조인 후 결과 확인
                if 'Tag_Code' in daily_data.columns:
                    matched_count = daily_data['Tag_Code'].notna().sum()
                elif '근무구역여부' in daily_data.columns:
                    matched_count = daily_data['근무구역여부'].notna().sum()
                else:
                    matched_count = 0
                self.logger.info(f"조인 결과: {matched_count}/{len(daily_data)} 매칭됨")
                
                # 새로운 태그 코드 체계 적용
                if 'Tag_Code' in daily_data.columns:
                    # Tag_Code 기반 활동 분류
                    # G1~G4: 근무영역, N1~N2: 비근무영역, T1~T3: 이동구간
                    daily_data['tag_code'] = daily_data['Tag_Code'].fillna('G1')  # 기본값
                    daily_data['space_type'] = daily_data['공간구분_NM'].fillna('근무영역')  # 기본값
                    daily_data['detail_type'] = daily_data['세부유형_NM'].fillna('주업무공간')  # 기본값
                    daily_data['allowed_activities'] = daily_data['라벨링_활동'].fillna('업무, 식사, 휴게')  # 기본값
                    
                    # 기존 컬럼과의 호환성 유지
                    # Tag_Code를 기반으로 work_area_type 설정
                    daily_data.loc[daily_data['tag_code'].str.startswith('G'), 'work_area_type'] = 'Y'  # 근무영역
                    daily_data.loc[daily_data['tag_code'].str.startswith('N'), 'work_area_type'] = 'N'  # 비근무영역
                    daily_data.loc[daily_data['tag_code'].str.startswith('T'), 'work_area_type'] = 'T'  # 이동구간
                else:
                    # 기존 방식 유지 (호환성)
                    daily_data['work_area_type'] = daily_data['근무구역여부'].fillna('Y')
                    daily_data['work_status'] = daily_data['근무'].fillna('W')
                    daily_data['activity_label'] = daily_data['라벨링'].fillna('YW')
                
                # Tag_Code 기반 기본 활동 분류
                if 'tag_code' in daily_data.columns:
                    # G1: 주업무공간 -> 업무
                    daily_data.loc[daily_data['tag_code'] == 'G1', 'activity_code'] = 'WORK'
                    
                    # G2: 보조업무공간 -> 준비
                    daily_data.loc[daily_data['tag_code'] == 'G2', 'activity_code'] = 'WORK_PREPARATION'
                    
                    # G3: 협업공간 -> 회의
                    daily_data.loc[daily_data['tag_code'] == 'G3', 'activity_code'] = 'MEETING'
                    
                    # G4: 교육공간 -> 교육
                    daily_data.loc[daily_data['tag_code'] == 'G4', 'activity_code'] = 'TRAINING'
                    
                    # N1: 휴게공간 -> 휴게
                    daily_data.loc[daily_data['tag_code'] == 'N1', 'activity_code'] = 'REST'
                    
                    # N2: 복지공간 -> 휴게
                    daily_data.loc[daily_data['tag_code'] == 'N2', 'activity_code'] = 'REST'
                    
                    # T1: 건물/구역 연결 -> 내부이동
                    daily_data.loc[daily_data['tag_code'] == 'T1', 'activity_code'] = 'MOVEMENT'
                    
                    # T2: 출입포인트(IN) -> 출근
                    daily_data.loc[daily_data['tag_code'] == 'T2', 'activity_code'] = 'COMMUTE_IN'
                    
                    # T3: 출입포인트(OUT) -> 퇴근
                    daily_data.loc[daily_data['tag_code'] == 'T3', 'activity_code'] = 'COMMUTE_OUT'
                else:
                    # 기존 라벨링 기반 분류 (호환성)
                    if 'activity_label' in daily_data.columns:
                        # GM: 근무구역 중 1선게이트로 들어옴 (이동)
                        daily_data.loc[daily_data['activity_label'] == 'GM', 'activity_code'] = 'MOVEMENT'
                        
                        # NM: 비근무구역에서 이동중
                        daily_data.loc[daily_data['activity_label'] == 'NM', 'activity_code'] = 'MOVEMENT'
                        
                        # YW: 근무구역에서 근무중
                        daily_data.loc[daily_data['activity_label'] == 'YW', 'activity_code'] = 'WORK'
                        
                        # NN: 비근무구역에서 비근무중 (휴식)
                        daily_data.loc[daily_data['activity_label'] == 'NN', 'activity_code'] = 'REST'
                        
                        # YM: 근무구역에서 이동중
                        daily_data.loc[daily_data['activity_label'] == 'YM', 'activity_code'] = 'MOVEMENT'
            
            # HMM 분류기 사용
            try:
                hmm_classifier = HMMActivityClassifier()
                daily_data = hmm_classifier.classify(daily_data, tag_location_master)
                self.logger.info("HMM 분류 성공")
            except Exception as hmm_error:
                self.logger.warning(f"HMM 분류 실패, 규칙 기반으로 대체: {hmm_error}")
                # 규칙 기반 분류로 폴백
                daily_data = self._apply_rule_based_classification(daily_data, tag_location_master)
            
            # Tag_Code 기반 신뢰도 세분화
            if 'tag_code' in daily_data.columns:
                # T2, T3 (출퇴근 포인트)는 가장 확실한 데이터 - 100%
                daily_data.loc[daily_data['tag_code'].isin(['T2', 'T3']), 'confidence'] = 100
                
                # G3 (협업공간), G4 (교육공간)는 명확한 활동 - 95%
                daily_data.loc[daily_data['tag_code'].isin(['G3', 'G4']), 'confidence'] = 95
                
                # G1 (주업무공간), G2 (보조업무공간)는 일반 작업 - 90%
                daily_data.loc[daily_data['tag_code'].isin(['G1', 'G2']), 'confidence'] = 90
                
                # N1, N2 (휴게/복지공간) - 90%
                daily_data.loc[daily_data['tag_code'].isin(['N1', 'N2']), 'confidence'] = 90
                
                # T1 (내부 이동) - 85%
                daily_data.loc[daily_data['tag_code'] == 'T1', 'confidence'] = 85
            
            # 우선순위 기반 상세 활동 분류
            # 참고: Tag_Code T2(출근), T3(퇴근)이 이미 설정되어 있으므로, 
            # 더 정확한 출퇴근 시간대 검증만 추가
            
            # 1. 식사시간 분류 (CAFETERIA 위치 + 시간대)
            cafeteria_mask = daily_data['DR_NM'].str.contains('CAFETERIA|식당|구내식당', case=False, na=False)
            
            # 시간대별 식사 분류 (더 정확한 시간대)
            breakfast_mask = cafeteria_mask & (daily_data['datetime'].dt.time >= pd.to_datetime('06:30').time()) & (daily_data['datetime'].dt.time <= pd.to_datetime('09:00').time())
            lunch_mask = cafeteria_mask & (daily_data['datetime'].dt.time >= pd.to_datetime('11:20').time()) & (daily_data['datetime'].dt.time <= pd.to_datetime('13:20').time())
            dinner_mask = cafeteria_mask & (daily_data['datetime'].dt.time >= pd.to_datetime('17:00').time()) & (daily_data['datetime'].dt.time <= pd.to_datetime('20:00').time())
            midnight_mask = cafeteria_mask & ((daily_data['datetime'].dt.time >= pd.to_datetime('23:30').time()) | (daily_data['datetime'].dt.time <= pd.to_datetime('01:00').time()))
            
            daily_data.loc[breakfast_mask, 'activity_code'] = 'BREAKFAST'
            daily_data.loc[lunch_mask, 'activity_code'] = 'LUNCH'
            daily_data.loc[dinner_mask, 'activity_code'] = 'DINNER'
            daily_data.loc[midnight_mask, 'activity_code'] = 'MIDNIGHT_MEAL'
            
            # 식사 활동은 위치+시간이 모두 일치하므로 신뢰도 상향
            meal_masks = breakfast_mask | lunch_mask | dinner_mask | midnight_mask
            # 식사 활동이면서 tag_code가 G1인 경우만 95%로 상향 (나머지는 기존 유지)
            if 'tag_code' in daily_data.columns:
                daily_data.loc[meal_masks & (daily_data['tag_code'] == 'G1'), 'confidence'] = 95
            
            # 2. 특수 활동 분류 (위치명 기반 세부 분류)
            # 회의실
            meeting_mask = daily_data['DR_NM'].str.contains('MEETING|회의|CONFERENCE', case=False, na=False)
            daily_data.loc[meeting_mask, 'activity_code'] = 'MEETING'
            # tag_code가 G3(협업공간)이 아닌 경우만 신뢰도 조정
            if 'tag_code' in daily_data.columns:
                daily_data.loc[meeting_mask & (daily_data['tag_code'] != 'G3'), 'confidence'] = 88
            
            # 피트니스/운동실
            fitness_mask = daily_data['DR_NM'].str.contains('FITNESS|GYM|체력단련|운동실', case=False, na=False)
            daily_data.loc[fitness_mask, 'activity_code'] = 'FITNESS'
            # tag_code가 N2(복지공간)이 아닌 경우만 신뢰도 조정
            if 'tag_code' in daily_data.columns:
                daily_data.loc[fitness_mask & (daily_data['tag_code'] != 'N2'), 'confidence'] = 87
            
            # 장비실/기계실
            equipment_mask = daily_data['DR_NM'].str.contains('EQUIPMENT|MACHINE|장비|기계실', case=False, na=False)
            daily_data.loc[equipment_mask & (daily_data['activity_code'] == 'WORK'), 'activity_code'] = 'EQUIPMENT_OPERATION'
            
            # 작업준비실
            prep_mask = daily_data['DR_NM'].str.contains('PREP|준비실|SETUP', case=False, na=False)
            daily_data.loc[prep_mask & (daily_data['activity_code'] == 'WORK'), 'activity_code'] = 'WORK_PREPARATION'
            
            # 휴게실
            rest_mask = daily_data['DR_NM'].str.contains('REST|LOUNGE|휴게실|탈의실', case=False, na=False)
            daily_data.loc[rest_mask, 'activity_code'] = 'REST'
            # tag_code가 N1(휴게공간)이 아닌 경우만 신뢰도 조정
            if 'tag_code' in daily_data.columns:
                daily_data.loc[rest_mask & (daily_data['tag_code'] != 'N1'), 'confidence'] = 86
            
            # 3. 집중근무 판별 (같은 작업 위치에 30분 이상 체류)
            # 체류시간 계산
            daily_data['next_time'] = daily_data['datetime'].shift(-1)
            daily_data['duration_minutes'] = (daily_data['next_time'] - daily_data['datetime']).dt.total_seconds() / 60
            
            # NaN 값 처리
            daily_data['duration_minutes'] = daily_data['duration_minutes'].fillna(5)  # 기본값 5분
            
            # 마지막 레코드는 5분으로 가정
            if len(daily_data) > 0:
                daily_data.loc[daily_data.index[-1], 'duration_minutes'] = 5
            
            # 같은 위치에서 30분 이상 작업한 경우 집중근무로 분류
            focused_work_mask = (
                (daily_data['activity_code'] == 'WORK') & 
                (daily_data['duration_minutes'] >= 30) &
                (daily_data['DR_NM'].str.contains('WORK_AREA', case=False, na=False))
            )
            daily_data.loc[focused_work_mask, 'activity_code'] = 'FOCUSED_WORK'
            # 집중근무는 추론 기반이므로 약간 낮은 신뢰도
            daily_data.loc[focused_work_mask & (daily_data['confidence'] > 85), 'confidence'] = 83
            
            # 4. 활동 타입 매핑 (이전 버전과의 호환성)
            activity_type_mapping = {
                'WORK': 'work',
                'FOCUSED_WORK': 'work',
                'EQUIPMENT_OPERATION': 'work',
                'WORK_PREPARATION': 'work',
                'WORKING': 'work',
                'TRAINING': 'education',
                'MEETING': 'meeting',
                'MOVEMENT': 'movement',
                'COMMUTE_IN': 'commute',
                'COMMUTE_OUT': 'commute',
                'BREAKFAST': 'breakfast',
                'LUNCH': 'lunch',
                'DINNER': 'dinner',
                'MIDNIGHT_MEAL': 'midnight_meal',
                'REST': 'rest',
                'FITNESS': 'rest',
                'LEAVE': 'rest',
                'IDLE': 'rest',
                'UNKNOWN': 'work'
            }
            daily_data['activity_type'] = daily_data['activity_code'].map(activity_type_mapping).fillna('work')
            
            return daily_data
            
        except Exception as e:
            self.logger.error(f"활동 분류 실패: {e}")
            # 오류 시에도 기본값 설정
            if 'activity_code' not in daily_data.columns:
                daily_data['activity_code'] = 'WORK'
            if 'activity_type' not in daily_data.columns:
                daily_data['activity_type'] = 'work'
            if 'duration_minutes' not in daily_data.columns:
                daily_data['duration_minutes'] = 5
            if 'confidence' not in daily_data.columns:
                daily_data['confidence'] = 80
            return daily_data
    
    def _apply_rule_based_classification(self, daily_data: pd.DataFrame, tag_location_master: pd.DataFrame) -> pd.DataFrame:
        """
        규칙 기반 활동 분류 (HMM 실패 시 폴백)
        """
        # 기존 규칙 기반 로직을 여기에 구현
        # 현재 코드에서는 이미 기본값이 설정되어 있으므로
        # 추가적인 규칙 기반 분류는 필요시 구현
        return daily_data
    
    def analyze_daily_data(self, employee_id: str, selected_date: date, classified_data: pd.DataFrame):
        """일일 데이터 분석"""
        try:
            # 근무시간 계산
            work_start = classified_data['datetime'].min()
            work_end = classified_data['datetime'].max()
            total_hours = (work_end - work_start).total_seconds() / 3600
            
            # 활동별 시간 집계 (새로운 activity_code 기준)
            if 'duration_minutes' in classified_data.columns:
                activity_summary = classified_data.groupby('activity_code')['duration_minutes'].sum()
                activity_type_summary = classified_data.groupby('activity_type')['duration_minutes'].sum()
                
                # 근무구역별 시간 집계
                if 'work_area_type' in classified_data.columns:
                    area_summary = classified_data.groupby('work_area_type')['duration_minutes'].sum()
                else:
                    area_summary = pd.Series()
            else:
                # duration_minutes가 없으면 기본값 5분으로 가정
                classified_data['duration_minutes'] = 5
                activity_summary = classified_data.groupby('activity_code')['duration_minutes'].sum()
                activity_type_summary = classified_data.groupby('activity_type')['duration_minutes'].sum()
                
                if 'work_area_type' in classified_data.columns:
                    area_summary = classified_data.groupby('work_area_type')['duration_minutes'].sum()
                else:
                    area_summary = pd.Series()
            
            # 구간별 활동 정리
            activity_segments = []
            for idx, row in classified_data.iterrows():
                # next_time이 NaT인 경우 처리
                end_time = row.get('next_time')
                if pd.isna(end_time):
                    end_time = row['datetime'] + timedelta(minutes=5)
                
                activity_segments.append({
                    'start_time': row['datetime'],
                    'end_time': end_time,
                    'activity': row['activity_type'],
                    'activity_code': row.get('activity_code', 'WORK'),
                    'location': row['DR_NM'],
                    'duration_minutes': row.get('duration_minutes', 5),
                    'confidence': row.get('confidence', 80)  # 신뢰도 추가
                })
            
            # Claim 데이터 가져오기
            claim_data = self.get_daily_claim_data(employee_id, selected_date)
            
            # 데이터 품질 분석
            data_quality = self.analyze_data_quality(classified_data)
            
            # 활동별 시간 통계 (시간 단위로)
            work_time_analysis = {
                'actual_work_hours': activity_type_summary.get('work', 0) / 60,
                'claimed_work_hours': claim_data['claim_hours'] if claim_data else 8.0,
                'efficiency_ratio': 0,
                'work_breakdown': {}
            }
            
            # 효율성 계산
            if work_time_analysis['claimed_work_hours'] > 0:
                work_time_analysis['efficiency_ratio'] = (
                    work_time_analysis['actual_work_hours'] / 
                    work_time_analysis['claimed_work_hours'] * 100
                )
            
            # 활동별 시간 분석
            for activity_type, minutes in activity_type_summary.items():
                work_time_analysis['work_breakdown'][activity_type] = minutes / 60
            
            return {
                'employee_id': employee_id,
                'analysis_date': selected_date,
                'work_start': work_start,
                'work_end': work_end,
                'total_hours': total_hours,
                'activity_summary': activity_summary.to_dict(),
                'area_summary': area_summary.to_dict() if not area_summary.empty else {},
                'activity_segments': activity_segments,
                'raw_data': classified_data,
                'total_records': len(classified_data),
                'claim_data': claim_data,
                'data_quality': data_quality,
                'work_time_analysis': work_time_analysis
            }
            
        except Exception as e:
            self.logger.error(f"일일 데이터 분석 실패: {e}")
            return None
    
    def analyze_data_quality(self, classified_data: pd.DataFrame) -> dict:
        """데이터 품질 분석"""
        if 'confidence' not in classified_data.columns:
            return {
                'overall_quality_score': 80,
                'tag_data_completeness': 100,
                'confidence_distribution': {
                    'high': 50,
                    'medium': 40,
                    'low': 10
                }
            }
        
        # 신뢰도 분포 계산
        confidence_values = classified_data['confidence']
        high_conf = (confidence_values >= 90).sum()
        medium_conf = ((confidence_values >= 80) & (confidence_values < 90)).sum()
        low_conf = (confidence_values < 80).sum()
        total = len(classified_data)
        
        confidence_dist = {
            'high': round(high_conf / total * 100, 1) if total > 0 else 0,
            'medium': round(medium_conf / total * 100, 1) if total > 0 else 0,
            'low': round(low_conf / total * 100, 1) if total > 0 else 0
        }
        
        # 전체 품질 점수 (평균 신뢰도)
        overall_score = round(confidence_values.mean(), 1) if len(confidence_values) > 0 else 80
        
        # 태그 데이터 완성도 (태그 코드가 있는 비율)
        if 'tag_code' in classified_data.columns:
            completeness = (classified_data['tag_code'].notna().sum() / total * 100) if total > 0 else 0
        else:
            completeness = 100
        
        return {
            'overall_quality_score': overall_score,
            'tag_data_completeness': round(completeness, 1),
            'confidence_distribution': confidence_dist
        }
    
    def render(self):
        """대시보드 렌더링"""
        st.markdown("### 👤 개인별 근무 분석")
        
        # 직원 선택 및 기간 설정
        self.render_controls()
        
        # 분석 실행 버튼
        if st.button("🔍 분석 실행", type="primary"):
            self.execute_analysis()
    
    def render_controls(self):
        """컨트롤 패널 렌더링"""
        # 실제 데이터에서 직원 목록 가져오기
        employee_list = self.get_available_employees()
        date_range_info = self.get_available_date_range()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # 직원 선택 방식
            selection_method = st.radio(
                "직원 선택 방식",
                ["목록에서 선택", "직접 입력"],
                key="employee_selection_method"
            )
            
            if selection_method == "목록에서 선택":
                if employee_list:
                    employee_id = st.selectbox(
                        "직원 선택",
                        employee_list,
                        key="individual_employee_select"
                    )
                else:
                    st.warning("로드된 직원 데이터가 없습니다.")
                    employee_id = st.text_input("직원 ID 입력", key="manual_employee_input")
            else:
                employee_id = st.text_input(
                    "직원 ID 입력",
                    placeholder="예: E001234",
                    key="individual_employee_input"
                )
            
            st.session_state.selected_employee = employee_id
        
        with col2:
            # 분석 날짜 (단일 날짜 선택)
            st.markdown("**분석 날짜**")
            
            # 사용 가능한 날짜 범위 표시
            if date_range_info:
                st.info(f"데이터 범위: {date_range_info['min_date']} ~ {date_range_info['max_date']}")
                
                # 기본값을 데이터 범위 내로 설정
                default_date = min(date_range_info['max_date'], date.today())
                
                selected_date = st.date_input(
                    "날짜 선택",
                    value=default_date,
                    min_value=date_range_info['min_date'],
                    max_value=date_range_info['max_date'],
                    key="individual_analysis_date"
                )
            else:
                # 데이터가 없을 경우 기본값 사용
                selected_date = st.date_input(
                    "날짜 선택",
                    value=date.today(),
                    key="individual_analysis_date_default"
                )
            
            st.session_state.analysis_date = selected_date
        
        with col3:
            # 분석 옵션
            analysis_options = st.multiselect(
                "분석 옵션",
                ["근무시간 분석", "식사시간 분석", "교대 근무 분석", "효율성 분석"],
                default=["근무시간 분석", "효율성 분석"],
                key="individual_analysis_options"
            )
            st.session_state.analysis_options = analysis_options
    
    def execute_analysis(self):
        """분석 실행"""
        employee_id = st.session_state.get('selected_employee')
        selected_date = st.session_state.get('analysis_date')
        
        if not employee_id or not selected_date:
            st.error("직원과 분석 날짜를 선택해주세요.")
            return
        
        try:
            # 분석 실행
            with st.spinner("분석 중..."):
                # 실제 데이터 가져오기
                daily_data = self.get_daily_tag_data(employee_id, selected_date)
                
                if daily_data is None or daily_data.empty:
                    st.warning(f"선택한 날짜({selected_date})에 해당 직원({employee_id})의 데이터가 없습니다.")
                    return
                
                # 활동 분류 수행
                classified_data = self.classify_activities(daily_data)
                
                # 분석 결과 생성
                analysis_result = self.analyze_daily_data(employee_id, selected_date, classified_data)
                
                # 결과 렌더링
                self.render_analysis_results(analysis_result)
                
        except Exception as e:
            st.error(f"분석 중 오류 발생: {e}")
            self.logger.error(f"개인 분석 오류: {e}")
    
    def create_sample_analysis_result(self, employee_id: str, date_range: tuple):
        """샘플 분석 결과 생성"""
        return {
            'employee_id': employee_id,
            'analysis_period': {
                'start_date': date_range[0].isoformat(),
                'end_date': date_range[1].isoformat()
            },
            'work_time_analysis': {
                'actual_work_hours': 8.5,
                'claimed_work_hours': 8.0,
                'efficiency_ratio': 89.5,
                'work_breakdown': {
                    'work': 6.5,
                    'meeting': 1.2,
                    'movement': 0.8
                }
            },
            'meal_time_analysis': {
                'meal_patterns': {
                    '조식': {'frequency': 5, 'avg_duration': 25},
                    '중식': {'frequency': 7, 'avg_duration': 45},
                    '석식': {'frequency': 3, 'avg_duration': 35},
                    '야식': {'frequency': 2, 'avg_duration': 20}
                },
                'total_meal_time': 180
            },
            'shift_analysis': {
                'preferred_shift': '주간',
                'shift_patterns': {
                    '주간': {'work_hours': 6.5, 'activity_count': 45},
                    '야간': {'work_hours': 2.0, 'activity_count': 15}
                }
            },
            'timeline_data': self.create_sample_timeline_data(date_range),
            'data_quality': {
                'overall_quality_score': 85,
                'tag_data_completeness': 90,
                'confidence_distribution': {
                    'high': 70,
                    'medium': 25,
                    'low': 5
                }
            }
        }
    
    def create_sample_timeline_data(self, date_range: tuple):
        """샘플 타임라인 데이터 생성"""
        timeline_data = []
        
        # 하루 샘플 데이터 생성
        base_date = date_range[0]
        activities = [
            {'time': '08:00', 'activity': '출근', 'location': 'GATE_A', 'confidence': 100},
            {'time': '08:15', 'activity': '근무', 'location': 'WORK_AREA_1', 'confidence': 95},
            {'time': '10:30', 'activity': '회의', 'location': 'MEETING_ROOM_1', 'confidence': 90},
            {'time': '11:30', 'activity': '근무', 'location': 'WORK_AREA_1', 'confidence': 95},
            {'time': '12:00', 'activity': '중식', 'location': 'CAFETERIA', 'confidence': 100},
            {'time': '13:00', 'activity': '근무', 'location': 'WORK_AREA_1', 'confidence': 95},
            {'time': '15:00', 'activity': '이동', 'location': 'CORRIDOR', 'confidence': 80},
            {'time': '15:30', 'activity': '작업', 'location': 'WORK_AREA_2', 'confidence': 90},
            {'time': '17:00', 'activity': '퇴근', 'location': 'GATE_A', 'confidence': 100}
        ]
        
        for activity in activities:
            timeline_data.append({
                'datetime': datetime.combine(base_date, datetime.strptime(activity['time'], '%H:%M').time()),
                'activity': activity['activity'],
                'location': activity['location'],
                'confidence': activity['confidence']
            })
        
        return timeline_data
    
    def render_analysis_results(self, analysis_result: dict):
        """분석 결과 렌더링"""
        st.markdown("---")
        st.markdown(f"## 📊 {analysis_result['analysis_date']} 분석 결과")
        
        # 기본 정보
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("출근 시각", analysis_result['work_start'].strftime('%H:%M'))
        with col2:
            st.metric("퇴근 시각", analysis_result['work_end'].strftime('%H:%M'))
        with col3:
            st.metric("총 근무시간", f"{analysis_result['total_hours']:.1f}시간")
        with col4:
            st.metric("태그 기록 수", f"{analysis_result['total_records']}건")
        
        # Claim 데이터 비교 (있을 경우)
        if analysis_result.get('claim_data'):
            st.markdown("### 📋 근무시간 Claim 비교")
            self.render_claim_comparison(analysis_result)
        
        # 활동별 시간 요약
        st.markdown("### 📊 활동별 시간 분석")
        self.render_activity_summary(analysis_result)
        
        # 구역별 체류 시간 분석
        st.markdown("### 📍 구역별 체류 시간 분석")
        self.render_area_summary(analysis_result)
        
        # 시계열 타임라인
        st.markdown("### 📅 일일 활동 타임라인")
        self.render_timeline_view(analysis_result)
        
        # 상세 Gantt 차트
        st.markdown("### 📊 활동 시퀀스 타임라인")
        # 개선된 Gantt 차트 사용
        improved_chart = render_improved_gantt_chart(analysis_result)
        if improved_chart:
            st.plotly_chart(improved_chart, use_container_width=True)
        else:
            # fallback to original chart
            self.render_detailed_gantt_chart(analysis_result)
        
        # 상세 태그 기록
        st.markdown("### 📋 상세 태그 기록")
        self.render_detailed_records(analysis_result)
    
    def render_daily_summary(self, analysis_result: dict):
        """일일 활동 요약 렌더링 (UI 참조자료 기반)"""
        st.markdown("### 📈 일일 활동 요약")
        
        work_analysis = analysis_result['work_time_analysis']
        
        # 주요 지표 대시보드
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "실제 근무시간",
                f"{work_analysis['actual_work_hours']:.1f}h",
                f"{work_analysis['actual_work_hours'] - work_analysis['claimed_work_hours']:+.1f}h"
            )
        
        with col2:
            st.metric(
                "업무 효율성",
                f"{work_analysis['efficiency_ratio']:.1f}%",
                "2.3%"
            )
        
        with col3:
            st.metric(
                "데이터 신뢰도",
                f"{analysis_result['data_quality']['overall_quality_score']}%",
                "1.5%"
            )
        
        with col4:
            st.metric(
                "활동 다양성",
                f"{len(work_analysis['work_breakdown'])}개",
                "1개"
            )
        
        # 활동 분류별 시간 분포 (프로그레스 바 스타일)
        st.markdown("#### 📊 활동 분류별 시간 분포")
        
        work_breakdown = work_analysis['work_breakdown']
        total_hours = sum(work_breakdown.values())
        
        for activity, hours in work_breakdown.items():
            percentage = (hours / total_hours * 100) if total_hours > 0 else 0
            col1, col2, col3 = st.columns([2, 6, 2])
            
            with col1:
                st.write(f"**{activity}**")
            
            with col2:
                st.progress(percentage / 100)
            
            with col3:
                st.write(f"{hours:.1f}h ({percentage:.1f}%)")
    
    def render_activity_timeline(self, analysis_result: dict):
        """활동 타임라인 렌더링 (UI 참조자료 기반)"""
        st.markdown("### 📅 활동 타임라인")
        
        timeline_data = analysis_result['timeline_data']
        
        if not timeline_data:
            st.warning("타임라인 데이터가 없습니다.")
            return
        
        # 타임라인 데이터를 DataFrame으로 변환
        df_timeline = pd.DataFrame(timeline_data)
        
        # 24시간 타임라인 차트 생성
        fig = go.Figure()
        
        # 활동별 색상 매핑
        activity_colors = {
            '출근': self.colors['work'],
            '근무': self.colors['work'],
            '작업': self.colors['work'],
            '회의': self.colors['meeting'],
            '이동': self.colors['movement'],
            '중식': self.colors['meal'],
            '조식': self.colors['meal'],
            '석식': self.colors['meal'],
            '야식': self.colors['meal'],
            '휴식': self.colors['rest'],
            '퇴근': self.colors['work']
        }
        
        # 각 활동에 대한 점과 선 추가
        for i, row in df_timeline.iterrows():
            activity = row['activity']
            color = activity_colors.get(activity, self.colors['work'])
            
            # 신뢰도에 따른 투명도 조정
            confidence = row['confidence']
            opacity = 0.5 + (confidence / 100) * 0.5
            
            fig.add_trace(go.Scatter(
                x=[row['datetime']],
                y=[activity],
                mode='markers',
                marker=dict(
                    size=15,
                    color=color,
                    opacity=opacity,
                    line=dict(width=2, color='white')
                ),
                name=activity,
                hovertemplate=(
                    f"<b>{activity}</b><br>" +
                    f"시간: {row['datetime'].strftime('%H:%M')}<br>" +
                    f"위치: {row['location']}<br>" +
                    f"신뢰도: {confidence}%<br>" +
                    "<extra></extra>"
                ),
                showlegend=False
            ))
        
        # 레이아웃 설정
        fig.update_layout(
            title="일일 활동 타임라인",
            xaxis_title="시간",
            yaxis_title="활동",
            height=400,
            hovermode='closest'
        )
        
        # X축 시간 형식 설정
        fig.update_xaxes(
            tickformat='%H:%M',
            dtick=3600000,  # 1시간 간격
            tickangle=45
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 데이터 신뢰도 시각화
        st.markdown("#### 🎯 데이터 신뢰도 분석")
        
        confidence_dist = analysis_result['data_quality']['confidence_distribution']
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 신뢰도 분포 파이 차트
            fig_conf = px.pie(
                values=list(confidence_dist.values()),
                names=list(confidence_dist.keys()),
                title="데이터 신뢰도 분포",
                color_discrete_map={
                    'high': '#4CAF50',
                    'medium': '#FF9800',
                    'low': '#F44336'
                }
            )
            st.plotly_chart(fig_conf, use_container_width=True)
        
        with col2:
            # 신뢰도 통계
            st.markdown("**신뢰도 통계**")
            st.write(f"• 높은 신뢰도: {confidence_dist['high']}%")
            st.write(f"• 중간 신뢰도: {confidence_dist['medium']}%")
            st.write(f"• 낮은 신뢰도: {confidence_dist['low']}%")
            
            overall_score = analysis_result['data_quality']['overall_quality_score']
            st.write(f"• 전체 품질 점수: {overall_score}%")
    
    def render_detailed_analysis(self, analysis_result: dict):
        """상세 분석 결과 렌더링"""
        st.markdown("### 📋 상세 분석 결과")
        
        # 탭으로 구분하여 표시
        tab1, tab2, tab3, tab4 = st.tabs(["🍽️ 식사시간", "🔄 교대근무", "📊 효율성", "📈 트렌드"])
        
        with tab1:
            self.render_meal_analysis(analysis_result)
        
        with tab2:
            self.render_shift_analysis(analysis_result)
        
        with tab3:
            self.render_efficiency_analysis(analysis_result)
        
        with tab4:
            self.render_trend_analysis(analysis_result)
    
    def render_meal_analysis(self, analysis_result: dict):
        """식사시간 분석 렌더링"""
        st.markdown("#### 🍽️ 식사시간 분석 (4번 식사)")
        
        meal_analysis = analysis_result['meal_time_analysis']
        meal_patterns = meal_analysis['meal_patterns']
        
        # 식사별 통계
        col1, col2 = st.columns(2)
        
        with col1:
            # 식사 빈도 차트
            meal_names = list(meal_patterns.keys())
            frequencies = [meal_patterns[meal]['frequency'] for meal in meal_names]
            
            fig_freq = px.bar(
                x=meal_names,
                y=frequencies,
                title="식사별 빈도",
                color=meal_names,
                color_discrete_map={
                    '조식': '#FF6B6B',
                    '중식': '#4ECDC4',
                    '석식': '#45B7D1',
                    '야식': '#96CEB4'
                }
            )
            st.plotly_chart(fig_freq, use_container_width=True)
        
        with col2:
            # 식사 지속시간 차트
            durations = [meal_patterns[meal]['avg_duration'] for meal in meal_names]
            
            fig_duration = px.bar(
                x=meal_names,
                y=durations,
                title="식사별 평균 지속시간 (분)",
                color=meal_names,
                color_discrete_map={
                    '조식': '#FF6B6B',
                    '중식': '#4ECDC4',
                    '석식': '#45B7D1',
                    '야식': '#96CEB4'
                }
            )
            st.plotly_chart(fig_duration, use_container_width=True)
        
        # 식사 패턴 요약
        st.markdown("**식사 패턴 요약**")
        total_meal_time = meal_analysis['total_meal_time']
        st.write(f"• 총 식사시간: {total_meal_time}분 ({total_meal_time/60:.1f}시간)")
        
        for meal, data in meal_patterns.items():
            st.write(f"• {meal}: {data['frequency']}회, 평균 {data['avg_duration']}분")
    
    def render_shift_analysis(self, analysis_result: dict):
        """교대근무 분석 렌더링"""
        st.markdown("#### 🔄 교대근무 분석")
        
        shift_analysis = analysis_result['shift_analysis']
        shift_patterns = shift_analysis['shift_patterns']
        
        # 교대별 근무시간 비교
        shifts = list(shift_patterns.keys())
        work_hours = [shift_patterns[shift]['work_hours'] for shift in shifts]
        activity_counts = [shift_patterns[shift]['activity_count'] for shift in shifts]
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig_hours = px.bar(
                x=shifts,
                y=work_hours,
                title="교대별 근무시간",
                color=shifts,
                color_discrete_map={
                    '주간': '#87CEEB',
                    '야간': '#4169E1'
                }
            )
            st.plotly_chart(fig_hours, use_container_width=True)
        
        with col2:
            fig_activities = px.bar(
                x=shifts,
                y=activity_counts,
                title="교대별 활동 수",
                color=shifts,
                color_discrete_map={
                    '주간': '#87CEEB',
                    '야간': '#4169E1'
                }
            )
            st.plotly_chart(fig_activities, use_container_width=True)
        
        # 교대 선호도
        preferred_shift = shift_analysis['preferred_shift']
        st.success(f"**선호 교대:** {preferred_shift}")
        
        # 교대별 효율성 계산
        for shift in shifts:
            hours = shift_patterns[shift]['work_hours']
            activities = shift_patterns[shift]['activity_count']
            efficiency = (activities / hours) if hours > 0 else 0
            st.write(f"• {shift} 교대 효율성: {efficiency:.1f} 활동/시간")
    
    def render_efficiency_analysis(self, analysis_result: dict):
        """효율성 분석 렌더링"""
        st.markdown("#### 📊 효율성 분석")
        
        work_analysis = analysis_result['work_time_analysis']
        efficiency_ratio = work_analysis['efficiency_ratio']
        
        # 효율성 게이지 차트
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = efficiency_ratio,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "업무 효율성 (%)"},
            delta = {'reference': 85},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, 50], 'color': "lightgray"},
                    {'range': [50, 80], 'color': "gray"},
                    {'range': [80, 100], 'color': "lightgreen"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))
        
        st.plotly_chart(fig_gauge, use_container_width=True)
        
        # 효율성 분석 요약
        st.markdown("**효율성 분석 요약**")
        
        if efficiency_ratio >= 90:
            st.success("🎉 매우 우수한 효율성을 보이고 있습니다!")
        elif efficiency_ratio >= 80:
            st.info("👍 양호한 효율성을 보이고 있습니다.")
        elif efficiency_ratio >= 70:
            st.warning("⚠️ 효율성 개선이 필요합니다.")
        else:
            st.error("❌ 효율성이 매우 낮습니다. 즉시 개선이 필요합니다.")
        
        # 개선 제안
        if efficiency_ratio < 85:
            st.markdown("**개선 제안**")
            st.write("• 집중 근무 시간 늘리기")
            st.write("• 불필요한 이동 줄이기")
            st.write("• 효율적인 업무 스케줄링")
    
    def render_trend_analysis(self, analysis_result: dict):
        """트렌드 분석 렌더링"""
        st.markdown("#### 📈 트렌드 분석")
        
        # 샘플 주간 트렌드 데이터
        dates = pd.date_range(start=date.today()-timedelta(days=7), 
                             end=date.today(), freq='D')
        
        trend_data = pd.DataFrame({
            'date': dates,
            'efficiency': np.random.uniform(80, 95, len(dates)),
            'work_hours': np.random.uniform(7.5, 9.0, len(dates)),
            'activity_count': np.random.randint(30, 60, len(dates))
        })
        
        # 트렌드 차트
        fig_trend = make_subplots(
            rows=2, cols=2,
            subplot_titles=('일별 효율성', '일별 근무시간', '일별 활동 수', '종합 트렌드'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": True}]]
        )
        
        # 효율성 트렌드
        fig_trend.add_trace(
            go.Scatter(x=trend_data['date'], y=trend_data['efficiency'], 
                      mode='lines+markers', name='효율성'),
            row=1, col=1
        )
        
        # 근무시간 트렌드
        fig_trend.add_trace(
            go.Scatter(x=trend_data['date'], y=trend_data['work_hours'], 
                      mode='lines+markers', name='근무시간'),
            row=1, col=2
        )
        
        # 활동 수 트렌드
        fig_trend.add_trace(
            go.Scatter(x=trend_data['date'], y=trend_data['activity_count'], 
                      mode='lines+markers', name='활동 수'),
            row=2, col=1
        )
        
        # 종합 트렌드 (효율성과 근무시간)
        fig_trend.add_trace(
            go.Scatter(x=trend_data['date'], y=trend_data['efficiency'], 
                      mode='lines', name='효율성', line=dict(color='blue')),
            row=2, col=2
        )
        
        fig_trend.add_trace(
            go.Scatter(x=trend_data['date'], y=trend_data['work_hours'], 
                      mode='lines', name='근무시간', line=dict(color='red')),
            row=2, col=2, secondary_y=True
        )
        
        fig_trend.update_layout(height=600, showlegend=True)
        st.plotly_chart(fig_trend, use_container_width=True)
        
        # 트렌드 분석 요약
        st.markdown("**트렌드 분석 요약**")
        
        efficiency_trend = "증가" if trend_data['efficiency'].iloc[-1] > trend_data['efficiency'].iloc[0] else "감소"
        work_hours_trend = "증가" if trend_data['work_hours'].iloc[-1] > trend_data['work_hours'].iloc[0] else "감소"
        
        st.write(f"• 효율성 트렌드: {efficiency_trend}")
        st.write(f"• 근무시간 트렌드: {work_hours_trend}")
        st.write(f"• 평균 일일 활동 수: {trend_data['activity_count'].mean():.1f}개")
    
    def render_activity_summary(self, analysis_result: dict):
        """활동별 시간 요약 렌더링"""
        activity_summary = analysis_result['activity_summary']
        
        # 데이터 준비
        activities = []
        for activity_code, minutes in activity_summary.items():
            activities.append({
                '활동': get_activity_name(activity_code, 'ko'),
                '시간(분)': round(minutes, 1),
                '시간': f"{int(minutes//60)}시간 {int(minutes%60)}분",
                '비율(%)': round(minutes / sum(activity_summary.values()) * 100, 1),
                'activity_code': activity_code  # 색상 매핑용
            })
        
        df_activities = pd.DataFrame(activities)
        
        # 차트와 테이블 표시
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # 파이 차트 - 새로운 색상 매핑
            color_map = {}
            for _, row in df_activities.iterrows():
                activity_name = row['활동']
                activity_code = row['activity_code']
                color_map[activity_name] = get_activity_color(activity_code)
            
            fig = px.pie(df_activities, values='시간(분)', names='활동', 
                        title='활동별 시간 분포',
                        color_discrete_map=color_map)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # 요약 테이블
            st.dataframe(df_activities[['활동', '시간', '비율(%)']], 
                        use_container_width=True, hide_index=True)
    
    def render_timeline_view(self, analysis_result: dict):
        """시계열 타임라인 뷰 렌더링 - Gantt 차트 형태"""
        segments = analysis_result['activity_segments']
        
        # 활동별 색상 및 한글명
        activity_colors = {
            'work': self.colors['work'],
            'meeting': self.colors['meeting'],
            'movement': self.colors['movement'],
            'breakfast': self.colors['meal'],
            'lunch': self.colors['meal'],
            'dinner': self.colors['meal'],
            'midnight_meal': self.colors['meal'],
            'rest': self.colors['rest']
        }
        
        activity_names = {
            'work': '업무',
            'meeting': '회의',
            'movement': '이동',
            'breakfast': '조식',
            'lunch': '중식',
            'dinner': '석식',
            'midnight_meal': '야식',
            'rest': '휴식'
        }
        
        # Gantt 차트 데이터 준비
        gantt_data = []
        for i, segment in enumerate(segments):
            # NaT 처리
            if pd.notna(segment['start_time']) and pd.notna(segment['end_time']):
                activity_code = segment.get('activity_code', 'WORK')
                gantt_data.append({
                    'Task': get_activity_name(activity_code, 'ko'),
                    'Start': segment['start_time'],
                    'Finish': segment['end_time'],
                    'Resource': activity_code,
                    'Location': segment['location'],
                    'Duration': segment['duration_minutes']
                })
        
        if not gantt_data:
            st.warning("타임라인 데이터가 없습니다.")
            return
        
        # Gantt 차트 생성
        df_gantt = pd.DataFrame(gantt_data)
        
        # 색상 매핑 생성
        color_map = {}
        for code in df_gantt['Resource'].unique():
            color_map[code] = get_activity_color(code)
        
        fig = px.timeline(
            df_gantt,
            x_start="Start",
            x_end="Finish",
            y="Task",
            color="Resource",
            color_discrete_map=color_map,
            hover_data={'Location': True, 'Duration': True},
            title="일일 활동 타임라인 (Gantt Chart)"
        )
        
        # 레이아웃 업데이트
        # 범례를 한글로 표시
        for trace in fig.data:
            if trace.name in color_map:
                # Resource 코드를 한글명으로 변환
                korean_name = get_activity_name(trace.name, 'ko')
                trace.name = korean_name
        
        fig.update_layout(
            height=300,
            xaxis_title="시간",
            yaxis_title="활동",
            showlegend=True,
            legend_title_text="활동 유형",
            hovermode='closest'
        )
        
        # Y축을 카테고리별로 정렬 (출근 맨 위, 퇴근 맨 아래)
        category_order = [
            '출근',  # 맨 위
            '집중근무', '근무', '작업중', '장비조작', '작업준비',  # 근무 관련
            '회의',  # 회의
            '조식', '중식', '석식', '야식',  # 식사
            '피트니스', '휴식',  # 휴식
            '이동',  # 이동
            '대기', '미분류',  # 기타
            '퇴근'  # 맨 아래
        ]
        # 실제 데이터에 있는 카테고리만 필터링하고 순서 유지
        actual_categories = list(df_gantt['Task'].unique())
        filtered_order = []
        
        # 정의된 순서대로 추가
        for cat in category_order:
            if cat in actual_categories:
                filtered_order.append(cat)
        
        # 정의되지 않은 카테고리가 있으면 중간에 추가
        for cat in actual_categories:
            if cat not in filtered_order:
                # 퇴근 바로 위에 추가
                if '퇴근' in filtered_order:
                    idx = filtered_order.index('퇴근')
                    filtered_order.insert(idx, cat)
                else:
                    filtered_order.append(cat)
        
        fig.update_yaxes(categoryorder="array", categoryarray=filtered_order)
        
        # X축 시간 포맷 설정
        fig.update_xaxes(
            tickformat='%H:%M',
            dtick=3600000,  # 1시간 간격
            tickangle=0
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def render_detailed_gantt_chart(self, analysis_result: dict):
        """상세 Gantt 차트 렌더링 - 모든 활동을 한 줄에 표시"""
        segments = analysis_result['activity_segments']
        
        # 활동별 색상
        activity_colors = {
            'work': self.colors['work'],
            'meeting': self.colors['meeting'],
            'movement': self.colors['movement'],
            'breakfast': self.colors['meal'],
            'lunch': self.colors['meal'],
            'dinner': self.colors['meal'],
            'midnight_meal': self.colors['meal'],
            'rest': self.colors['rest']
        }
        
        # 활동 한글명
        activity_names = {
            'work': '업무',
            'meeting': '회의',
            'movement': '이동',
            'breakfast': '조식',
            'lunch': '중식',
            'dinner': '석식',
            'midnight_meal': '야식',
            'rest': '휴식'
        }
        
        # 작업 시작/종료 시간
        work_start = analysis_result['work_start']
        work_end = analysis_result['work_end']
        
        # 모든 활동을 하나의 타임라인에 표시
        fig = go.Figure()
        
        for i, segment in enumerate(segments):
            if pd.notna(segment['start_time']) and pd.notna(segment['end_time']):
                activity_code = segment.get('activity_code', 'WORK')
                
                # 시간을 분 단위로 변환
                start_minutes = (segment['start_time'] - work_start).total_seconds() / 60
                duration = segment['duration_minutes']
                
                # hover 텍스트 생성
                hover_text = (
                    f"<b>{get_activity_name(activity_code, 'ko')}</b><br>" +
                    f"시간: {segment['start_time'].strftime('%H:%M')} - {segment['end_time'].strftime('%H:%M')}<br>" +
                    f"위치: {segment['location']}<br>" +
                    f"체류: {duration:.0f}분"
                )
                
                # 막대 추가
                fig.add_trace(go.Bar(
                    x=[duration],
                    y=['활동'],
                    orientation='h',
                    base=start_minutes,
                    marker_color=get_activity_color(activity_code),
                    name=get_activity_name(activity_code, 'ko'),
                    hovertemplate=hover_text + "<extra></extra>",
                    showlegend=False,
                    width=0.8
                ))
        
        # 레전드를 위한 더미 트레이스 추가
        added_legends = set()
        # 실제 데이터에 있는 활동 코드만 레전드에 추가
        activity_codes_in_data = set(seg.get('activity_code', 'WORK') for seg in segments)
        
        for activity_code in activity_codes_in_data:
            if activity_code not in added_legends:
                fig.add_trace(go.Scatter(
                    x=[None],
                    y=[None],
                    mode='markers',
                    marker=dict(color=get_activity_color(activity_code), size=10),
                    name=get_activity_name(activity_code, 'ko'),
                    showlegend=True
                ))
                added_legends.add(activity_code)
        
        # 레이아웃 설정
        total_minutes = (work_end - work_start).total_seconds() / 60
        
        fig.update_layout(
            title="하루 전체 활동 시퀀스",
            height=250,
            barmode='overlay',
            xaxis=dict(
                title="시간",
                tickmode='array',
                tickvals=[i * 60 for i in range(int(total_minutes // 60) + 2)],
                ticktext=[(work_start + timedelta(hours=i)).strftime('%H:%M') 
                         for i in range(int(total_minutes // 60) + 2)],
                range=[0, total_minutes]
            ),
            yaxis=dict(
                showticklabels=False,
                range=[-0.5, 0.5]
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 주요 활동 구간 표시
        st.markdown("#### 주요 활동 구간")
        
        # 30분 이상 체류한 구간만 표시
        major_segments = [s for s in segments if s['duration_minutes'] >= 30]
        
        if major_segments:
            segment_data = []
            for seg in major_segments[:10]:  # 상위 10개만
                # NaT 처리
                start_str = seg['start_time'].strftime('%H:%M') if pd.notna(seg['start_time']) else 'N/A'
                end_str = seg['end_time'].strftime('%H:%M') if pd.notna(seg['end_time']) else 'N/A'
                
                segment_data.append({
                    '시작': start_str,
                    '종료': end_str,
                    '활동': get_activity_name(seg.get('activity_code', 'WORK'), 'ko'),
                    '위치': seg['location'],
                    '체류시간': f"{int(seg['duration_minutes'])}분"
                })
            
            df_segments = pd.DataFrame(segment_data)
            st.dataframe(df_segments, use_container_width=True, hide_index=True)
    
    def render_detailed_records(self, analysis_result: dict):
        """상세 태그 기록 렌더링"""
        raw_data = analysis_result['raw_data']
        
        # 표시할 컬럼 선택
        display_columns = ['datetime', 'DR_NO', 'DR_NM', 'INOUT_GB', 'activity_code', 'activity_type', 
                          'work_area_type', 'work_status', 'activity_label', 'duration_minutes']
        
        # 일부 컬럼이 없을 수 있으므로 확인
        available_columns = [col for col in display_columns if col in raw_data.columns]
        
        # 컬럼명 한글화
        column_names = {
            'datetime': '시각',
            'DR_NO': '게이트 번호',
            'DR_NM': '위치',
            'INOUT_GB': '입/출',
            'activity_code': '활동 코드',
            'activity_type': '활동 분류',
            'work_area_type': '구역',
            'work_status': '상태',
            'activity_label': '라벨',
            'duration_minutes': '체류시간(분)'
        }
        
        # 데이터프레임 준비
        df_display = raw_data[available_columns].copy()
        df_display['datetime'] = df_display['datetime'].dt.strftime('%H:%M:%S')
        df_display['duration_minutes'] = df_display['duration_minutes'].round(1)
        
        # 활동 코드를 한글명으로 변환
        if 'activity_code' in df_display.columns:
            df_display['activity_code'] = df_display['activity_code'].apply(
                lambda x: get_activity_name(x, 'ko')
            )
        
        # 구역 타입 한글 변환
        if 'work_area_type' in df_display.columns:
            area_type_map = {'Y': '근무구역', 'G': '1선게이트', 'N': '비근무구역'}
            df_display['work_area_type'] = df_display['work_area_type'].map(area_type_map).fillna(df_display['work_area_type'])
        
        # 상태 한글 변환
        if 'work_status' in df_display.columns:
            status_map = {'W': '근무', 'M': '이동', 'N': '비근무'}
            df_display['work_status'] = df_display['work_status'].map(status_map).fillna(df_display['work_status'])
        
        df_display = df_display.rename(columns=column_names)
        
        # 필터링 옵션
        col1, col2 = st.columns(2)
        with col1:
            activity_filter = st.multiselect(
                "활동 유형 필터",
                options=df_display['활동 분류'].unique(),
                default=df_display['활동 분류'].unique()
            )
        
        with col2:
            location_filter = st.text_input("위치 검색", "")
        
        # 필터 적용
        filtered_df = df_display[df_display['활동 분류'].isin(activity_filter)]
        if location_filter:
            filtered_df = filtered_df[filtered_df['위치'].str.contains(location_filter, case=False, na=False)]
        
        # 데이터 표시 (height 제거하여 전체 표시)
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        
        # 다운로드 버튼
        csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 CSV 다운로드",
            data=csv,
            file_name=f"태그기록_{analysis_result['employee_id']}_{analysis_result['analysis_date']}.csv",
            mime='text/csv'
        )
    
    def render_claim_comparison(self, analysis_result: dict):
        """Claim 데이터와 실제 근무시간 비교"""
        claim_data = analysis_result['claim_data']
        
        # 실제 근무시간과 Claim 시간 비교
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**🏷️ Claim 데이터**")
            st.write(f"• 신고 출근: {claim_data['claim_start']}")
            st.write(f"• 신고 퇴근: {claim_data['claim_end']}")
            st.write(f"• 신고 근무시간: {claim_data['claim_hours']}시간")
            st.write(f"• 근무유형: {claim_data['claim_type']}")
            if claim_data['overtime'] > 0:
                st.write(f"• 초과근무: {claim_data['overtime']}시간")
        
        with col2:
            st.markdown("**📍 실제 태그 데이터**")
            st.write(f"• 실제 출근: {analysis_result['work_start'].strftime('%H:%M')}")
            st.write(f"• 실제 퇴근: {analysis_result['work_end'].strftime('%H:%M')}")
            st.write(f"• 실제 근무시간: {analysis_result['total_hours']:.1f}시간")
            
            # 실제 활동 시간 계산
            activity_summary = analysis_result['activity_summary']
            work_activities = ['work', 'meeting']
            actual_work_time = sum(activity_summary.get(act, 0) for act in work_activities) / 60
            st.write(f"• 순수 업무시간: {actual_work_time:.1f}시간")
        
        with col3:
            st.markdown("**📊 차이 분석**")
            
            # 시간 차이 계산
            time_diff = analysis_result['total_hours'] - claim_data['claim_hours']
            
            if abs(time_diff) < 0.5:
                st.success(f"✅ 거의 일치 (차이: {abs(time_diff):.1f}시간)")
            elif time_diff > 0:
                st.warning(f"⚠️ 실제가 더 김 (+{time_diff:.1f}시간)")
            else:
                st.info(f"ℹ️ 신고가 더 김 ({time_diff:.1f}시간)")
            
            # 효율성 계산
            if claim_data['claim_hours'] > 0:
                efficiency = (actual_work_time / claim_data['claim_hours']) * 100
                st.write(f"• 업무 효율성: {efficiency:.1f}%")
        
        # 시각적 비교
        st.markdown("#### 📈 시간대별 비교")
        self.render_time_comparison_chart(analysis_result, claim_data)
    
    def render_time_comparison_chart(self, analysis_result: dict, claim_data: dict):
        """시간대별 비교 차트"""
        fig = go.Figure()
        
        # Claim 시간대
        claim_start_str = str(claim_data['claim_start'])
        claim_end_str = str(claim_data['claim_end'])
        
        # 시간 파싱 시도
        try:
            if len(claim_start_str) == 4:  # HHMM 형식
                claim_start_hour = int(claim_start_str[:2])
                claim_start_min = int(claim_start_str[2:])
            else:
                claim_start_hour = 8
                claim_start_min = 0
                
            if len(claim_end_str) == 4:  # HHMM 형식
                claim_end_hour = int(claim_end_str[:2])
                claim_end_min = int(claim_end_str[2:])
            else:
                claim_end_hour = 17
                claim_end_min = 0
        except:
            claim_start_hour, claim_start_min = 8, 0
            claim_end_hour, claim_end_min = 17, 0
        
        # 실제 근무시간
        actual_start = analysis_result['work_start'].hour + analysis_result['work_start'].minute / 60
        actual_end = analysis_result['work_end'].hour + analysis_result['work_end'].minute / 60
        
        # Claim 근무시간
        claim_start = claim_start_hour + claim_start_min / 60
        claim_end = claim_end_hour + claim_end_min / 60
        
        # 차트에 추가
        fig.add_trace(go.Bar(
            x=[actual_end - actual_start],
            y=['실제 근무'],
            orientation='h',
            name='실제',
            marker_color='lightblue',
            base=actual_start,
            text=f"{analysis_result['work_start'].strftime('%H:%M')} - {analysis_result['work_end'].strftime('%H:%M')}",
            textposition='inside'
        ))
        
        fig.add_trace(go.Bar(
            x=[claim_end - claim_start],
            y=['신고 근무'],
            orientation='h',
            name='Claim',
            marker_color='lightgreen',
            base=claim_start,
            text=f"{claim_start_hour:02d}:{claim_start_min:02d} - {claim_end_hour:02d}:{claim_end_min:02d}",
            textposition='inside'
        ))
        
        # 레이아웃
        fig.update_layout(
            title="근무시간 비교",
            xaxis_title="시간",
            height=200,
            showlegend=True,
            xaxis=dict(
                tickmode='linear',
                tick0=0,
                dtick=2,
                range=[0, 24]
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def render_area_summary(self, analysis_result: dict):
        """구역별 체류 시간 분석 렌더링"""
        area_summary = analysis_result.get('area_summary', {})
        
        if not area_summary:
            st.info("구역별 데이터가 없습니다.")
            return
        
        # 구역 한글명 매핑
        area_names = {
            'Y': '근무구역',
            'G': '1선게이트',
            'N': '비근무구역'
        }
        
        # 전체 시간 계산
        total_minutes = sum(area_summary.values())
        
        col1, col2, col3 = st.columns(3)
        
        # 근무구역 시간
        work_area_minutes = area_summary.get('Y', 0)
        work_area_hours = work_area_minutes / 60
        work_area_percent = (work_area_minutes / total_minutes * 100) if total_minutes > 0 else 0
        
        with col1:
            st.metric(
                "근무구역 체류",
                f"{work_area_hours:.1f}시간",
                f"{work_area_percent:.1f}%"
            )
        
        # 비근무구역 시간
        non_work_minutes = area_summary.get('N', 0)
        non_work_hours = non_work_minutes / 60
        non_work_percent = (non_work_minutes / total_minutes * 100) if total_minutes > 0 else 0
        
        with col2:
            st.metric(
                "비근무구역 체류",
                f"{non_work_hours:.1f}시간",
                f"{non_work_percent:.1f}%",
                delta_color="inverse"  # 비근무구역은 적을수록 좋음
            )
        
        # 게이트 통과 시간
        gate_minutes = area_summary.get('G', 0)
        gate_percent = (gate_minutes / total_minutes * 100) if total_minutes > 0 else 0
        
        with col3:
            st.metric(
                "게이트 통과",
                f"{gate_minutes:.0f}분",
                f"{gate_percent:.1f}%"
            )
        
        # 구역별 분포 차트
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # 파이 차트
            area_data = []
            for area_code, minutes in area_summary.items():
                area_data.append({
                    '구역': area_names.get(area_code, area_code),
                    '시간(분)': minutes,
                    '비율(%)': round(minutes / total_minutes * 100, 1) if total_minutes > 0 else 0
                })
            
            df_areas = pd.DataFrame(area_data)
            
            # 색상 설정
            colors = {
                '근무구역': '#2E86AB',  # 파란색
                '비근무구역': '#FF6B6B',  # 빨간색
                '1선게이트': '#FFD700'  # 금색
            }
            
            fig = px.pie(
                df_areas, 
                values='시간(분)', 
                names='구역',
                title='구역별 체류 시간 분포',
                color_discrete_map=colors
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # 요약 테이블
            st.markdown("#### 구역별 상세")
            for _, row in df_areas.iterrows():
                st.write(f"**{row['구역']}**")
                st.write(f"- 시간: {int(row['시간(분)']//60)}시간 {int(row['시간(분)']%60)}분")
                st.write(f"- 비율: {row['비율(%)']}%")
                st.write("")
        
        # 비근무구역 체류가 많은 경우 경고
        if non_work_percent > 30:
            st.warning(f"⚠️ 비근무구역 체류 시간이 {non_work_percent:.1f}%로 높습니다. 업무 효율성 개선이 필요할 수 있습니다.")
        elif non_work_percent > 20:
            st.info(f"ℹ️ 비근무구역 체류 시간: {non_work_percent:.1f}%")