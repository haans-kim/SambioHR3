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
from datetime import datetime, timedelta, date, time
import logging
from pathlib import Path
from typing import List, Dict, Any
import matplotlib.pyplot as plt
import sqlite3
from sqlalchemy import text
from .improved_gantt_chart import render_improved_gantt_chart
from ...utils.recent_views_manager import RecentViewsManager, render_recent_views_section
# HMM 제거됨 - 태그 기반 규칙만 사용
# from .hmm_classifier import HMMActivityClassifier

from ...analysis import IndividualAnalyzer
from ...analysis.network_analyzer import NetworkAnalyzer
from ...tag_system.confidence_calculator_v2 import ConfidenceCalculatorV2
from ...tag_system.rule_integration import apply_rules_to_tags, get_rule_integration
from ...tag_system.confidence_state import ActivityState
from ...config.activity_types import (
    ACTIVITY_TYPES, get_activity_color, get_activity_name,
    get_activity_type, ActivityType
)

class IndividualDashboard:
    """개인별 대시보드 컴포넌트"""
    
    def __init__(self, individual_analyzer: IndividualAnalyzer):
        self.analyzer = individual_analyzer
        self.logger = logging.getLogger(__name__)
        
        # 싱글톤 DatabaseManager 사용
        from ...database import get_database_manager
        self.db_manager = get_database_manager()
        
        # 신뢰지수 계산기 초기화
        self.confidence_calculator = ConfidenceCalculatorV2()
        
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
            from ...database import get_pickle_manager
            pickle_manager = get_pickle_manager()
            
            # 조직현황 데이터에서 직원 목록 우선 추출 (전체 직원 정보)
            org_data = pickle_manager.load_dataframe(name='organization_data')
            if org_data is not None and '사번' in org_data.columns:
                # 사번과 이름을 함께 표시
                employees = []
                for _, row in org_data.iterrows():
                    employee_display = f"{row['사번']} - {row['성명']}"
                    employees.append(employee_display)
                return sorted(employees)
            
            # 태깅 데이터에서 직원 목록 추출
            tag_data = pickle_manager.load_dataframe(name='tag_data')
            if tag_data is not None and '사번' in tag_data.columns:
                employees = sorted(tag_data['사번'].unique().tolist())
                return employees  # 전체 직원 표시
            
            # 다른 데이터 소스 시도
            claim_data = pickle_manager.load_dataframe(name='claim_data')
            if claim_data is not None and '사번' in claim_data.columns:
                employees = sorted(claim_data['사번'].unique().tolist())
                return employees
            
            return []
        except Exception as e:
            self.logger.warning(f"직원 목록 로드 실패: {e}")
            return []
    
    def get_employee_info(self, employee_id: str) -> dict:
        """직원 정보 조회"""
        try:
            from ...database import get_pickle_manager
            pickle_manager = get_pickle_manager()
            
            # 조직현황 데이터에서 직원 정보 조회
            org_data = pickle_manager.load_dataframe(name='organization_data')
            if org_data is not None and '사번' in org_data.columns:
                # 사번 형식 맞추기
                if ' - ' in str(employee_id):
                    employee_id = employee_id.split(' - ')[0].strip()
                
                # 직원 정보 찾기 (사번 타입 맞춰서 비교)
                org_data['사번'] = org_data['사번'].astype(str)
                emp_info = org_data[org_data['사번'] == str(employee_id)]
                if not emp_info.empty:
                    row = emp_info.iloc[0]
                    return {
                        'id': employee_id,
                        'name': row.get('성명', employee_id),
                        'department': row.get('조', row.get('팀', row.get('BU', 'N/A'))),
                        'center': row.get('센터', 'N/A'),
                        'bu': row.get('BU', 'N/A'),
                        'team': row.get('팀', 'N/A'),
                        'position': row.get('직급', 'N/A')
                    }
            
            # 조직 데이터에서 찾을 수 없으면 기본값 반환
            return {
                'id': employee_id,
                'name': employee_id,
                'department': 'N/A',
                'center': 'N/A',
                'bu': 'N/A',
                'team': 'N/A',
                'position': 'N/A'
            }
            
        except Exception as e:
            self.logger.warning(f"직원 정보 조회 실패: {e}")
            return {'id': employee_id, 'name': employee_id, 'department': 'N/A'}
    
    def get_organization_hierarchy(self):
        """조직 계층 구조 데이터 가져오기"""
        try:
            from ...database import get_pickle_manager
            pickle_manager = get_pickle_manager()
            
            # 조직현황 데이터 로드
            org_data = pickle_manager.load_dataframe(name='organization_data')
            if org_data is None:
                return None
            
            # 조직 계층 구조 생성
            hierarchy = {
                'centers': sorted(org_data['센터'].dropna().unique().tolist()),
                'by_center': {}
            }
            
            # 센터별로 하위 조직 구조 생성
            for center in hierarchy['centers']:
                center_data = org_data[org_data['센터'] == center]
                
                hierarchy['by_center'][center] = {
                    'bus': sorted(center_data['BU'].dropna().unique().tolist()),
                    'by_bu': {}
                }
                
                # BU별로 하위 조직 구조 생성
                for bu in hierarchy['by_center'][center]['bus']:
                    bu_data = center_data[center_data['BU'] == bu]
                    
                    hierarchy['by_center'][center]['by_bu'][bu] = {
                        'teams': sorted(bu_data['팀'].dropna().unique().tolist()),
                        'by_team': {}
                    }
                    
                    # 팀별로 하위 조직 구조 생성
                    for team in hierarchy['by_center'][center]['by_bu'][bu]['teams']:
                        team_data = bu_data[bu_data['팀'] == team]
                        
                        hierarchy['by_center'][center]['by_bu'][bu]['by_team'][team] = {
                            'groups': sorted(team_data['그룹'].dropna().unique().tolist()),
                            'by_group': {}
                        }
                        
                        # 그룹별로 파트 구조 생성
                        for group in hierarchy['by_center'][center]['by_bu'][bu]['by_team'][team]['groups']:
                            group_data = team_data[team_data['그룹'] == group]
                            
                            hierarchy['by_center'][center]['by_bu'][bu]['by_team'][team]['by_group'][group] = {
                                'parts': sorted(group_data['파트'].dropna().unique().tolist()),
                                'employees': {}
                            }
                            
                            # 파트별로 직원 목록 생성
                            for part in hierarchy['by_center'][center]['by_bu'][bu]['by_team'][team]['by_group'][group]['parts']:
                                part_data = group_data[group_data['파트'] == part]
                                employees = part_data[['사번', '성명', '직급명']].to_dict('records')
                                hierarchy['by_center'][center]['by_bu'][bu]['by_team'][team]['by_group'][group]['employees'][part] = employees
            
            return hierarchy
            
        except Exception as e:
            self.logger.warning(f"조직 계층 구조 로드 실패: {e}")
            return None
    
    def get_employees_by_organization(self, center=None, bu=None, team=None, group=None, part=None):
        """조직 단위별 직원 목록 가져오기"""
        try:
            from ...database import get_pickle_manager
            pickle_manager = get_pickle_manager()
            
            # 조직현황 데이터 로드
            org_data = pickle_manager.load_dataframe(name='organization_data')
            if org_data is None:
                return []
            
            # 필터링
            filtered_data = org_data
            
            if center and center != "전체":
                filtered_data = filtered_data[filtered_data['센터'] == center]
            
            if bu and bu != "전체":
                filtered_data = filtered_data[filtered_data['BU'] == bu]
            
            if team and team != "전체":
                filtered_data = filtered_data[filtered_data['팀'] == team]
            
            if group and group != "전체":
                filtered_data = filtered_data[filtered_data['그룹'] == group]
            
            if part and part != "전체":
                filtered_data = filtered_data[filtered_data['파트'] == part]
            
            # 직원 목록 생성
            employees = []
            for _, row in filtered_data.iterrows():
                employees.append({
                    'id': row['사번'],
                    'name': row['성명'],
                    'position': row.get('직급명', ''),
                    'display': f"{row['사번']} - {row['성명']} ({row.get('직급명', '')})"
                })
            
            return sorted(employees, key=lambda x: x['id'])
            
        except Exception as e:
            self.logger.warning(f"조직별 직원 목록 로드 실패: {e}")
            return []
    
    def render_organization_selection(self):
        """조직 계층 구조 기반 직원 선택 UI"""
        try:
            from ...database import get_pickle_manager
            pickle_manager = get_pickle_manager()
            
            # 조직현황 데이터 로드
            org_data = pickle_manager.load_dataframe(name='organization_data')
            if org_data is None:
                st.warning("조직 데이터가 없습니다.")
                return None
            
            # 센터 선택
            centers = ["전체"] + sorted(org_data['센터'].dropna().unique().tolist())
            selected_center = st.selectbox(
                "센터 선택",
                centers,
                key="org_center_select"
            )
            
            # BU 선택
            if selected_center != "전체":
                filtered_data = org_data[org_data['센터'] == selected_center]
                bus = ["전체"] + sorted(filtered_data['BU'].dropna().unique().tolist())
            else:
                bus = ["전체"]
            
            selected_bu = st.selectbox(
                "BU 선택",
                bus,
                key="org_bu_select"
            )
            
            # 팀 선택
            if selected_bu != "전체" and selected_center != "전체":
                filtered_data = org_data[
                    (org_data['센터'] == selected_center) & 
                    (org_data['BU'] == selected_bu)
                ]
                teams = ["전체"] + sorted(filtered_data['팀'].dropna().unique().tolist())
            else:
                teams = ["전체"]
            
            selected_team = st.selectbox(
                "팀 선택",
                teams,
                key="org_team_select"
            )
            
            # 그룹 선택
            if selected_team != "전체" and selected_bu != "전체" and selected_center != "전체":
                filtered_data = org_data[
                    (org_data['센터'] == selected_center) & 
                    (org_data['BU'] == selected_bu) &
                    (org_data['팀'] == selected_team)
                ]
                groups = ["전체"] + sorted(filtered_data['그룹'].dropna().unique().tolist())
            else:
                groups = ["전체"]
            
            selected_group = st.selectbox(
                "그룹 선택",
                groups,
                key="org_group_select"
            )
            
            # 파트 선택
            if selected_group != "전체" and selected_team != "전체" and selected_bu != "전체" and selected_center != "전체":
                filtered_data = org_data[
                    (org_data['센터'] == selected_center) & 
                    (org_data['BU'] == selected_bu) &
                    (org_data['팀'] == selected_team) &
                    (org_data['그룹'] == selected_group)
                ]
                parts = ["전체"] + sorted(filtered_data['파트'].dropna().unique().tolist())
            else:
                parts = ["전체"]
            
            selected_part = st.selectbox(
                "파트 선택",
                parts,
                key="org_part_select"
            )
            
            # 직원 목록 가져오기
            employees = self.get_employees_by_organization(
                center=selected_center if selected_center != "전체" else None,
                bu=selected_bu if selected_bu != "전체" else None,
                team=selected_team if selected_team != "전체" else None,
                group=selected_group if selected_group != "전체" else None,
                part=selected_part if selected_part != "전체" else None
            )
            
            # 직원 선택
            if employees:
                employee_options = [emp['display'] for emp in employees]
                selected_employee_display = st.selectbox(
                    f"직원 선택 ({len(employees)}명)",
                    employee_options,
                    key="org_employee_select"
                )
                
                # 선택된 직원의 ID 반환
                for emp in employees:
                    if emp['display'] == selected_employee_display:
                        return emp['id']
            else:
                st.info("선택한 조직에 직원이 없습니다.")
                return None
                
        except Exception as e:
            self.logger.error(f"조직 기반 선택 오류: {e}")
            st.error(f"조직 선택 중 오류 발생: {e}")
            return None
    
    def get_available_date_range(self):
        """로드된 데이터에서 사용 가능한 날짜 범위 가져오기"""
        try:
            from ...database import get_pickle_manager
            pickle_manager = get_pickle_manager()
            
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
            from ...database import get_pickle_manager
            pickle_manager = get_pickle_manager()
            
            # Claim 데이터 로드
            claim_data = pickle_manager.load_dataframe(name='claim_data')
            if claim_data is None:
                self.logger.warning("Claim 데이터가 없습니다")
                return None
                
            # 컬럼명 확인 (디버깅용)
            self.logger.info(f"Claim 데이터 컬럼: {claim_data.columns.tolist()}")
            
            # 날짜 형식 변환
            # claim_data의 근무일이 Timestamp인 경우 처리
            if not claim_data.empty and pd.api.types.is_datetime64_any_dtype(claim_data['근무일']):
                # Timestamp를 date로 변환
                claim_data['근무일_date'] = pd.to_datetime(claim_data['근무일']).dt.date
                # 해당 직원과 날짜의 데이터 필터링
                daily_claim = claim_data[
                    (claim_data['사번'] == int(employee_id)) & 
                    (claim_data['근무일_date'] == selected_date)
                ]
            else:
                # 기존 방식 (정수형)
                date_str = selected_date.strftime('%Y%m%d')
                date_int = int(date_str)
                daily_claim = claim_data[
                    (claim_data['사번'] == employee_id) & 
                    (claim_data['근무일'] == date_int)
                ]
            
            if daily_claim.empty:
                return None
            
            # 필요한 정보 추출
            claim_info = {
                'exists': True,
                'claim_start': daily_claim.iloc[0].get('시작', daily_claim.iloc[0].get('출근시간', 'N/A')),
                'claim_end': daily_claim.iloc[0].get('종료', daily_claim.iloc[0].get('퇴근시간', 'N/A')),
                'claim_hours': daily_claim.iloc[0].get('근무시간', daily_claim.iloc[0].get('근로시간', 8)),
                'claim_type': daily_claim.iloc[0].get('WORKSCHDTYPNM', daily_claim.iloc[0].get('근무유형', '선택근무제')),
                'overtime': daily_claim.iloc[0].get('초과근무', daily_claim.iloc[0].get('연장근무', 0)),
                'raw_claim': daily_claim.iloc[0].to_dict()
            }
            
            # 근무시간이 문자열인 경우 숫자로 변환
            if isinstance(claim_info['claim_hours'], str):
                try:
                    # "8:00" 형태인 경우
                    if ':' in str(claim_info['claim_hours']):
                        hours, minutes = claim_info['claim_hours'].split(':')
                        claim_info['claim_hours'] = float(hours) + float(minutes) / 60
                    else:
                        claim_info['claim_hours'] = float(claim_info['claim_hours'])
                except:
                    claim_info['claim_hours'] = 8.0
            
            return claim_info
            
        except Exception as e:
            self.logger.warning(f"Claim 데이터 로드 실패: {e}")
            return None
    
    def get_tag_location_master(self):
        """태깅지점 마스터 데이터 가져오기 (DB에서 직접 로드)"""
        try:
            from sqlalchemy import text
            
            # 데이터베이스에서 직접 로드
            query = """
            SELECT 
                "정렬No",
                "위치",
                COALESCE("DR_NO", "기기번호") as DR_NO,
                "게이트명" as DR_NM,
                "표기명",
                "입출구분" as INOUT_GB,
                "공간구분_code",
                "세부유형_code",
                "Tag_Code",
                "공간구분_NM",
                "세부유형_NM",
                "라벨링_활동"
            FROM tag_location_master
            ORDER BY "정렬No"
            """
            
            with self.db_manager.engine.connect() as conn:
                tag_location_master = pd.read_sql(text(query), conn)
                
            if tag_location_master is not None and not tag_location_master.empty:
                self.logger.info(f"태깅지점 마스터 데이터 로드 성공: {len(tag_location_master)}건")
                self.logger.info(f"마스터 데이터 컬럼: {tag_location_master.columns.tolist()}")
                
                # 디버깅: 정문 관련 태그 확인
                gate_tags = tag_location_master[tag_location_master['DR_NM'].str.contains('정문|SPEED GATE', case=False, na=False)]
                if not gate_tags.empty:
                    self.logger.info(f"정문 관련 태그 마스터 데이터:")
                    for idx, row in gate_tags.head(10).iterrows():
                        self.logger.info(f"  - DR_NO={row['DR_NO']}, DR_NM={row['DR_NM']}, 입출구분={row.get('INOUT_GB', 'N/A')}, Tag_Code={row.get('Tag_Code', 'N/A')}")
                
                # Tag_Code 값 확인
                if 'Tag_Code' in tag_location_master.columns:
                    unique_codes = tag_location_master['Tag_Code'].unique()
                    self.logger.info(f"전체 Tag_Code 종류: {unique_codes}")
                
                # DR_NO 컬럼 타입 확인 및 문자열 변환
                tag_location_master['DR_NO'] = tag_location_master['DR_NO'].astype(str).str.strip()
                
                return tag_location_master
            else:
                self.logger.warning("태깅지점 마스터 데이터가 없습니다.")
                return None
                
        except Exception as e:
            self.logger.warning(f"태깅지점 마스터 데이터 로드 실패: {e}")
            return None
    
    def get_employee_work_type(self, employee_id: str, selected_date: date):
        """직원의 근무제 유형 확인"""
        try:
            from ...database import get_pickle_manager
            pickle_manager = get_pickle_manager()
            
            # Claim 데이터에서 근무제 유형 확인
            claim_data = pickle_manager.load_dataframe(name='claim_data')
            if claim_data is not None and '사번' in claim_data.columns:
                # 사번 형식 맞추기
                if ' - ' in str(employee_id):
                    employee_id = employee_id.split(' - ')[0].strip()
                
                # 날짜 형식 맞추기 - 근무일이 datetime 타입인 경우와 int 타입인 경우 모두 처리
                date_int = int(selected_date.strftime('%Y%m%d'))
                date_datetime = pd.to_datetime(selected_date)
                
                # 디버깅: Claim 데이터 정보
                self.logger.info(f"Claim 데이터 조회 - 사번: {employee_id}, 날짜: {selected_date}")
                self.logger.info(f"Claim 데이터 행 수: {len(claim_data)}")
                self.logger.info(f"근무일 컬럼 타입: {claim_data['근무일'].dtype}")
                
                # 사번을 숫자로 변환
                try:
                    emp_id_int = int(employee_id)
                    
                    # 근무일 컬럼 타입에 따라 다르게 처리
                    if pd.api.types.is_datetime64_any_dtype(claim_data['근무일']):
                        emp_claim = claim_data[
                            (claim_data['사번'] == emp_id_int) & 
                            (claim_data['근무일'] == date_datetime)
                        ]
                        self.logger.info(f"datetime 타입으로 조회 결과: {len(emp_claim)}건")
                    else:
                        emp_claim = claim_data[
                            (claim_data['사번'] == emp_id_int) & 
                            (claim_data['근무일'] == date_int)
                        ]
                        self.logger.info(f"int 타입으로 조회 결과: {len(emp_claim)}건")
                except:
                    emp_claim = claim_data[
                        (claim_data['사번'] == employee_id) & 
                        (claim_data['근무일'] == date_int)
                    ]
                    self.logger.info(f"문자 사번으로 조회 결과: {len(emp_claim)}건")
                
                if not emp_claim.empty and 'WORKSCHDTYPNM' in emp_claim.columns:
                    work_type = emp_claim.iloc[0]['WORKSCHDTYPNM']
                    self.logger.info(f"Claim 데이터에서 근무제 확인: {work_type}")
                    
                    # 디버깅: 정확한 값 확인
                    self.logger.info(f"근무제 원본 값: '{work_type}', 타입: {type(work_type)}")
                    self.logger.info(f"근무제 값 길이: {len(str(work_type))}")
                    self.logger.info(f"근무제 값 repr: {repr(work_type)}")
                    
                    # 선택적근로시간제, 선택근무제 등 다양한 표현 처리
                    if '선택' in str(work_type) or '선택적' in str(work_type):
                        self.logger.info(f"선택근무제로 분류: {work_type}")
                        return 'selective'
                    elif '탄력' in str(work_type):
                        self.logger.info(f"탄력근무제로 분류: {work_type}")
                        return 'flexible'
                    elif '야간' in str(work_type) or '2교대' in str(work_type) or '교대' in str(work_type):
                        self.logger.info(f"야간/교대근무제로 분류: {work_type}")
                        return 'night_shift'
                    else:
                        # Claim 데이터가 있지만 키워드가 없는 경우 기본값으로 처리
                        self.logger.info(f"근무제 키워드 매칭 실패, 일반 근무로 분류: {work_type}")
                        return 'standard'
            
            # Claim 데이터가 없는 경우 기본값 사용
            self.logger.info("Claim 데이터에서 근무제를 찾을 수 없음 - 기본값(standard) 사용")
            return 'standard'  # 기본값
            
        except Exception as e:
            self.logger.warning(f"근무제 유형 확인 실패: {e}")
            return 'standard'
    
    def get_meal_data(self, employee_id: str, selected_date: date):
        """특정 직원의 특정 날짜 식사 데이터 가져오기"""
        try:
            from ...database import get_pickle_manager
            pickle_manager = get_pickle_manager()
            
            # 식사 데이터 로드
            meal_data = pickle_manager.load_dataframe(name='meal_data')
            if meal_data is None:
                self.logger.info("식사 데이터가 없습니다.")
                return None
            
            # 근무 유형 확인
            work_type = self.get_employee_work_type(employee_id, selected_date)
            self.logger.info(f"직원 {employee_id}의 근무 유형: {work_type}")
            
            self.logger.info(f"식사 데이터 로드 완료: {len(meal_data)}행")
            self.logger.info(f"식사 데이터 컬럼: {list(meal_data.columns[:10])}")
            
            # 날짜 필터링
            # meal_data의 컬럼명 확인 (취식일시 or meal_datetime)
            date_column = None
            if '취식일시' in meal_data.columns:
                date_column = '취식일시'
            elif 'meal_datetime' in meal_data.columns:
                date_column = 'meal_datetime'
            else:
                self.logger.warning(f"날짜 컬럼을 찾을 수 없습니다. 사용 가능한 컬럼: {list(meal_data.columns)}")
                return None
            
            # 날짜 컬럼을 datetime으로 변환
            if not pd.api.types.is_datetime64_any_dtype(meal_data[date_column]):
                meal_data[date_column] = pd.to_datetime(meal_data[date_column])
            
            # 사번 컬럼 찾기
            emp_id_column = None
            if '사번' in meal_data.columns:
                emp_id_column = '사번'
            elif 'employee_id' in meal_data.columns:
                emp_id_column = 'employee_id'
            else:
                self.logger.warning(f"사번 컬럼을 찾을 수 없습니다. 사용 가능한 컬럼: {list(meal_data.columns)}")
                return None
            
            # 사번 형식 맞추기 - "사번 - 이름" 형식 처리
            if ' - ' in str(employee_id):
                # "사번 - 이름" 형식에서 사번만 추출
                employee_id = employee_id.split(' - ')[0].strip()
            
            # 사번 데이터 타입 확인 및 변환
            self.logger.info(f"검색할 사번: {employee_id}, 날짜: {selected_date}")
            
            try:
                # 숫자로 변환 시도
                emp_id_int = int(employee_id)
                
                # meal_data의 사번도 숫자로 변환
                meal_data[emp_id_column] = pd.to_numeric(meal_data[emp_id_column], errors='coerce')
                
                # 야간/교대 근무자는 전날 데이터도 포함해야 함 (선택근무제는 제외)
                if work_type == 'night_shift':
                    # 야간/교대 근무자는 전날과 당일 데이터 모두 가져오기
                    prev_date = selected_date - timedelta(days=1)
                    self.logger.info(f"야간 근무자 식사 데이터 조회: {prev_date} ~ {selected_date}")
                    
                    daily_meals = meal_data[
                        (meal_data[emp_id_column] == emp_id_int) & 
                        ((meal_data[date_column].dt.date == selected_date) | 
                         (meal_data[date_column].dt.date == prev_date))
                    ].copy()
                    
                    # 디버깅: 각 날짜별 식사 건수 확인
                    prev_meals = meal_data[(meal_data[emp_id_column] == emp_id_int) & (meal_data[date_column].dt.date == prev_date)]
                    curr_meals = meal_data[(meal_data[emp_id_column] == emp_id_int) & (meal_data[date_column].dt.date == selected_date)]
                    self.logger.info(f"전날({prev_date}) 식사: {len(prev_meals)}건, 당일({selected_date}) 식사: {len(curr_meals)}건")
                else:
                    # 일반 근무자는 당일 데이터만
                    daily_meals = meal_data[
                        (meal_data[emp_id_column] == emp_id_int) & 
                        (meal_data[date_column].dt.date == selected_date)
                    ].copy()
                
                self.logger.info(f"숫자 비교 결과: {len(daily_meals)}건의 식사 데이터 찾음 (근무유형: {work_type})")
                
                # 디버깅: 날짜 필터링 전 데이터 확인
                if work_type == 'night_shift':
                    self.logger.info(f"필터링 전 전날({prev_date}) 식사: {len(prev_meals)}건, 당일({selected_date}) 식사: {len(curr_meals)}건")
                
            except ValueError:
                # 문자열로 비교
                meal_data[emp_id_column] = meal_data[emp_id_column].astype(str)
                
                if work_type == 'night_shift':
                    # 야간/교대 근무자는 전날과 당일 데이터 모두 가져오기
                    prev_date = selected_date - timedelta(days=1)
                    daily_meals = meal_data[
                        (meal_data[emp_id_column] == str(employee_id)) & 
                        ((meal_data[date_column].dt.date == selected_date) | 
                         (meal_data[date_column].dt.date == prev_date))
                    ].copy()
                else:
                    # 일반 근무자는 당일 데이터만
                    daily_meals = meal_data[
                        (meal_data[emp_id_column] == str(employee_id)) & 
                        (meal_data[date_column].dt.date == selected_date)
                    ].copy()
                
                self.logger.info(f"문자열 비교 결과: {len(daily_meals)}건의 식사 데이터 찾음 (근무유형: {work_type})")
            
            # 야간/교대 근무자의 경우 시간대 필터링  
            if work_type == 'night_shift' and not daily_meals.empty:
                # 전날 저녁 17시 ~ 당일 오전 12시까지로 필터링
                start_time = datetime.combine(selected_date - timedelta(days=1), time(17, 0))
                end_time = datetime.combine(selected_date, time(12, 0))
                
                # 식사 시간 필터링
                daily_meals = daily_meals[
                    (pd.to_datetime(daily_meals[date_column]) >= start_time) & 
                    (pd.to_datetime(daily_meals[date_column]) < end_time)
                ]
                self.logger.info(f"야간 근무자 식사 데이터 필터링: {start_time} ~ {end_time}, {len(daily_meals)}건")
                
                # 필터링 전후 비교를 위해 로깅
                before_count = len(meal_data[
                    (meal_data[emp_id_column] == emp_id_int if 'emp_id_int' in locals() else meal_data[emp_id_column] == str(employee_id))
                ])
                self.logger.info(f"전체 식사 데이터 중 해당 사번: {before_count}건")
            
            if not daily_meals.empty:
                self.logger.info(f"직원 {employee_id}의 {selected_date} 식사 데이터: {len(daily_meals)}건")
                # 찾은 식사 데이터 내용 로깅
                for idx, row in daily_meals.iterrows():
                    meal_time = row.get(date_column, '')
                    meal_type = row.get('식사대분류', row.get('meal_category', ''))
                    # 배식구 정보를 우선적으로 사용
                    service_point = row.get('배식구', row.get('service_point', ''))
                    restaurant = row.get('식당명', row.get('restaurant_name', ''))
                    # 배식구가 있으면 배식구를, 없으면 식당명을 표시
                    location_info = service_point if service_point else restaurant
                    self.logger.info(f"  - {meal_time}: {meal_type} @ {location_info}")
                    # 테이크아웃 여부도 로깅
                    if '테이크아웃' in row:
                        self.logger.info(f"    테이크아웃 여부: {row['테이크아웃']}")
            
            return daily_meals
            
        except Exception as e:
            self.logger.error(f"식사 데이터 로드 중 오류 발생: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None
    
    def get_daily_tag_data(self, employee_id: str, selected_date: date):
        """특정 직원의 특정 날짜 태깅 데이터 가져오기 (Knox/Equipment 데이터 포함)"""
        try:
            from ...database import get_pickle_manager
            from ...data.integrated_data_processor import IntegratedDataProcessor
            pickle_manager = get_pickle_manager()
            
            # 태깅 데이터 로드
            tag_data = pickle_manager.load_dataframe(name='tag_data')
            if tag_data is None:
                return None
            
            # 근무제 유형 확인
            work_type = self.get_employee_work_type(employee_id, selected_date)
            
            # 날짜 형식 변환 (YYYYMMDD)
            date_str = selected_date.strftime('%Y%m%d')
            date_int = int(date_str)
            
            # 사번 형식 확인 및 변환
            try:
                emp_id_int = int(employee_id)
                
                # 야간/교대 근무의 경우 야간 근무 고려 (선택근무제는 제외)
                if work_type == 'night_shift':
                    # 야간 근무자는 전날 저녁 ~ 당일 아침이 한 근무일
                    # 따라서 '선택 날짜'는 퇴근하는 날짜를 의미
                    prev_date = selected_date - timedelta(days=1)
                    prev_date_int = int(prev_date.strftime('%Y%m%d'))
                    
                    # 야간 근무자는 전날 저녁부터 당일 아침까지만 필요
                    # 전날 데이터 (17시 이후)와 당일 데이터 (12시 이전)만 로드
                    prev_data = tag_data[
                        (tag_data['사번'] == emp_id_int) & 
                        (tag_data['ENTE_DT'] == prev_date_int)
                    ].copy()
                    
                    current_data = tag_data[
                        (tag_data['사번'] == emp_id_int) & 
                        (tag_data['ENTE_DT'] == date_int)
                    ].copy()
                    
                    # 시간 필터링을 여기서 미리 수행
                    if not prev_data.empty:
                        prev_data['hour'] = prev_data['출입시각'].astype(str).str.zfill(6).str[:2].astype(int)
                        prev_data = prev_data[prev_data['hour'] >= 17]  # 17시 이후만
                    
                    if not current_data.empty:
                        current_data['hour'] = current_data['출입시각'].astype(str).str.zfill(6).str[:2].astype(int)
                        current_data = current_data[current_data['hour'] < 12]  # 12시 이전만
                    
                    # 두 데이터 결합
                    if not prev_data.empty and not current_data.empty:
                        daily_data = pd.concat([prev_data, current_data], ignore_index=True)
                    elif not prev_data.empty:
                        daily_data = prev_data
                    elif not current_data.empty:
                        daily_data = current_data
                    else:
                        daily_data = pd.DataFrame()
                    
                    self.logger.info(f"야간 근무자 데이터 로드: 전날 저녁({len(prev_data)}건) + 당일 오전({len(current_data)}건) = {len(daily_data)}건")
                else:
                    # 일반 근무제는 당일 데이터만
                    daily_data = tag_data[
                        (tag_data['사번'] == emp_id_int) & 
                        (tag_data['ENTE_DT'] == date_int)
                    ].copy()
                    
            except ValueError:
                # 숫자 변환 실패 시 문자열로 비교
                tag_data['사번'] = tag_data['사번'].astype(str)
                daily_data = tag_data[
                    (tag_data['사번'] == str(employee_id)) & 
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
            
            # 야간/교대 근무의 경우 야간 근무 시간대 필터링 (선택근무제는 제외)
            if work_type == 'night_shift':
                # 야간 근무는 전날 저녁 ~ 당일 아침 (하나의 근무 사이클)
                # 선택한 날짜 = 퇴근하는 날짜 기준
                
                # 전날 저녁 17시 ~ 당일 오전 12시까지로 필터링
                start_time = datetime.combine(selected_date - timedelta(days=1), time(17, 0))
                end_time = datetime.combine(selected_date, time(12, 0))
                
                # 야간 근무 시간대 필터링
                daily_data = daily_data[
                    (daily_data['datetime'] >= start_time) & 
                    (daily_data['datetime'] < end_time)
                ]
                
                self.logger.info(f"야간 근무 시간대 필터링: {start_time} ~ {end_time}, {len(daily_data)}건")
                
                # 실제 출근 시간 확인
                if not daily_data.empty:
                    first_tag = daily_data.iloc[0]['datetime']
                    last_tag = daily_data.iloc[-1]['datetime']
                    self.logger.info(f"실제 근무: {first_tag.strftime('%m/%d %H:%M')} ~ {last_tag.strftime('%m/%d %H:%M')}")
                
                # 정문 태그 확인
                gate_tags = daily_data[daily_data['DR_NM'].str.contains('정문|GATE', case=False, na=False)]
                if not gate_tags.empty:
                    self.logger.info(f"정문 태그 {len(gate_tags)}건 포함됨:")
                    for _, tag in gate_tags.iterrows():
                        self.logger.info(f"  - {tag['datetime']}: {tag['DR_NM']}")
                else:
                    self.logger.warning("정문 태그가 필터링 후 없음")
            
            # Knox 및 Equipment 데이터를 태그 형식으로 추가
            knox_equipment_tags = self._get_knox_and_equipment_tags(employee_id, selected_date, work_type)
            if knox_equipment_tags is not None and not knox_equipment_tags.empty:
                self.logger.info(f"Knox/Equipment 데이터 {len(knox_equipment_tags)}건을 추가")
                
                # 태그별 상세 정보 로깅
                for _, tag in knox_equipment_tags.iterrows():
                    self.logger.info(f"  - {tag['datetime']}: {tag['DR_NM']} ({tag['Tag_Code']})")
                
                # 야간 근무자의 경우 시간대 필터링
                if work_type == 'night_shift':
                    start_time = datetime.combine(selected_date - timedelta(days=1), time(17, 0))
                    end_time = datetime.combine(selected_date, time(12, 0))
                    
                    self.logger.info(f"야간 근무자 필터링 적용: {start_time} ~ {end_time}")
                    knox_equipment_tags_before = len(knox_equipment_tags)
                    
                    knox_equipment_tags = knox_equipment_tags[
                        (knox_equipment_tags['datetime'] >= start_time) & 
                        (knox_equipment_tags['datetime'] < end_time)
                    ]
                    self.logger.info(f"야간 근무 시간대 필터링 후: {len(knox_equipment_tags)}건 (필터링 전: {knox_equipment_tags_before}건)")
                else:
                    self.logger.info(f"주간 근무자(work_type: {work_type}) - 시간대 필터링 미적용")
                
                # 기존 데이터와 병합
                if not knox_equipment_tags.empty:
                    daily_data = pd.concat([daily_data, knox_equipment_tags], ignore_index=True)
                    daily_data = daily_data.sort_values('datetime').reset_index(drop=True)
                    self.logger.info(f"병합 후 총 {len(daily_data)}건의 태그")
            
            return daily_data
            
        except Exception as e:
            self.logger.error(f"일일 태그 데이터 로드 실패: {e}")
            return None
    
    def _get_knox_and_equipment_tags(self, employee_id: str, selected_date: date, work_type: str) -> pd.DataFrame:
        """Knox 및 Equipment 데이터를 태그 형식으로 변환하여 반환"""
        try:
            from ...database import get_pickle_manager
            pickle_manager = get_pickle_manager()
            
            all_tags = []
            emp_id_str = str(employee_id)
            self.logger.info(f"_get_knox_and_equipment_tags 호출 - 사번: {emp_id_str}, 날짜: {selected_date}, 근무유형: {work_type}")
            
            # 1. Knox Approval 데이터
            knox_approval = pickle_manager.load_dataframe(name='knox_approval_data')
            if knox_approval is not None:
                # 사번 컬럼 확인 및 변환
                if 'UserNo' in knox_approval.columns:
                    knox_approval['employee_id'] = knox_approval['UserNo'].astype(str)
                elif '사번' in knox_approval.columns:
                    knox_approval['employee_id'] = knox_approval['사번'].astype(str)
                
                # 해당 직원의 데이터 필터링
                if 'employee_id' in knox_approval.columns:
                    emp_data = knox_approval[knox_approval['employee_id'] == emp_id_str]
                    if not emp_data.empty:
                        for _, row in emp_data.iterrows():
                            timestamp = pd.to_datetime(row.get('Timestamp', row.get('timestamp')))
                            if timestamp.date() == selected_date:
                                tag = {
                                    'ENTE_DT': int(timestamp.strftime('%Y%m%d')),
                                    '출입시각': int(timestamp.strftime('%H%M%S')),
                                    '사번': int(employee_id),
                                    'DR_NO': 'O_KNOX_APPROVAL',
                                    'DR_NM': 'Knox 결재 시스템',
                                    'INOUT_GB': 'O',
                                    'datetime': timestamp,
                                    'time': timestamp.strftime('%H%M%S'),
                                    'Tag_Code': 'O',
                                    'source': 'knox_approval'
                                }
                                all_tags.append(tag)
            
            # 2. Knox PIMS 데이터 (G3 태그)
            knox_pims = pickle_manager.load_dataframe(name='knox_pims_data')
            if knox_pims is not None:
                self.logger.info(f"Knox PIMS 데이터 로드됨: {len(knox_pims)}건")
                self.logger.info(f"Knox PIMS 컬럼: {list(knox_pims.columns)}")
                
                # 사번 컬럼 변환
                if '사번' in knox_pims.columns:
                    knox_pims['employee_id'] = knox_pims['사번'].astype(str)
                    self.logger.info(f"사번 컬럼 변환 완료")
                else:
                    self.logger.warning(f"Knox PIMS에 '사번' 컬럼이 없습니다. 컬럼: {list(knox_pims.columns)}")
                
                # 해당 직원의 데이터 필터링
                if 'employee_id' in knox_pims.columns:
                    emp_data = knox_pims[knox_pims['employee_id'] == emp_id_str]
                    self.logger.info(f"Knox PIMS - {emp_id_str} 사번 데이터: {len(emp_data)}건")
                    
                    # 20220245 사번 데이터 상세 확인
                    if emp_id_str == '20220245' and not emp_data.empty:
                        self.logger.info(f"20220245 사번의 전체 Knox PIMS 데이터:")
                        for idx, row in emp_data.iterrows():
                            start_time_str = row.get('시작일시_GMT+9', row.get('start_time', ''))
                            self.logger.info(f"  - 일정ID: {row.get('일정ID', '')}, 시작: {start_time_str}")
                    
                    if not emp_data.empty:
                        matched_count = 0
                        for _, row in emp_data.iterrows():
                            # 시작 시간 처리
                            start_time_str = row.get('시작일시_GMT+9', row.get('start_time'))
                            if pd.isna(start_time_str):
                                self.logger.warning(f"시작 시간이 없음: 일정ID {row.get('일정ID', '')}")
                                continue
                                
                            start_time = pd.to_datetime(start_time_str)
                            end_time_str = row.get('종료일시_GMT+9', row.get('end_time'))
                            end_time = pd.to_datetime(end_time_str) if pd.notna(end_time_str) else None
                            
                            self.logger.debug(f"Knox PIMS 시간 확인 - 일정ID: {row.get('일정ID', '')}, 시작시간: {start_time}, 종료시간: {end_time}, 선택날짜: {selected_date}")
                            
                            if start_time.date() == selected_date:
                                matched_count += 1
                                self.logger.info(f"Knox PIMS 매칭 - 시간: {start_time} ~ {end_time}, 일정ID: {row.get('일정ID', '')}, 일정구분: {row.get('일정_구분', '')}")
                                
                                # 회의 시간 계산 (분 단위)
                                meeting_duration = None
                                if end_time:
                                    meeting_duration = (end_time - start_time).total_seconds() / 60
                                    self.logger.info(f"Knox PIMS 회의 duration 계산: {start_time} ~ {end_time} = {meeting_duration:.1f}분")
                                
                                tag = {
                                    'ENTE_DT': int(start_time.strftime('%Y%m%d')),
                                    '출입시각': int(start_time.strftime('%H%M%S')),
                                    '사번': int(employee_id),
                                    'DR_NO': 'G3_KNOX_PIMS',
                                    'DR_NM': 'Knox PIMS 회의',
                                    'INOUT_GB': 'G3',
                                    'datetime': start_time,
                                    'time': start_time.strftime('%H%M%S'),
                                    'Tag_Code': 'G3',
                                    'source': 'knox_pims',
                                    'meeting_id': row.get('일정ID', row.get('meeting_id', '')),
                                    'knox_end_time': end_time,  # Knox PIMS 종료시간 저장
                                    'knox_duration': meeting_duration  # Knox PIMS 회의 시간(분) 저장
                                }
                                self.logger.info(f"Knox PIMS 태그 생성: {tag}")
                                all_tags.append(tag)
                        self.logger.info(f"Knox PIMS - {selected_date} 날짜로 매칭된 데이터: {matched_count}건")
            
            # 3. Knox Mail 데이터
            knox_mail = pickle_manager.load_dataframe(name='knox_mail_data')
            if knox_mail is not None:
                # 사번 컬럼 변환
                if '발신인사번_text' in knox_mail.columns:
                    knox_mail['employee_id'] = knox_mail['발신인사번_text'].astype(str)
                
                # 해당 직원의 데이터 필터링
                if 'employee_id' in knox_mail.columns:
                    emp_data = knox_mail[knox_mail['employee_id'] == emp_id_str]
                    if not emp_data.empty:
                        for _, row in emp_data.iterrows():
                            timestamp = pd.to_datetime(row.get('발신일시_GMT9', row.get('timestamp')))
                            if timestamp.date() == selected_date:
                                tag = {
                                    'ENTE_DT': int(timestamp.strftime('%Y%m%d')),
                                    '출입시각': int(timestamp.strftime('%H%M%S')),
                                    '사번': int(employee_id),
                                    'DR_NO': 'O_KNOX_MAIL',
                                    'DR_NM': 'Knox 메일 시스템',
                                    'INOUT_GB': 'O',
                                    'datetime': timestamp,
                                    'time': timestamp.strftime('%H%M%S'),
                                    'Tag_Code': 'O',
                                    'source': 'knox_mail'
                                }
                                all_tags.append(tag)
            
            # 4. Equipment 데이터 (EAM, LAMS, MES)
            equipment_data = self.get_employee_equipment_data(employee_id, selected_date)
            if equipment_data is not None and not equipment_data.empty:
                for _, equip in equipment_data.iterrows():
                    timestamp = pd.to_datetime(equip['timestamp'])
                    tag = {
                        'ENTE_DT': int(timestamp.strftime('%Y%m%d')),
                        '출입시각': int(timestamp.strftime('%H%M%S')),
                        '사번': int(employee_id),
                        'DR_NO': f"O_{equip.get('system_type', 'EQUIP')}",
                        'DR_NM': f"{equip.get('system_type', 'Equipment')} 사용",
                        'INOUT_GB': 'O',
                        'datetime': timestamp,
                        'time': timestamp.strftime('%H%M%S'),
                        'Tag_Code': 'O',
                        'source': f"equipment_{equip.get('system_type', '').lower()}"
                    }
                    all_tags.append(tag)
            
            # DataFrame으로 변환
            if all_tags:
                tags_df = pd.DataFrame(all_tags)
                self.logger.info(f"Knox/Equipment 태그 생성: 총 {len(tags_df)}건")
                
                # 태그 종류별 통계
                if 'Tag_Code' in tags_df.columns:
                    tag_stats = tags_df.groupby('Tag_Code').size()
                    for Tag_Code, count in tag_stats.items():
                        self.logger.info(f"  - {Tag_Code} 태그: {count}건")
                
                # G3 태그 상세 확인
                g3_tags = tags_df[tags_df['Tag_Code'] == 'G3']
                if not g3_tags.empty:
                    self.logger.info(f"G3 태그 {len(g3_tags)}건 상세:")
                    for _, tag in g3_tags.iterrows():
                        self.logger.info(f"  - {tag['datetime']}: {tag['DR_NM']} (meeting_id: {tag.get('meeting_id', 'N/A')})")
                else:
                    self.logger.info("G3 태그가 없음")
                
                return tags_df
            else:
                self.logger.info("Knox/Equipment 태그가 전혀 없음")
                return pd.DataFrame()
                
        except Exception as e:
            self.logger.error(f"Knox/Equipment 태그 생성 실패: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return pd.DataFrame()
    
    def get_employee_attendance_data(self, employee_id: str, selected_date) -> pd.DataFrame:
        """직원의 근태 정보 조회"""
        try:
            # 날짜를 datetime으로 변환하고 문자열로 포맷
            date_obj = pd.to_datetime(selected_date)
            date_str = date_obj.strftime('%Y-%m-%d')
            
            # 근태 데이터 조회 쿼리
            query = """
                SELECT * FROM attendance_data 
                WHERE employee_id = :emp_id
                AND :target_date BETWEEN start_date AND end_date
            """
            
            result = self.db_manager.execute_query(
                query, 
                {'emp_id': employee_id, 'target_date': date_str}
            )
            
            if result:
                df = pd.DataFrame(result)
                # 날짜 컬럼 datetime으로 변환
                date_columns = ['start_date', 'end_date', 'created_date']
                for col in date_columns:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col])
                
                self.logger.info(f"직원 {employee_id}의 근태 데이터 {len(df)}건 조회")
                return df
            
            return pd.DataFrame()
            
        except Exception as e:
            self.logger.error(f"근태 데이터 조회 실패: {e}")
            return pd.DataFrame()
    
    def get_employee_equipment_data_from_db(self, employee_id: str, selected_date: date):
        """DB에서 직원의 장비 사용 데이터 조회"""
        try:
            # 근무 유형 확인
            work_type = self.get_employee_work_type(employee_id, selected_date)
            
            if work_type == 'night_shift':
                # 야간/교대 근무자는 전날 17:00부터 당일 12:00까지
                start_date = selected_date - timedelta(days=1)
                end_date = selected_date
                
                query = f"""
                SELECT * FROM equipment_logs 
                WHERE employee_id = '{employee_id}' 
                AND datetime >= '{start_date} 17:00:00'
                AND datetime < '{end_date} 12:00:00'
                """
            else:
                # 일반 근무자는 당일 데이터만
                query = f"""
                SELECT * FROM equipment_logs 
                WHERE employee_id = '{employee_id}' 
                AND DATE(datetime) = '{selected_date}'
                """
            
            # DB 쿼리 실행
            result = self.db_manager.execute_query(text(query))
            
            if result and len(result) > 0:
                # DataFrame으로 변환
                equipment_data = pd.DataFrame(result)
                equipment_data['timestamp'] = pd.to_datetime(equipment_data['datetime'])
                return equipment_data
            
            return None
            
        except Exception as e:
            self.logger.warning(f"DB에서 장비 데이터 조회 실패: {e}")
            return None
    
    def get_employee_equipment_data(self, employee_id: str, selected_date: date):
        """직원의 일일 장비 사용 데이터 가져오기"""
        try:
            # 먼저 DB에서 조회 시도
            equipment_data = self.get_employee_equipment_data_from_db(employee_id, selected_date)
            if equipment_data is not None:
                return equipment_data
                
            # DB에 데이터가 없으면 pickle 파일에서 로드
            from ...database import get_pickle_manager
            pickle_manager = get_pickle_manager()
            
            # 사번 형식 맞추기
            if ' - ' in str(employee_id):
                employee_id = employee_id.split(' - ')[0].strip()
            
            # 근무 유형 확인
            work_type = self.get_employee_work_type(employee_id, selected_date)
            
            equipment_data_list = []
            
            # LAMS 데이터 로드
            lams_data = pickle_manager.load_dataframe(name='lams_data')
            if lams_data is not None and not lams_data.empty:
                try:
                    # 사번을 숫자로 변환
                    emp_id_int = int(employee_id)
                    lams_data['employee_id'] = pd.to_numeric(lams_data['employee_id'], errors='coerce')
                    
                    # 날짜 필터링
                    daily_lams = lams_data[
                        (lams_data['employee_id'] == emp_id_int) & 
                        (pd.to_datetime(lams_data['timestamp']).dt.date == selected_date)
                    ].copy()
                    
                    if not daily_lams.empty:
                        daily_lams['system'] = 'LAMS(품질시스템)'
                        equipment_data_list.append(daily_lams)
                        self.logger.info(f"LAMS 데이터 {len(daily_lams)}건 로드")
                        
                except Exception as e:
                    self.logger.debug(f"LAMS 데이터 로드 실패: {e}")
            
            # MES 데이터 로드
            mes_data = pickle_manager.load_dataframe(name='mes_data')
            if mes_data is not None and not mes_data.empty:
                try:
                    # 사번을 숫자로 변환
                    emp_id_int = int(employee_id)
                    mes_data['employee_id'] = pd.to_numeric(mes_data['employee_id'], errors='coerce')
                    
                    # 날짜 필터링
                    daily_mes = mes_data[
                        (mes_data['employee_id'] == emp_id_int) & 
                        (pd.to_datetime(mes_data['timestamp']).dt.date == selected_date)
                    ].copy()
                    
                    if not daily_mes.empty:
                        daily_mes['system'] = 'MES(생산시스템)'
                        equipment_data_list.append(daily_mes)
                        self.logger.info(f"MES 데이터 {len(daily_mes)}건 로드")
                        
                except Exception as e:
                    self.logger.debug(f"MES 데이터 로드 실패: {e}")
            
            # EAM 데이터 로드
            eam_data = pickle_manager.load_dataframe(name='eam_data')
            if eam_data is not None and not eam_data.empty:
                try:
                    # 사번을 숫자로 변환
                    emp_id_int = int(employee_id)
                    eam_data['employee_id'] = pd.to_numeric(eam_data['employee_id'], errors='coerce')
                    
                    # 날짜 필터링
                    daily_eam = eam_data[
                        (eam_data['employee_id'] == emp_id_int) & 
                        (pd.to_datetime(eam_data['timestamp']).dt.date == selected_date)
                    ].copy()
                    
                    if not daily_eam.empty:
                        daily_eam['system'] = 'EAM(안전설비시스템)'
                        equipment_data_list.append(daily_eam)
                        self.logger.info(f"EAM 데이터 {len(daily_eam)}건 로드")
                        
                except Exception as e:
                    self.logger.debug(f"EAM 데이터 로드 실패: {e}")
            
            # 통합된 장비 데이터 로드 (equipment_data_merged)
            merged_data = pickle_manager.load_dataframe(name='equipment_data_merged')
            if merged_data is not None and not merged_data.empty:
                try:
                    # 사번을 숫자로 변환
                    emp_id_int = int(employee_id)
                    merged_data['employee_id'] = pd.to_numeric(merged_data['employee_id'], errors='coerce')
                    
                    # 날짜 필터링
                    daily_merged = merged_data[
                        (merged_data['employee_id'] == emp_id_int) & 
                        (pd.to_datetime(merged_data['timestamp']).dt.date == selected_date)
                    ].copy()
                    
                    if not daily_merged.empty:
                        self.logger.info(f"통합 장비 데이터 {len(daily_merged)}건 로드")
                        return daily_merged
                        
                except Exception as e:
                    self.logger.warning(f"통합 장비 데이터 로드 실패: {e}")
            
            # 개별 데이터를 통합
            if equipment_data_list:
                combined_data = pd.concat(equipment_data_list, ignore_index=True)
                combined_data = combined_data.sort_values('timestamp')
                
                # 야간/교대 근무자의 경우 시간대 필터링 (선택근무제는 제외)
                if work_type == 'night_shift':
                    # 전날 저녁 17시 ~ 당일 오전 12시까지로 필터링
                    start_time = datetime.combine(selected_date - timedelta(days=1), time(17, 0))
                    end_time = datetime.combine(selected_date, time(12, 0))
                    
                    combined_data = combined_data[
                        (pd.to_datetime(combined_data['timestamp']) >= start_time) & 
                        (pd.to_datetime(combined_data['timestamp']) < end_time)
                    ]
                    self.logger.info(f"야간 근무자 장비 데이터 필터링: {start_time} ~ {end_time}")
                
                self.logger.info(f"총 {len(combined_data)}건의 장비 사용 데이터")
                return combined_data if not combined_data.empty else None
            
            return None
            
        except Exception as e:
            self.logger.error(f"장비 데이터 로드 실패: {e}")
            return None
    
    def check_work_hour_compliance(self, employee_id: str, selected_date: date, work_hours: float):
        """근무제별 근무시간 준수 여부 확인"""
        work_type = self.get_employee_work_type(employee_id, selected_date)
        
        compliance = {
            'work_type': work_type,
            'work_type_name': '',
            'is_compliant': True,
            'violations': [],
            'details': {}
        }
        
        if work_type == 'selective':
            compliance['work_type_name'] = '선택적 근로시간제'
            
            # 월 단위 계산을 위한 데이터 필요
            month_start = selected_date.replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            days_in_month = (month_end - month_start).days + 1
            weekdays_in_month = sum(1 for i in range(days_in_month) 
                                   if (month_start + timedelta(days=i)).weekday() < 5)
            
            # 의무근무시간 계산
            mandatory_hours_1 = weekdays_in_month * 8  # 평일수 × 8시간
            mandatory_hours_2 = (40 / 7) * days_in_month  # 40hr/7일 × 월일수
            mandatory_hours = max(mandatory_hours_1, mandatory_hours_2)  # 더 유리한 기준
            
            # 최대근무시간 계산
            max_hours = (52 / 7) * days_in_month
            
            compliance['details'] = {
                'mandatory_hours': round(mandatory_hours, 2),
                'max_hours': round(max_hours, 2),
                'current_month_days': days_in_month,
                'current_month_weekdays': weekdays_in_month
            }
            
            # 일 최소 1분 이상 체크
            if work_hours < 0.017:  # 1분 = 0.017시간
                compliance['is_compliant'] = False
                compliance['violations'].append("일 최소 1분 이상 근무 필요")
                
        elif work_type == 'flexible':
            compliance['work_type_name'] = '탄력적 근로시간제'
            
            # 의무 근무시간: 1일 11시간
            mandatory_hours = 11
            
            compliance['details'] = {
                'mandatory_hours': mandatory_hours,
                'schedule_type': '주간(08:00-20:30) 또는 야간(20:00-08:30)'
            }
            
            # 11시간 근무 체크
            if work_hours < mandatory_hours:
                compliance['is_compliant'] = False
                compliance['violations'].append(f"의무 근무시간(11시간) 미달: {work_hours:.1f}시간")
                
        else:
            compliance['work_type_name'] = '표준 근로시간제'
            compliance['details'] = {
                'standard_hours': 8
            }
        
        return compliance
    
    def _apply_location_based_classification(self, daily_data: pd.DataFrame) -> int:
        """위치 기반 우선 분류 - 식당/카페테리아는 절대 MOVEMENT가 될 수 없음"""
        count = 0
        
        # 식당/카페테리아 키워드
        meal_location_keywords = [
            '탕맛기픈', '식당', '카페테리아', 'CAFETERIA', 'BP', '구내식당',
            '카페', '음식', '푸드', 'FOOD', '급식', '식사'
        ]
        
        for idx in daily_data.index:
            location = str(daily_data.loc[idx, 'DR_NM']) if 'DR_NM' in daily_data.columns else ''
            
            # 식당 관련 위치인 경우 강제로 식사로 분류
            if any(keyword in location for keyword in meal_location_keywords):
                # 시간대별 식사 분류
                hour = daily_data.loc[idx, 'datetime'].hour if 'datetime' in daily_data.columns else 12
                
                if 6 <= hour <= 9:
                    daily_data.loc[idx, 'activity_code'] = 'BREAKFAST'
                elif 11 <= hour <= 14:
                    daily_data.loc[idx, 'activity_code'] = 'LUNCH'
                elif 17 <= hour <= 20:
                    daily_data.loc[idx, 'activity_code'] = 'DINNER'
                elif 23 <= hour or hour <= 2:
                    daily_data.loc[idx, 'activity_code'] = 'MIDNIGHT_MEAL'
                else:
                    daily_data.loc[idx, 'activity_code'] = 'LUNCH'  # 기본값
                
                daily_data.loc[idx, 'confidence'] = 95
                daily_data.loc[idx, 'activity_type'] = 'meal'
                count += 1
                
                self.logger.info(f"🍽️ 위치 기반 식사 분류: {location} → {daily_data.loc[idx, 'activity_code']}")
        
        return count

    def classify_activities(self, daily_data: pd.DataFrame, employee_id: str = None, selected_date: date = None):
        """활동 분류 수행 (HMM 기반)"""
        try:
            # 태깅지점 마스터 데이터 로드
            tag_location_master = self.get_tag_location_master()
            
            # 위치 기반 우선 분류 제거 - 태그 기반으로만 처리
            # location_based_count = self._apply_location_based_classification(daily_data)
            # self.logger.info(f"🔍 위치 기반 우선 분류: {location_based_count}건 처리")
            
            # 기본 활동 분류 - 기존 값이 없는 경우에만 설정
            if 'activity_code' not in daily_data.columns:
                daily_data['activity_code'] = 'WORK'  # 기본값
            if 'work_area_type' not in daily_data.columns:
                daily_data['work_area_type'] = 'Y'  # 기본값 (근무구역)
            if 'work_status' not in daily_data.columns:
                daily_data['work_status'] = 'W'  # 기본값 (근무상태)
            if 'activity_label' not in daily_data.columns:
                daily_data['activity_label'] = 'YW'  # 기본값 (근무구역에서 근무중)
            if 'confidence' not in daily_data.columns:
                daily_data['confidence'] = 80  # 기본 신뢰도
            if 'is_takeout' not in daily_data.columns:
                daily_data['is_takeout'] = False  # 테이크아웃 여부 기본값 False
            # Tag_Code는 기본값을 설정하지 않음 - 마스터 데이터에서 가져와야 함
            if 'protected_from_meal' not in daily_data.columns:
                daily_data['protected_from_meal'] = False  # 식사 분류 보호 플래그
            
            # O 태그 (장비 사용) 처리
            o_tag_mask = daily_data['INOUT_GB'] == 'O'
            if o_tag_mask.any():
                daily_data.loc[o_tag_mask, 'activity_code'] = 'EQUIPMENT_OPERATION'
                daily_data.loc[o_tag_mask, 'confidence'] = 98  # 장비 사용 로그는 높은 신뢰도
                daily_data.loc[o_tag_mask, 'work_area_type'] = 'Y'  # 장비 사용은 근무구역
                daily_data.loc[o_tag_mask, 'work_status'] = 'O'  # 장비 조작 상태
                daily_data.loc[o_tag_mask, 'activity_label'] = 'YO'  # 근무구역에서 장비조작
                self.logger.info(f"O 태그 {o_tag_mask.sum()}건을 EQUIPMENT_OPERATION으로 분류")
            
            # Tag_Code 기반 추가 분류 (Knox/Equipment 데이터)
            if 'Tag_Code' in daily_data.columns:
                # G3 태그 (회의) 처리
                g3_mask = daily_data['Tag_Code'] == 'G3'
                if g3_mask.any():
                    daily_data.loc[g3_mask, 'activity_code'] = 'G3_MEETING'
                    daily_data.loc[g3_mask, 'confidence'] = 100  # 회의 데이터는 확실함
                    daily_data.loc[g3_mask, 'work_area_type'] = 'Y'
                    daily_data.loc[g3_mask, 'work_status'] = 'M'  # Meeting
                    daily_data.loc[g3_mask, 'activity_label'] = 'YM'
                    self.logger.info(f"G3 태그 {g3_mask.sum()}건을 G3_MEETING으로 분류")
                
                # O 태그 추가 처리 (Knox/Equipment 데이터)
                o_Tag_Code_mask = daily_data['Tag_Code'] == 'O'
                if o_Tag_Code_mask.any():
                    # source 정보로 세부 분류
                    if 'source' in daily_data.columns:
                        knox_approval_mask = o_Tag_Code_mask & (daily_data['source'] == 'knox_approval')
                        knox_mail_mask = o_Tag_Code_mask & (daily_data['source'] == 'knox_mail')
                        eam_mask = o_Tag_Code_mask & (daily_data['source'] == 'equipment_eam')
                        lams_mask = o_Tag_Code_mask & (daily_data['source'] == 'equipment_lams')
                        mes_mask = o_Tag_Code_mask & (daily_data['source'] == 'equipment_mes')
                        
                        if knox_approval_mask.any():
                            daily_data.loc[knox_approval_mask, 'activity_code'] = 'KNOX_APPROVAL'
                            self.logger.info(f"Knox Approval {knox_approval_mask.sum()}건 분류")
                        
                        if knox_mail_mask.any():
                            daily_data.loc[knox_mail_mask, 'activity_code'] = 'KNOX_MAIL'
                            self.logger.info(f"Knox Mail {knox_mail_mask.sum()}건 분류")
                        
                        if eam_mask.any():
                            daily_data.loc[eam_mask, 'activity_code'] = 'EAM_WORK'
                            self.logger.info(f"EAM {eam_mask.sum()}건 분류")
                        
                        if lams_mask.any():
                            daily_data.loc[lams_mask, 'activity_code'] = 'LAMS_WORK'
                            self.logger.info(f"LAMS {lams_mask.sum()}건 분류")
                        
                        if mes_mask.any():
                            daily_data.loc[mes_mask, 'activity_code'] = 'MES_WORK'
                            self.logger.info(f"MES {mes_mask.sum()}건 분류")
                    else:
                        # source 정보가 없으면 일반 O태그 작업으로
                        daily_data.loc[o_Tag_Code_mask, 'activity_code'] = 'O_TAG_WORK'
                    
                    daily_data.loc[o_Tag_Code_mask, 'confidence'] = 95
                    daily_data.loc[o_Tag_Code_mask, 'work_area_type'] = 'Y'
                    daily_data.loc[o_Tag_Code_mask, 'work_status'] = 'W'
                    daily_data.loc[o_Tag_Code_mask, 'activity_label'] = 'YW'
            
            # 디버깅: DR_NM 값 확인
            unique_dr_nm = daily_data['DR_NM'].unique()
            gate_related = [dr for dr in unique_dr_nm if any(keyword in str(dr).upper() for keyword in ['정문', '게이트', 'GATE', 'SPEED', '입구', '출구'])]
            if gate_related:
                self.logger.info(f"게이트 관련 DR_NM 발견: {gate_related}")
            
            # 근무 유형 확인
            work_type = self.get_employee_work_type(employee_id, selected_date) if employee_id and selected_date else 'standard'
            
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
                
                # 701-10-1-1 특별 체크
                if '701-10-1-1' in daily_data['DR_NO_str'].values:
                    self.logger.info("701-10-1-1이 daily_data에 있음")
                    matching_master = tag_location_master[tag_location_master['DR_NO_str'] == '701-10-1-1']
                    if not matching_master.empty:
                        self.logger.info(f"701-10-1-1 마스터 데이터: Tag_Code={matching_master.iloc[0]['Tag_Code']}")
                    else:
                        self.logger.info("701-10-1-1이 마스터에 없음")
                        # 701-10으로 매칭 시도 (DR_NO의 앞부분만)
                        dr_no_prefix = '701-10'
                        matching_prefix = tag_location_master[tag_location_master['DR_NO_str'].str.startswith(dr_no_prefix)]
                        if not matching_prefix.empty:
                            self.logger.info(f"{dr_no_prefix}로 시작하는 마스터 {len(matching_prefix)}건:")
                            for idx, row in matching_prefix.head(3).iterrows():
                                self.logger.info(f"  - DR_NO={row['DR_NO_str']}, DR_NM={row['DR_NM']}, Tag_Code={row.get('Tag_Code', 'N/A')}")
                        
                        # 정문 SPEED GATE 관련 마스터 데이터 확인
                        speed_gate_masters = tag_location_master[tag_location_master['DR_NM'].str.contains('정문.*SPEED GATE', case=False, na=False, regex=True)]
                        if not speed_gate_masters.empty:
                            self.logger.info(f"정문 SPEED GATE 관련 마스터 {len(speed_gate_masters)}건:")
                            for idx, row in speed_gate_masters.head(5).iterrows():
                                self.logger.info(f"  - DR_NO={row['DR_NO_str']}, DR_NM={row['DR_NM']}, Tag_Code={row.get('Tag_Code', 'N/A')}")
                
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
                
                # INOUT_GB가 있으면 포함 (정확한 매칭을 위해)
                if 'INOUT_GB' in tag_location_master.columns:
                    join_columns.append('INOUT_GB')
                
                # INOUT_GB 값 표준화 (입문/출문 -> IN/OUT 또는 그 반대)
                if 'INOUT_GB' in daily_data.columns:
                    # 원본 값 백업
                    daily_data['INOUT_GB_ORIGINAL'] = daily_data['INOUT_GB'].copy()
                    
                    # 데이터와 마스터의 INOUT_GB 값 형식 확인
                    data_inout_values = set(daily_data['INOUT_GB'].dropna().unique())
                    master_inout_values = set(tag_location_master['INOUT_GB'].dropna().unique()) if 'INOUT_GB' in tag_location_master.columns else set()
                    
                    self.logger.info(f"데이터 INOUT_GB 값: {data_inout_values}")
                    self.logger.info(f"마스터 INOUT_GB 값: {master_inout_values}")
                    
                    # 값 형식이 다른 경우 변환
                    if '입문' in data_inout_values and 'IN' in master_inout_values:
                        # 한글 -> 영문 변환
                        daily_data['INOUT_GB'] = daily_data['INOUT_GB'].replace({'입문': 'IN', '출문': 'OUT'})
                        self.logger.info("INOUT_GB 값 변환: 입문->IN, 출문->OUT")
                    elif 'IN' in data_inout_values and '입문' in master_inout_values:
                        # 영문 -> 한글 변환
                        daily_data['INOUT_GB'] = daily_data['INOUT_GB'].replace({'IN': '입문', 'OUT': '출문'})
                        self.logger.info("INOUT_GB 값 변환: IN->입문, OUT->출문")
                
                # 🚨 DR_NM 기반 매칭 우선 시도 (표기명 우선, 게이트명 차선)
                Tag_Code_matched = False
                
                # 1. DR_NM과 표기명으로 매칭 시도
                if 'DR_NM' in daily_data.columns and '표기명' in tag_location_master.columns:
                    self.logger.info("🔍 DR_NM과 표기명으로 Tag_Code 조회 시도")
                    
                    # 필요한 컬럼만 선택
                    display_columns = ['표기명', 'Tag_Code']
                    for col in ['공간구분_NM', '세부유형_NM', '라벨링_활동', '근무구역여부', '근무', '라벨링', 'INOUT_GB']:
                        if col in tag_location_master.columns:
                            display_columns.append(col)
                    
                    # DR_NM과 표기명으로 매칭
                    daily_data_temp = daily_data.merge(
                        tag_location_master[display_columns],
                        left_on='DR_NM',
                        right_on='표기명',
                        how='left',
                        suffixes=('', '_display')
                    )
                    
                    # 표기명으로 매칭된 경우 정보 업데이트
                    display_matched = daily_data_temp['Tag_Code_display'].notna()
                    if display_matched.any():
                        for col in display_columns:
                            if col != '표기명' and f'{col}_display' in daily_data_temp.columns:
                                daily_data.loc[display_matched, col] = daily_data_temp.loc[display_matched, f'{col}_display']
                        self.logger.info(f"✅ 표기명 매칭으로 {display_matched.sum()}건의 Tag_Code 찾음")
                        Tag_Code_matched = True
                
                # 2. 표기명으로 못 찾은 경우 게이트명으로 매칭 시도
                if not Tag_Code_matched and 'DR_NM' in daily_data.columns and '게이트명' in tag_location_master.columns:
                    self.logger.info("🔍 DR_NM과 게이트명으로 Tag_Code 조회 시도")
                    
                    # 필요한 컬럼만 선택
                    gate_columns = ['게이트명', 'Tag_Code']
                    for col in ['공간구분_NM', '세부유형_NM', '라벨링_활동', '근무구역여부', '근무', '라벨링']:
                        if col in tag_location_master.columns:
                            gate_columns.append(col)
                    
                    # DR_NM과 게이트명으로 매칭
                    daily_data_temp = daily_data.merge(
                        tag_location_master[gate_columns],
                        left_on='DR_NM',
                        right_on='게이트명',
                        how='left',
                        suffixes=('', '_gate')
                    )
                    
                    # 게이트명으로 매칭된 경우 정보 업데이트 (Tag_Code가 없는 것만)
                    gate_matched = daily_data_temp['Tag_Code_gate'].notna()
                    no_tag_mask = daily_data['Tag_Code'].isna() if 'Tag_Code' in daily_data.columns else pd.Series([True] * len(daily_data))
                    update_mask = gate_matched & no_tag_mask
                    
                    if update_mask.any():
                        for col in gate_columns:
                            if col != '게이트명' and f'{col}_gate' in daily_data_temp.columns:
                                daily_data.loc[update_mask, col] = daily_data_temp.loc[update_mask, f'{col}_gate']
                        self.logger.info(f"✅ 게이트명 매칭으로 {update_mask.sum()}건의 Tag_Code 찾음")
                
                # DR_NO_str + INOUT_GB로 추가 매칭 (게이트명으로 못 찾은 경우)
                if 'INOUT_GB' in daily_data.columns and 'INOUT_GB' in tag_location_master.columns:
                    self.logger.info("DR_NO + INOUT_GB 조합으로 추가 조인")
                    
                    # 이동 관련 태그 디버깅
                    movement_tags = daily_data[daily_data['DR_NO_str'].str.startswith('701', na=False)].head(5)
                    if not movement_tags.empty:
                        self.logger.info(f"이동 태그 샘플 (조인 전):")
                        for idx, row in movement_tags.iterrows():
                            self.logger.info(f"  - DR_NO={row['DR_NO_str']}, INOUT_GB={row.get('INOUT_GB', 'N/A')}")
                        
                        # 마스터 데이터의 INOUT_GB 값 확인
                        master_inout_values = tag_location_master['INOUT_GB'].unique()
                        self.logger.info(f"마스터 데이터의 INOUT_GB 고유값: {master_inout_values}")
                        
                        # 701로 시작하는 마스터 샘플
                        master_701 = tag_location_master[tag_location_master['DR_NO_str'].str.startswith('701', na=False)].head(10)
                        if not master_701.empty:
                            self.logger.info("701로 시작하는 마스터 데이터 샘플:")
                            for idx, row in master_701.iterrows():
                                self.logger.info(f"  - DR_NO={row['DR_NO_str']}, INOUT_GB={row.get('INOUT_GB', 'N/A')}, Tag_Code={row.get('Tag_Code', 'N/A')}")
                        
                        # 마스터에서 매칭되는 것 찾기
                        for idx, row in movement_tags.iterrows():
                            dr_no = row['DR_NO_str']
                            inout_gb = row.get('INOUT_GB', '')
                            master_match = tag_location_master[
                                (tag_location_master['DR_NO_str'] == dr_no) & 
                                (tag_location_master['INOUT_GB'] == inout_gb)
                            ]
                            if not master_match.empty:
                                self.logger.info(f"  마스터 매치 발견: DR_NO={dr_no}, INOUT_GB={inout_gb}, Tag_Code={master_match.iloc[0].get('Tag_Code', 'N/A')}")
                            else:
                                self.logger.info(f"  마스터 매치 없음: DR_NO={dr_no}, INOUT_GB={inout_gb}")
                    
                    daily_data = daily_data.merge(
                        tag_location_master[join_columns],
                        on=['DR_NO_str', 'INOUT_GB'],
                        how='left',
                        suffixes=('', '_master')
                    )
                    
                    # 조인 후 이동 태그 확인
                    movement_tags_after = daily_data[daily_data['DR_NO_str'].str.startswith('701', na=False)].head(5)
                    if not movement_tags_after.empty:
                        self.logger.info(f"이동 태그 샘플 (조인 후):")
                        for idx, row in movement_tags_after.iterrows():
                            self.logger.info(f"  - DR_NO={row['DR_NO_str']}, INOUT_GB={row.get('INOUT_GB', 'N/A')}, Tag_Code={row.get('Tag_Code', 'N/A')}")
                else:
                    # DR_NO_str만으로 조인 (fallback)
                    self.logger.info("DR_NO만으로 조인 (fallback)")
                    daily_data = daily_data.merge(
                        tag_location_master[join_columns],
                        on='DR_NO_str',
                        how='left',
                        suffixes=('', '_master')
                    )
                
                # 매칭되지 않은 레코드에 대해 prefix 매칭 시도
                unmatched_mask = daily_data['Tag_Code'].isna() if 'Tag_Code' in daily_data.columns else pd.Series([True] * len(daily_data))
                if unmatched_mask.any():
                    self.logger.info(f"매칭되지 않은 {unmatched_mask.sum()}건에 대해 prefix 매칭 시도")
                    
                    # 각 매칭되지 않은 레코드에 대해 처리
                    for idx in daily_data[unmatched_mask].index:
                        dr_no = daily_data.loc[idx, 'DR_NO_str']
                        dr_nm = daily_data.loc[idx, 'DR_NM']
                        
                        # DR_NO의 prefix로 매칭 시도 (예: '701-10-1-1' -> '701-10')
                        if '-' in dr_no:
                            dr_prefix = '-'.join(dr_no.split('-')[:2])  # 첫 두 부분만 사용
                            prefix_match = tag_location_master[tag_location_master['DR_NO_str'].str.startswith(dr_prefix)]
                            
                            # DR_NM도 비슷한지 확인
                            if not prefix_match.empty:
                                # DR_NM에서 유사한 것 찾기
                                for _, master_row in prefix_match.iterrows():
                                    if any(word in dr_nm for word in str(master_row['DR_NM']).split()):
                                        # 매칭된 마스터 데이터 적용
                                        for col in join_columns:
                                            if col != 'DR_NO_str' and col in master_row:
                                                daily_data.loc[idx, col] = master_row[col]
                                        self.logger.info(f"Prefix 매칭 성공: {dr_no} -> {master_row['DR_NO_str']}")
                                        break
                
                # 조인 후 결과 확인
                if 'Tag_Code' in daily_data.columns:
                    matched_count = daily_data['Tag_Code'].notna().sum()
                elif '근무구역여부' in daily_data.columns:
                    matched_count = daily_data['근무구역여부'].notna().sum()
                else:
                    matched_count = 0
                self.logger.info(f"조인 결과: {matched_count}/{len(daily_data)} 매칭됨")
                
                # 701-10-1-1 조인 후 체크
                if '701-10-1-1' in daily_data['DR_NO_str'].values:
                    test_rows = daily_data[daily_data['DR_NO_str'] == '701-10-1-1']
                    self.logger.info(f"701-10-1-1 조인 후 {len(test_rows)}건:")
                    for idx, test_row in test_rows.head(3).iterrows():
                        self.logger.info(f"  - INOUT_GB={test_row.get('INOUT_GB', 'N/A')}, Tag_Code={test_row.get('Tag_Code', 'None')}")
                
                # 새로운 태그 코드 체계 적용
                if 'Tag_Code' in daily_data.columns:
                    # Tag_Code 기반 활동 분류
                    # G1~G4: 근무영역, N1~N2: 비근무영역, T1~T3: 이동구간
                    # Tag_Code가 없는 경우 정문 태그를 수동으로 매핑
                    # 디버깅: Tag_Code 상태 확인
                    Tag_Code_na_count = daily_data['Tag_Code'].isna().sum()
                    self.logger.info(f"Tag_Code가 없는 레코드: {Tag_Code_na_count}건")
                    
                    # 정문 데이터 확인
                    gate_data = daily_data[daily_data['DR_NM'].str.contains('정문|SPEED\s*GATE', case=False, na=False, regex=True)]
                    if not gate_data.empty:
                        self.logger.info(f"정문 관련 데이터 {len(gate_data)}건 발견:")
                        for idx, row in gate_data.head(3).iterrows():
                            self.logger.info(f"  - {row['datetime']}: DR_NM={row['DR_NM']}, Tag_Code={row.get('Tag_Code')}, INOUT_GB={row.get('INOUT_GB')}")
                    
                    # 매칭 후 특별 처리: 정문/SPEED GATE는 무조건 T2/T3로 매핑
                    # 정문 입문 -> T2
                    gate_entry_mask = (daily_data['DR_NM'].str.contains('정문|SPEED\s*GATE', case=False, na=False, regex=True)) & \
                                    (daily_data['INOUT_GB'] == '입문')
                    if gate_entry_mask.any():
                        daily_data.loc[gate_entry_mask, 'Tag_Code'] = 'T2'
                        self.logger.info(f"정문 입문 {gate_entry_mask.sum()}건을 강제로 T2로 매핑")
                    
                    # 정문 출문 -> T3
                    gate_exit_mask = (daily_data['DR_NM'].str.contains('정문|SPEED\s*GATE', case=False, na=False, regex=True)) & \
                                    (daily_data['INOUT_GB'] == '출문')
                    if gate_exit_mask.any():
                        daily_data.loc[gate_exit_mask, 'Tag_Code'] = 'T3'
                        self.logger.info(f"정문 출문 {gate_exit_mask.sum()}건을 강제로 T3로 매핑")
                    
                    # Tag_Code가 없거나 잘못된 정문 데이터를 찾기
                    gate_entry_mask = ((daily_data['Tag_Code'].isna()) | (daily_data['Tag_Code'] != 'T2')) & \
                                    (daily_data['DR_NM'].str.contains('정문|SPEED\s*GATE', case=False, na=False, regex=True)) & \
                                    (daily_data['INOUT_GB'] == '입문')
                    gate_exit_mask = ((daily_data['Tag_Code'].isna()) | (daily_data['Tag_Code'] != 'T3')) & \
                                   (daily_data['DR_NM'].str.contains('정문|SPEED\s*GATE', case=False, na=False, regex=True)) & \
                                   (daily_data['INOUT_GB'] == '출문')
                    
                    # 정문 태그 매핑
                    if gate_entry_mask.any():
                        daily_data.loc[gate_entry_mask, 'Tag_Code'] = 'T2'
                        self.logger.info(f"Tag_Code 누락된 정문 입문을 T2로 매핑: {gate_entry_mask.sum()}건")
                    
                    if gate_exit_mask.any():
                        daily_data.loc[gate_exit_mask, 'Tag_Code'] = 'T3'
                        self.logger.info(f"Tag_Code 누락된 정문 출문을 T3로 매핑: {gate_exit_mask.sum()}건")
                    
                    # 태그 기반 시스템에서는 DR_NM 키워드로 Tag_Code를 강제 변경하지 않음
                    # M1/M2 태그는 마스터 데이터에서만 할당됨
                    
                    # Tag_Code를 Tag_Code로 복사 (기본값은 G1)
                    daily_data['Tag_Code'] = daily_data['Tag_Code'].fillna('G1')
                    
                    # 디버깅: Tag_Code 설정 후 확인
                    gate_tags = daily_data[daily_data['DR_NM'].str.contains('정문|SPEED GATE', case=False, na=False)]
                    if not gate_tags.empty:
                        self.logger.info(f"정문/SPEED GATE 태그 설정 확인:")
                        for idx, row in gate_tags.head().iterrows():
                            self.logger.info(f"  - {row['datetime']}: {row['DR_NM']} -> Tag_Code={row.get('Tag_Code', 'N/A')}, Tag_Code={row.get('Tag_Code', 'N/A')}")
                    
                    # 디버깅: 701-10-1-1의 Tag_Code 확인
                    gate_701_after = daily_data[daily_data['DR_NO'] == '701-10-1-1']
                    if not gate_701_after.empty:
                        self.logger.info(f"[조인 후] 701-10-1-1의 Tag_Code 설정됨:")
                        for idx, row in gate_701_after.head().iterrows():
                            self.logger.info(f"  - {row['datetime']}: Tag_Code={row.get('Tag_Code')}, Tag_Code={row.get('Tag_Code')}, INOUT_GB={row.get('INOUT_GB')}")
                    daily_data['space_type'] = daily_data['공간구분_NM'].fillna('근무영역')  # 기본값
                    daily_data['detail_type'] = daily_data['세부유형_NM'].fillna('주업무공간')  # 기본값
                    daily_data['allowed_activities'] = daily_data['라벨링_활동'].fillna('업무, 식사, 휴게')  # 기본값
                    
                    # 기존 컬럼과의 호환성 유지
                    # Tag_Code를 기반으로 work_area_type 설정
                    daily_data.loc[daily_data['Tag_Code'].str.startswith('G'), 'work_area_type'] = 'Y'  # 근무영역
                    daily_data.loc[daily_data['Tag_Code'].str.startswith('N'), 'work_area_type'] = 'N'  # 비근무영역
                    daily_data.loc[daily_data['Tag_Code'].str.startswith('T'), 'work_area_type'] = 'T'  # 이동구간
                else:
                    # 기존 방식 유지 (호환성)
                    if '근무구역여부' in daily_data.columns:
                        daily_data['work_area_type'] = daily_data['근무구역여부'].fillna('Y')
                    if '근무' in daily_data.columns:
                        daily_data['work_status'] = daily_data['근무'].fillna('W')
                    if '라벨링' in daily_data.columns:
                        daily_data['activity_label'] = daily_data['라벨링'].fillna('YW')
                        
                        # 라벨링이 T2/T3가 아닌 경우, 정문 태그를 수동으로 매핑
                        gate_entry_mask = (daily_data['DR_NM'].str.contains('정문|SPEED\s*GATE', case=False, na=False, regex=True)) & \
                                        (daily_data['INOUT_GB'] == '입문')
                        gate_exit_mask = (daily_data['DR_NM'].str.contains('정문|SPEED\s*GATE', case=False, na=False, regex=True)) & \
                                       (daily_data['INOUT_GB'] == '출문')
                        
                        if gate_entry_mask.any():
                            daily_data.loc[gate_entry_mask, 'Tag_Code'] = 'T2'
                            self.logger.info(f"정문 입문을 T2로 매핑: {gate_entry_mask.sum()}건")
                        
                        if gate_exit_mask.any():
                            daily_data.loc[gate_exit_mask, 'Tag_Code'] = 'T3'
                            self.logger.info(f"정문 출문을 T3로 매핑: {gate_exit_mask.sum()}건")
                
                # Tag_Code 기반 기본 활동 분류
                if 'Tag_Code' in daily_data.columns:
                    # G1: 주업무공간 -> 업무
                    daily_data.loc[daily_data['Tag_Code'] == 'G1', 'activity_code'] = 'WORK'
                    
                    # G2: 보조업무공간 -> 준비
                    daily_data.loc[daily_data['Tag_Code'] == 'G2', 'activity_code'] = 'WORK_PREPARATION'
                    
                    # G3: 협업공간 -> 회의
                    daily_data.loc[daily_data['Tag_Code'] == 'G3', 'activity_code'] = 'MEETING'
                    
                    # G4: 교육공간 -> 교육
                    daily_data.loc[daily_data['Tag_Code'] == 'G4', 'activity_code'] = 'TRAINING'
                    
                    # N1: 휴게공간 -> 휴게
                    daily_data.loc[daily_data['Tag_Code'] == 'N1', 'activity_code'] = 'REST'
                    
                    # N2: 복지공간 -> 휴게
                    daily_data.loc[daily_data['Tag_Code'] == 'N2', 'activity_code'] = 'REST'
                    
                    # T1: 건물/구역 연결 -> 짧은 시간만 이동으로 분류
                    t1_mask = daily_data['Tag_Code'] == 'T1'
                    if t1_mask.any():
                        # T1 태그의 duration을 확인하여 짧은 것만 이동으로 분류
                        t1_movement_count = 0
                        t1_work_count = 0
                        for idx in daily_data[t1_mask].index:
                            duration = daily_data.loc[idx, 'duration_minutes']
                            if pd.isna(duration) or duration <= 10:  # 10분 이하만 이동
                                daily_data.loc[idx, 'activity_code'] = 'MOVEMENT'
                                t1_movement_count += 1
                            else:  # 10분 초과는 작업으로 분류
                                daily_data.loc[idx, 'activity_code'] = 'WORK'
                                t1_work_count += 1
                        self.logger.info(f"🔍 T1 태그 처리: 총 {t1_mask.sum()}건 → MOVEMENT {t1_movement_count}건, WORK {t1_work_count}건")
                    
                    # T2: 출입포인트(IN) -> 출근으로 처리
                    t2_mask = daily_data['Tag_Code'] == 'T2'
                    if t2_mask.any():
                        # T2는 무조건 COMMUTE_IN으로 처리 (시간대 제한 제거)
                        daily_data.loc[t2_mask, 'activity_code'] = 'COMMUTE_IN'
                        daily_data.loc[t2_mask, 'activity_type'] = 'commute'
                        daily_data.loc[t2_mask, 'confidence'] = 100
                        daily_data.loc[t2_mask, 'activity_label'] = ''  # YW 대신 빈 문자열로 설정
                        activity_type_obj = get_activity_type('COMMUTE_IN')
                        if activity_type_obj:
                            daily_data.loc[t2_mask, '활동분류'] = activity_type_obj.name_ko
                        self.logger.info(f"T2 태그 처리: {t2_mask.sum()}건 -> 모두 COMMUTE_IN으로 설정")
                        
                        # 디버깅: T2 태그 처리 결과 확인
                        t2_data_after = daily_data[t2_mask]
                        if not t2_data_after.empty:
                            self.logger.info(f"[T2 처리 후] 활동 분류 결과:")
                            for idx, row in t2_data_after.head().iterrows():
                                self.logger.info(f"  - {row['datetime']}: activity_code={row.get('activity_code')}, DR_NM={row.get('DR_NM')}")
                        
                        # T2 태그는 식사로 분류되지 않도록 표시
                        daily_data.loc[t2_mask, 'protected_from_meal'] = True
                    
                    # T3: 출입포인트(OUT) -> 시간대별 출퇴근 처리
                    t3_mask = daily_data['Tag_Code'] == 'T3'
                    if t3_mask.any():
                        for idx in daily_data[t3_mask].index:
                            hour = daily_data.loc[idx, 'datetime'].hour
                            # 야간 근무자는 5-10시 퇴근, 일반 근무자는 17-22시 퇴근
                            if (work_type == 'night_shift' and 5 <= hour <= 10) or \
                               (work_type != 'night_shift' and 17 <= hour <= 22):
                                daily_data.loc[idx, 'activity_code'] = 'COMMUTE_OUT'
                                daily_data.loc[idx, 'activity_type'] = 'commute'
                                daily_data.loc[idx, 'confidence'] = 100
                            else:
                                daily_data.loc[idx, 'activity_code'] = 'MOVEMENT'
                                daily_data.loc[idx, 'activity_type'] = 'movement'
                        self.logger.info(f"T3 태그 처리: {t3_mask.sum()}건")
                        
                        # T3 태그는 식사로 분류되지 않도록 표시
                        daily_data.loc[t3_mask, 'protected_from_meal'] = True
                
                # 이미 위에서 정문 태그를 처리했으므로 이 부분은 삭제
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
                        
                        # YM: 근무구역에서 이동중 -> 짧은 시간만 이동으로 분류
                        ym_mask = daily_data['activity_label'] == 'YM'
                        if ym_mask.any():
                            ym_movement_count = 0
                            ym_work_count = 0
                            for idx in daily_data[ym_mask].index:
                                duration = daily_data.loc[idx, 'duration_minutes']
                                if pd.isna(duration) or duration <= 15:  # 15분 이하만 이동
                                    daily_data.loc[idx, 'activity_code'] = 'MOVEMENT'
                                    ym_movement_count += 1
                                else:  # 15분 초과는 작업으로 분류 (근무구역에서 장시간)
                                    daily_data.loc[idx, 'activity_code'] = 'WORK'
                                    ym_work_count += 1
                            self.logger.info(f"🔍 YM 태그 처리: 총 {ym_mask.sum()}건 → MOVEMENT {ym_movement_count}건, WORK {ym_work_count}건")
            
            # HMM 분류기 사용 전에 is_actual_meal 플래그 확인
            if 'is_actual_meal' not in daily_data.columns:
                daily_data['is_actual_meal'] = False
            
            # HMM 분류 전에 식사 관련 태그 미리 표시하여 HMM이 잘못 분류하지 않도록 함
            meal_mask = (daily_data['INOUT_GB'] == '식사') | (daily_data['is_actual_meal'] == True)
            if meal_mask.any():
                self.logger.info("HMM 분류 전 식사 관련 태그 사전 처리")
                
                # 연속된 식사를 그룹으로 처리
                meal_groups = []
                in_meal = False
                current_group = []
                
                for idx in daily_data.index:
                    if meal_mask[idx]:
                        if not in_meal:
                            in_meal = True
                            current_group = [idx]
                        else:
                            current_group.append(idx)
                    else:
                        if in_meal and current_group:
                            meal_groups.append(current_group)
                            in_meal = False
                            current_group = []
                
                if in_meal and current_group:
                    meal_groups.append(current_group)
                
                # 각 식사 그룹에 대해 전후 처리
                for group in meal_groups:
                    first_meal_time = daily_data.loc[group[0], 'datetime']
                    last_meal_time = daily_data.loc[group[-1], 'datetime']
                    
                    # 식사 전 출문은 MOVEMENT로 강제 설정 (원래대로 복원)
                    before_mask = (
                        (daily_data['datetime'] >= first_meal_time - timedelta(minutes=30)) & 
                        (daily_data['datetime'] < first_meal_time) &
                        (daily_data['INOUT_GB'] == '출문')
                    )
                    if before_mask.any():
                        # 디버깅: 변경 전 상태 확인
                        for idx in daily_data[before_mask].index:
                            prev_code = daily_data.loc[idx, 'activity_code']
                            self.logger.info(f"식사 전 출문 사전 설정 - {daily_data.loc[idx, 'datetime']}: {prev_code} -> MOVEMENT")
                        
                        daily_data.loc[before_mask, 'activity_code'] = 'MOVEMENT'
                        daily_data.loc[before_mask, 'confidence'] = 95
                        self.logger.info(f"식사 전 출문 사전 설정 완료: {before_mask.sum()}건")
                    
                    # 식사 후 첫 입문은 WORK로 강제 설정
                    after_mask = (
                        (daily_data['datetime'] > last_meal_time) & 
                        (daily_data['datetime'] <= last_meal_time + timedelta(minutes=30)) &
                        (daily_data['INOUT_GB'] == '입문')
                    )
                    if after_mask.any():
                        first_idx = daily_data[after_mask].index[0]
                        daily_data.loc[first_idx, 'activity_code'] = 'WORK'
                        daily_data.loc[first_idx, 'confidence'] = 95
                        self.logger.info(f"식사 후 입문 사전 설정: {daily_data.loc[first_idx, 'datetime']}")
            
            # HMM 분류기 비활성화 - 태그 기반 규칙만 사용
            # HMM은 태그 기반 시스템과 충돌하므로 사용하지 않음
            # 참조: /Users/hanskim/Project/SambioHR2/태그 기반 근무유형 분석 시스템 - 참조 문서.md
            self.logger.info("HMM 분류 대신 태그 기반 규칙 사용")
            
            # 디버깅: 스피드게이트 태그 확인
            speed_gate_data = daily_data[daily_data['DR_NM'].str.contains('SPEED GATE', case=False, na=False)]
            if not speed_gate_data.empty:
                self.logger.info(f"스피드게이트 태그 {len(speed_gate_data)}개 발견:")
                for idx, row in speed_gate_data.iterrows():
                    self.logger.info(f"  - {row['datetime']}: {row['DR_NM']}, Tag_Code={row.get('Tag_Code', 'N/A')}, activity={row['activity_code']}")
            
            # 태그 기반 규칙 적용
            try:
                daily_data = self._apply_tag_based_rules(daily_data, tag_location_master)
                
                # 태그 기반 규칙 적용 후 추가 확인
                # T2/T3 태그가 제대로 설정된 경우 확인
                t2_count = (daily_data['Tag_Code'] == 'T2').sum()
                t3_count = (daily_data['Tag_Code'] == 'T3').sum()
                self.logger.info(f"태그 기반 규칙 적용 후: T2 태그 {t2_count}건, T3 태그 {t3_count}건")
                
                # T2 태그의 activity_code 확인
                t2_data = daily_data[daily_data['Tag_Code'] == 'T2']
                if not t2_data.empty:
                    self.logger.info(f"T2 태그의 activity_code 상태:")
                    for idx, row in t2_data.head(3).iterrows():
                        self.logger.info(f"  - {row['datetime']}: activity_code={row.get('activity_code', 'N/A')}, DR_NM={row['DR_NM']}")
                
                # 디버깅: 태그 기반 규칙 후에도 정문 태그가 WORK로 되어 있는지 확인
                gate_work_mask = daily_data['DR_NM'].str.contains('정문|SPEED GATE', case=False, na=False) & \
                                (daily_data['activity_code'] == 'WORK')
                if gate_work_mask.any():
                    self.logger.warning(f"태그 기반 규칙 후에도 정문 태그가 WORK로 분류됨: {gate_work_mask.sum()}건")
                    for idx in daily_data[gate_work_mask].index:
                        self.logger.warning(f"  - {daily_data.loc[idx, 'datetime']} at {daily_data.loc[idx, 'DR_NM']}, Tag_Code={daily_data.loc[idx, 'Tag_Code']}")
                
                # 실제 식사 태그가 없는데 식사로 분류된 경우 확인
                if 'is_actual_meal' in daily_data.columns:
                    false_meals = daily_data[
                        (daily_data['activity_code'].isin(['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL'])) &
                        (~daily_data['is_actual_meal'])
                    ]
                    if not false_meals.empty:
                        self.logger.warning(f"식사 태그 없이 식사로 분류된 건수: {len(false_meals)}")
                        for idx, row in false_meals.iterrows():
                            self.logger.warning(f"  - {row['datetime']}: {row['DR_NM']} -> {row['activity_code']}")
                
                # 식사 태그가 없는데 식사로 분류된 경우 강제로 수정
                if 'is_actual_meal' in daily_data.columns:
                    false_meal_mask = (
                        daily_data['activity_code'].isin(['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL']) &
                        (~daily_data['is_actual_meal'])
                    )
                    if false_meal_mask.any():
                        self.logger.info(f"식사 태그 없이 분류된 {false_meal_mask.sum()}건을 수정")
                        # 스피드게이트 입문이면 COMMUTE_IN으로
                        gate_in_mask = false_meal_mask & daily_data['DR_NM'].str.contains('SPEED GATE.*입문|정문.*입문', case=False, na=False)
                        daily_data.loc[gate_in_mask, 'activity_code'] = 'COMMUTE_IN'
                        daily_data.loc[gate_in_mask, 'confidence'] = 100
                        
                        # 나머지는 WORK로
                        other_mask = false_meal_mask & (~gate_in_mask)
                        daily_data.loc[other_mask, 'activity_code'] = 'WORK'
                        daily_data.loc[other_mask, 'confidence'] = 85
                
                # 스피드게이트 입문을 출근으로 강제 수정 (추가 확인)
                speed_gate_mask = daily_data['DR_NM'].str.contains('SPEED GATE.*입문|정문.*입문', case=False, na=False)
                if speed_gate_mask.any():
                    self.logger.info(f"게이트 입문 {speed_gate_mask.sum()}건을 수정")
                    # 시간대에 따른 분류
                    for idx in daily_data[speed_gate_mask].index:
                        hour = daily_data.loc[idx, 'datetime'].hour
                        if work_type == 'night_shift' and 17 <= hour <= 22:  # 야간 근무자는 저녁 출근
                            daily_data.loc[idx, 'activity_code'] = 'COMMUTE_IN'
                            daily_data.loc[idx, 'confidence'] = 100
                        elif work_type != 'night_shift' and 5 <= hour < 10:  # 일반 근무자는 아침 출근
                            daily_data.loc[idx, 'activity_code'] = 'COMMUTE_IN'
                            daily_data.loc[idx, 'confidence'] = 100
                        else:  # 그 외 시간대는 이동
                            daily_data.loc[idx, 'activity_code'] = 'MOVEMENT'
                            daily_data.loc[idx, 'confidence'] = 90
                
                # 스피드게이트/정문 출문을 퇴근으로 처리
                gate_exit_mask = daily_data['DR_NM'].str.contains('SPEED GATE.*출문|정문.*출문', case=False, na=False)
                if gate_exit_mask.any():
                    self.logger.info(f"게이트 출문 {gate_exit_mask.sum()}건을 수정")
                    # 시간대에 따른 분류
                    for idx in daily_data[gate_exit_mask].index:
                        hour = daily_data.loc[idx, 'datetime'].hour
                        if work_type == 'night_shift' and 5 <= hour <= 10:  # 야간 근무자는 아침 퇴근
                            daily_data.loc[idx, 'activity_code'] = 'COMMUTE_OUT'
                            daily_data.loc[idx, 'confidence'] = 100
                        elif work_type != 'night_shift' and 17 <= hour <= 22:  # 일반 근무자는 저녁 퇴근
                            daily_data.loc[idx, 'activity_code'] = 'COMMUTE_OUT'
                            daily_data.loc[idx, 'confidence'] = 100
                
                # 식사 전후 출문/입문 처리
                # 1. 식사 그룹 찾기 (연속된 식사 태그를 하나의 그룹으로)
                meal_mask = (daily_data['activity_code'].isin(['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL'])) | (daily_data['INOUT_GB'] == '식사')
                meal_groups = []
                
                if meal_mask.any():
                    # 연속된 식사 태그를 그룹으로 묶기
                    in_meal_group = False
                    current_group = []
                    
                    for idx in daily_data.index:
                        if meal_mask[idx]:
                            if not in_meal_group:
                                in_meal_group = True
                                current_group = [idx]
                            else:
                                current_group.append(idx)
                        else:
                            if in_meal_group:
                                # 식사 그룹 종료
                                meal_groups.append(current_group)
                                in_meal_group = False
                                current_group = []
                    
                    # 마지막 그룹 처리
                    if in_meal_group and current_group:
                        meal_groups.append(current_group)
                
                self.logger.info(f"식사 그룹 {len(meal_groups)}개 발견")
                
                # 2. 각 식사 그룹에 대해 전후 처리
                for group in meal_groups:
                    # 그룹의 첫 식사 시간과 마지막 식사 시간
                    first_meal_time = daily_data.loc[group[0], 'datetime']
                    last_meal_time = daily_data.loc[group[-1], 'datetime']
                    
                    # 식사 전 출문 처리 (첫 식사 기준)
                    before_meal_mask = (
                        (daily_data['datetime'] >= first_meal_time - timedelta(minutes=30)) & 
                        (daily_data['datetime'] < first_meal_time) &
                        (daily_data['INOUT_GB'] == '출문')
                    )
                    if before_meal_mask.any():
                        for idx in daily_data[before_meal_mask].index:
                            prev_code = daily_data.loc[idx, 'activity_code']
                            daily_data.loc[idx, 'activity_code'] = 'MOVEMENT'
                            daily_data.loc[idx, 'confidence'] = 90
                            self.logger.info(f"식사 전 출문 처리: {daily_data.loc[idx, 'datetime']} (이전: {prev_code} -> MOVEMENT)")
                    
                    # 식사 후 입문 처리 (마지막 식사 기준)
                    after_meal_mask = (
                        (daily_data['datetime'] > last_meal_time) & 
                        (daily_data['datetime'] <= last_meal_time + timedelta(minutes=30)) &
                        (daily_data['INOUT_GB'] == '입문')
                    )
                    if after_meal_mask.any():
                        # 식사 후 최초 입문만 업무 복귀로
                        first_entry_idx = daily_data[after_meal_mask].index[0]
                        prev_code = daily_data.loc[first_entry_idx, 'activity_code']
                        if prev_code != 'COMMUTE_IN':
                            daily_data.loc[first_entry_idx, 'activity_code'] = 'WORK'
                            daily_data.loc[first_entry_idx, 'confidence'] = 95
                            self.logger.info(f"식사 후 업무복귀 처리: {daily_data.loc[first_entry_idx, 'datetime']} (이전: {prev_code} -> WORK)")
                
                self.logger.info(f"식사 태그 {len(meal_indices)}개 발견")
                
                # 디버깅: 식사 전후 출문/입문 데이터 확인
                for idx in daily_data.index:
                    time_obj = daily_data.loc[idx, 'datetime'].time()
                    time_str = time_obj.strftime('%H:%M')
                    # 문제가 되는 시간대 확인
                    if time_str in ['07:39', '12:16', '17:37', '07:48', '12:33']:
                        self.logger.info(f"{time_obj} 데이터 발견 - 식사 처리 전: activity_code={daily_data.loc[idx, 'activity_code']}, INOUT_GB={daily_data.loc[idx, 'INOUT_GB']}")
                
                for meal_idx in meal_indices:
                    # 식사 후 30분 이내의 입문 태그 찾기
                    meal_time = daily_data.loc[meal_idx, 'datetime']
                    meal_code = daily_data.loc[meal_idx, 'activity_code']
                    self.logger.info(f"식사 확인: {meal_time} - {meal_code}")
                    
                    after_meal_mask = (
                        (daily_data['datetime'] > meal_time) & 
                        (daily_data['datetime'] <= meal_time + timedelta(minutes=30)) &
                        (daily_data['INOUT_GB'] == '입문')
                    )
                    
                    if after_meal_mask.any():
                        self.logger.info(f"식사 후 입문 태그 {after_meal_mask.sum()}개 발견")
                        # 식사 후 최초 입문은 무조건 업무 복귀
                        for idx in daily_data[after_meal_mask].index:
                            prev_code = daily_data.loc[idx, 'activity_code']
                            # 이미 출근으로 분류된 경우는 제외
                            if prev_code != 'COMMUTE_IN':
                                daily_data.loc[idx, 'activity_code'] = 'WORK'
                                daily_data.loc[idx, 'confidence'] = 95
                                self.logger.info(f"식사 후 업무복귀 처리: {daily_data.loc[idx, 'datetime']} - {daily_data.loc[idx, 'DR_NM']} (이전: {prev_code} -> WORK)")
                                
                                # 디버깅: 변경 확인
                                time_obj = daily_data.loc[idx, 'datetime'].time()
                                if (time_obj.hour == 12 and time_obj.minute == 33) or (time_obj.hour == 12 and time_obj.minute == 49):
                                    self.logger.info(f"{time_obj} 데이터 - 처리 후: activity_code={daily_data.loc[idx, 'activity_code']}")
                                break  # 첫 번째 입문만 처리
                
                self.logger.info("태그 기반 분류 성공")
            except Exception as hmm_error:
                self.logger.warning(f"태그 기반 분류 실패, 규칙 기반으로 대체: {hmm_error}")
                # 규칙 기반 분류로 폴백
                daily_data = self._apply_rule_based_classification(daily_data, tag_location_master)
            
            # 태그 기반 분류 후 Tag_Code가 T2/T3인 게이트를 강제로 출퇴근으로 설정
            if 'Tag_Code' in daily_data.columns:
                # T2 (출입포인트-IN) 태그를 출근으로 강제 설정
                t2_mask = (daily_data['Tag_Code'] == 'T2')
                if t2_mask.any():
                    t2_wrong = t2_mask & (~daily_data['activity_code'].isin(['COMMUTE_IN']))
                    if t2_wrong.any():
                        self.logger.warning(f"태그 기반 분류 후 T2 태그 {t2_wrong.sum()}건을 COMMUTE_IN으로 수정")
                        daily_data.loc[t2_wrong, 'activity_code'] = 'COMMUTE_IN'
                        daily_data.loc[t2_wrong, 'activity_type'] = 'commute'
                        daily_data.loc[t2_wrong, 'confidence'] = 100
                
                # T3 (출입포인트-OUT) 태그를 퇴근으로 강제 설정
                t3_mask = (daily_data['Tag_Code'] == 'T3')
                if t3_mask.any():
                    t3_wrong = t3_mask & (~daily_data['activity_code'].isin(['COMMUTE_OUT']))
                    if t3_wrong.any():
                        self.logger.warning(f"태그 기반 분류 후 T3 태그 {t3_wrong.sum()}건을 COMMUTE_OUT으로 수정")
                        daily_data.loc[t3_wrong, 'activity_code'] = 'COMMUTE_OUT'
                        daily_data.loc[t3_wrong, 'activity_type'] = 'commute'
                        daily_data.loc[t3_wrong, 'confidence'] = 100
            
            # Tag_Code 기반 신뢰도 세분화
            if 'Tag_Code' in daily_data.columns:
                # T2, T3 (출퇴근 포인트)는 가장 확실한 데이터 - 100%
                daily_data.loc[daily_data['Tag_Code'].isin(['T2', 'T3']), 'confidence'] = 100
                
                # G3 (협업공간), G4 (교육공간)는 명확한 활동 - 95%
                daily_data.loc[daily_data['Tag_Code'].isin(['G3', 'G4']), 'confidence'] = 95
                
                # G1 (주업무공간), G2 (보조업무공간)는 일반 작업 - 90%
                daily_data.loc[daily_data['Tag_Code'].isin(['G1', 'G2']), 'confidence'] = 90
                
                # N1, N2 (휴게/복지공간) - 90%
                daily_data.loc[daily_data['Tag_Code'].isin(['N1', 'N2']), 'confidence'] = 90
                
                # T1 (내부 이동) - 85%
                daily_data.loc[daily_data['Tag_Code'] == 'T1', 'confidence'] = 85
            
            # 우선순위 기반 상세 활동 분류
            # 참고: Tag_Code T2(출근), T3(퇴근)이 이미 설정되어 있으므로, 
            # 더 정확한 출퇴근 시간대 검증만 추가
            
            # 0. M1/M2 태그 기반 식사 분류 (최우선) - 확정적 규칙 엔진 사용
            # M1: 바이오플라자 식사, M2: 테이크아웃
            if 'Tag_Code' in daily_data.columns:
                m1_mask = daily_data['Tag_Code'] == 'M1'
                m2_mask = daily_data['Tag_Code'] == 'M2'
                
                if m1_mask.any() or m2_mask.any():
                    self.logger.info(f"M1 태그 {m1_mask.sum()}건, M2 태그 {m2_mask.sum()}건 발견 - 확정적 규칙 엔진 적용")
                    
                    # M1/M2 태그가 있는 행의 정보 출력
                    for idx in daily_data[m1_mask | m2_mask].index[:5]:
                        self.logger.info(f"  - {daily_data.loc[idx, 'datetime']}: {daily_data.loc[idx, 'DR_NM']} (Tag_Code={daily_data.loc[idx, 'Tag_Code']})")
                    
                    # 확정적 규칙 엔진 가져오기
                    rule_integration = get_rule_integration()
                    
                    # M1/M2 태그에 대해 시간대별 식사 분류 및 duration 계산
                    for idx in daily_data[m1_mask | m2_mask].index:
                        hour = daily_data.loc[idx, 'datetime'].hour
                        minute = daily_data.loc[idx, 'datetime'].minute
                        time_in_minutes = hour * 60 + minute
                        
                        # 다음 태그까지의 시간 계산
                        idx_position = daily_data.index.get_loc(idx)
                        to_next_minutes = None
                        if idx_position + 1 < len(daily_data):
                            next_idx = daily_data.index[idx_position + 1]
                            time_diff = (daily_data.loc[next_idx, 'datetime'] - daily_data.loc[idx, 'datetime']).total_seconds() / 60
                            to_next_minutes = time_diff
                        
                        # 규칙 엔진을 통한 식사 시간 계산
                        meal_duration = rule_integration.get_meal_duration(
                            daily_data.loc[idx, 'Tag_Code'],
                            to_next_minutes
                        )
                        
                        # duration_minutes 설정 (activity_summary 계산에 사용됨)
                        daily_data.loc[idx, 'duration_minutes'] = meal_duration
                        self.logger.info(f"[M1/M2 duration 설정] idx={idx}, tag={daily_data.loc[idx, 'Tag_Code']}, "
                                        f"duration_minutes={meal_duration}, to_next_minutes={to_next_minutes}")
                        
                        # M1/M2 태그는 식사로 분류하지만 시간대별 activity_code는 설정하지 않음
                        # 태그 기반 시스템에서는 Tag_Code가 분류의 기준
                        daily_data.loc[idx, 'activity_code'] = 'MEAL'  # 일반 식사 활동
                        daily_data.loc[idx, '활동분류'] = '식사중'
                        
                        # M1/M2 태그 기반이므로 높은 신뢰도
                        daily_data.loc[idx, 'confidence'] = 100
                        daily_data.loc[idx, 'is_actual_meal'] = True
                        daily_data.loc[idx, 'activity_type'] = 'meal'
                        
                        # M2는 테이크아웃
                        if daily_data.loc[idx, 'Tag_Code'] == 'M2':
                            daily_data.loc[idx, 'is_takeout'] = True
                            self.logger.info(f"M2 테이크아웃 - {daily_data.loc[idx, 'datetime']}: {daily_data.loc[idx, 'activity_code']} (duration: {meal_duration}분)")
            
            # 1. 식사시간 분류 - 태그 기반 시스템에서는 M1/M2 태그만 식사로 분류
            # 실제 식사 데이터는 검증용으로만 사용하고, 태그를 변경하지 않음
            # 🚨 중요: 태그 기반 시스템에서는 마스터 데이터의 Tag_Code를 변경하지 않음
            meal_data = None
            if employee_id and selected_date:
                meal_data = self.get_meal_data(employee_id, selected_date)
            
            if meal_data is not None and not meal_data.empty:
                # 실제 식사 데이터는 로깅용으로만 사용
                self.logger.info(f"식사 데이터 {len(meal_data)}건 확인 (태그 변경 없음)")
                date_column = 'meal_datetime' if 'meal_datetime' in meal_data.columns else '취식일시'
                category_column = 'meal_category' if 'meal_category' in meal_data.columns else '식사대분류'
                
                if date_column in meal_data.columns:
                    meal_data[date_column] = pd.to_datetime(meal_data[date_column])
                    
                    # 각 식사별로 처리 - 🚨 태그 변경 로직 제거
                    for _, meal in meal_data.iterrows():
                        meal_time = meal[date_column]
                        meal_category = meal.get(category_column, '')
                        
                        # 해당 시간대 근처의 M1/M2 태그만 확인 (태그 변경 없음)
                        time_window = timedelta(minutes=15)
                        nearby_tags = daily_data[
                            (daily_data['datetime'] >= meal_time - time_window) &
                            (daily_data['datetime'] <= meal_time + time_window) &
                            (daily_data['Tag_Code'].isin(['M1', 'M2']))
                        ]
                        
                        if not nearby_tags.empty:
                            # M1/M2 태그가 있는 경우만 로깅 (태그 변경 없음)
                            self.logger.info(f"식사 시간 {meal_time}에 M1/M2 태그 {len(nearby_tags)}개 확인 (태그 변경 없음)")
                            
                            # 실제 식사 데이터와 M1/M2 태그의 매칭 정보만 로깅
                            for idx in nearby_tags.index:
                                tag_time = daily_data.loc[idx, 'datetime']
                                tag_code = daily_data.loc[idx, 'Tag_Code']
                                self.logger.info(f"  - {tag_time}: Tag_Code={tag_code}, 식사 종류={meal_category}")
            
            # 식사 태그 데이터가 없는 경우에는 식사로 분류하지 않음
            # 실제 식사 태그가 있는 경우에만 위에서 이미 처리됨
            
            # is_actual_meal 플래그 초기화 (식사 태그가 없는 경우 False)
            if 'is_actual_meal' not in daily_data.columns:
                daily_data['is_actual_meal'] = False
            
            # 식사 태그 중 위치명에 '테이크아웃'이 포함된 경우 is_takeout 설정
            meal_tag_mask = (daily_data['INOUT_GB'] == '식사')
            if meal_tag_mask.any():
                takeout_location_mask = meal_tag_mask & daily_data['DR_NM'].str.contains('테이크아웃', case=False, na=False)
                if takeout_location_mask.any():
                    daily_data.loc[takeout_location_mask, 'is_takeout'] = True
                    self.logger.info(f"위치명 기반 테이크아웃 설정: {takeout_location_mask.sum()}건")
            
            # 식사 활동의 신뢰도 조정
            meal_activity_codes = ['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL']
            meal_activity_mask = daily_data['activity_code'].isin(meal_activity_codes)
            if meal_activity_mask.any() and 'Tag_Code' in daily_data.columns:
                # 식사 활동이면서 Tag_Code가 G1인 경우만 95%로 상향 (나머지는 기존 유지)
                daily_data.loc[meal_activity_mask & (daily_data['Tag_Code'] == 'G1'), 'confidence'] = 95
            
            # 1.5. 장비 사용 데이터 반영
            if employee_id and selected_date:
                equipment_data = self.get_employee_equipment_data(employee_id, selected_date)
                if equipment_data is not None and not equipment_data.empty:
                    self.logger.info(f"장비 사용 데이터 {len(equipment_data)}건을 활동 분류에 반영합니다.")
                    
                    # 장비 사용 시간대의 태그를 EQUIPMENT_OPERATION으로 변경
                    for _, equip in equipment_data.iterrows():
                        equip_time = pd.to_datetime(equip['timestamp'])
                        system_type = equip.get('system_type', equip.get('system', ''))
                        
                        # 해당 시간대 근처의 태그 찾기 (±5분)
                        time_window = timedelta(minutes=5)
                        nearby_tags = daily_data[
                            (daily_data['datetime'] >= equip_time - time_window) &
                            (daily_data['datetime'] <= equip_time + time_window)
                        ]
                        
                        if not nearby_tags.empty:
                            # 가장 가까운 시간의 태그 찾기
                            time_diffs = abs(nearby_tags['datetime'] - equip_time)
                            closest_idx = time_diffs.idxmin()
                            
                            # 장비 조작으로 분류
                            daily_data.loc[closest_idx, 'activity_code'] = 'EQUIPMENT_OPERATION'
                            daily_data.loc[closest_idx, 'confidence'] = 98  # 실제 장비 사용 로그이므로 높은 신뢰도
                            daily_data.loc[closest_idx, 'equipment_type'] = system_type
                            
                            # 장비 사용 세션 확장 (전후 10분간 같은 위치에 있었다면)
                            session_start = equip_time - timedelta(minutes=10)
                            session_end = equip_time + timedelta(minutes=10)
                            session_mask = (
                                (daily_data['datetime'] >= session_start) &
                                (daily_data['datetime'] <= session_end) &
                                (daily_data['DR_NO'] == daily_data.loc[closest_idx, 'DR_NO']) &
                                (daily_data['activity_code'] == 'WORK')
                            )
                            daily_data.loc[session_mask, 'activity_code'] = 'EQUIPMENT_OPERATION'
                            daily_data.loc[session_mask, 'confidence'] = 95
                            daily_data.loc[session_mask, 'equipment_type'] = system_type
            
            # 2. 특수 활동 분류 (위치명 기반 세부 분류)
            # 회의실
            meeting_mask = daily_data['DR_NM'].str.contains('MEETING|회의|CONFERENCE', case=False, na=False)
            daily_data.loc[meeting_mask, 'activity_code'] = 'MEETING'
            # Tag_Code가 G3(협업공간)이 아닌 경우만 신뢰도 조정
            if 'Tag_Code' in daily_data.columns:
                daily_data.loc[meeting_mask & (daily_data['Tag_Code'] != 'G3'), 'confidence'] = 88
            
            # 피트니스/운동실
            fitness_mask = daily_data['DR_NM'].str.contains('FITNESS|GYM|체력단련|운동실', case=False, na=False)
            daily_data.loc[fitness_mask, 'activity_code'] = 'FITNESS'
            # Tag_Code가 N2(복지공간)이 아닌 경우만 신뢰도 조정
            if 'Tag_Code' in daily_data.columns:
                daily_data.loc[fitness_mask & (daily_data['Tag_Code'] != 'N2'), 'confidence'] = 87
            
            # 장비실/기계실
            equipment_mask = daily_data['DR_NM'].str.contains('EQUIPMENT|MACHINE|장비|기계실', case=False, na=False)
            daily_data.loc[equipment_mask & (daily_data['activity_code'] == 'WORK'), 'activity_code'] = 'EQUIPMENT_OPERATION'
            
            # 작업준비실
            prep_mask = daily_data['DR_NM'].str.contains('PREP|준비실|SETUP', case=False, na=False)
            daily_data.loc[prep_mask & (daily_data['activity_code'] == 'WORK'), 'activity_code'] = 'WORK_PREPARATION'
            
            # 휴게실
            rest_mask = daily_data['DR_NM'].str.contains('REST|LOUNGE|휴게실|탈의실', case=False, na=False)
            daily_data.loc[rest_mask, 'activity_code'] = 'REST'
            # Tag_Code가 N1(휴게공간)이 아닌 경우만 신뢰도 조정
            if 'Tag_Code' in daily_data.columns:
                daily_data.loc[rest_mask & (daily_data['Tag_Code'] != 'N1'), 'confidence'] = 86
            
            # 3. 집중근무 판별 (같은 작업 위치에 30분 이상 체류)
            # 체류시간 계산 (M1/M2 태그는 위에서 이미 계산됨)
            # M1/M2 태그와 Knox PIMS의 duration을 먼저 백업
            if 'Tag_Code' in daily_data.columns:
                m1_m2_mask = daily_data['Tag_Code'].isin(['M1', 'M2'])
                m1_m2_durations = daily_data.loc[m1_m2_mask, 'duration_minutes'].copy() if 'duration_minutes' in daily_data.columns and m1_m2_mask.any() else pd.Series()
            
            # Knox PIMS duration 백업
            knox_pims_mask = pd.Series([False] * len(daily_data))
            knox_durations = pd.Series(dtype='float64')
            if 'source' in daily_data.columns:
                knox_pims_mask = daily_data['source'] == 'knox_pims'
                if knox_pims_mask.any() and 'knox_duration' in daily_data.columns:
                    knox_durations = daily_data.loc[knox_pims_mask, 'knox_duration'].copy()
            
            daily_data['next_time'] = daily_data['datetime'].shift(-1)
            daily_data['duration_minutes'] = (daily_data['next_time'] - daily_data['datetime']).dt.total_seconds() / 60
            
            # 🔍 Duration 계산 디버깅 (첫 번째 계산)
            for idx in daily_data.index:
                if '탕맛기픈' in str(daily_data.loc[idx, 'DR_NM']):
                    self.logger.info(f"🔍 [1차 계산] 탕맛기픈 duration: {daily_data.loc[idx, 'datetime']} → {daily_data.loc[idx, 'duration_minutes']:.1f}분")
            
            # NaN 값 처리
            daily_data['duration_minutes'] = daily_data['duration_minutes'].fillna(5)  # 기본값 5분
            
            # 마지막 레코드는 5분으로 가정
            if len(daily_data) > 0:
                daily_data.loc[daily_data.index[-1], 'duration_minutes'] = 5
            
            # M1/M2 태그의 duration 복원
            if 'Tag_Code' in daily_data.columns and m1_m2_mask.any() and not m1_m2_durations.empty:
                daily_data.loc[m1_m2_mask, 'duration_minutes'] = m1_m2_durations
                self.logger.info(f"[첫 번째 duration 계산] M1/M2 태그 duration 복원: {m1_m2_mask.sum()}건")
            
            # Knox PIMS duration 복원
            if knox_pims_mask.any() and not knox_durations.empty:
                daily_data.loc[knox_pims_mask, 'duration_minutes'] = knox_durations
                self.logger.info(f"[첫 번째 duration 계산] Knox PIMS duration 복원: {knox_pims_mask.sum()}건")
            
            # O 태그 (장비 사용)의 체류시간 설정
            o_tag_indices = daily_data[daily_data['INOUT_GB'] == 'O'].index
            for idx in o_tag_indices:
                # 장비 사용은 기본적으로 10분으로 설정
                daily_data.loc[idx, 'duration_minutes'] = 10
                # 다음 태그까지의 시간이 30분 이내면 그 시간으로 조정
                if idx < len(daily_data) - 1:
                    next_idx = daily_data.index[daily_data.index.get_loc(idx) + 1]
                    time_to_next = (daily_data.loc[next_idx, 'datetime'] - daily_data.loc[idx, 'datetime']).total_seconds() / 60
                    if time_to_next < 30:
                        daily_data.loc[idx, 'duration_minutes'] = time_to_next
            
            # 식사 태그 전후 처리 - 식사 전까지의 작업 시간 조정
            meal_activities = ['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL']
            for idx in daily_data.index:
                if daily_data.loc[idx, 'activity_code'] in meal_activities:
                    # 이전 레코드가 작업 활동인 경우
                    if idx > 0:
                        prev_idx = daily_data.index[daily_data.index.get_loc(idx) - 1]
                        if daily_data.loc[prev_idx, 'activity_code'] in ['WORK', 'FOCUSED_WORK', 'EQUIPMENT_OPERATION']:
                            # 식사 시작 시간을 이전 활동의 종료 시간으로 설정
                            meal_start = daily_data.loc[idx, 'datetime']
                            daily_data.loc[prev_idx, 'next_time'] = meal_start
                            # duration 재계산
                            duration = (meal_start - daily_data.loc[prev_idx, 'datetime']).total_seconds() / 60
                            daily_data.loc[prev_idx, 'duration_minutes'] = duration
                    
                    # 식사 태그에 meal_location 정보 반영
                    if daily_data.loc[idx, 'is_actual_meal']:
                        # meal_location이 있으면 무조건 사용 (배식구 정보가 여기에 들어있음)
                        if 'meal_location' in daily_data.columns and pd.notna(daily_data.loc[idx, 'meal_location']):
                            daily_data.loc[idx, 'DR_NM'] = daily_data.loc[idx, 'meal_location']
                        # meal_location이 없는 경우에만 기본값 사용
                        elif not ('BP' in str(daily_data.loc[idx, 'DR_NM']) or '식당' in str(daily_data.loc[idx, 'DR_NM']) or 'CAFETERIA' in str(daily_data.loc[idx, 'DR_NM'])):
                            daily_data.loc[idx, 'DR_NM'] = 'BP_CAFETERIA'
                        
                        # 🚨 가상 MOVEMENT_TO_BP 태그 생성 중단 - 불필요한 이동시간 추가 방지
                        # BP로 이동하는 가상 태그 추가 (식사 5분 전) - DISABLED
                        # if idx > 0:
                        #     move_to_bp_time = daily_data.loc[idx, 'datetime'] - timedelta(minutes=5)
                        #     # 새로운 이동 레코드 생성
                        #     move_record = daily_data.loc[idx].copy()
                        #     move_record['datetime'] = move_to_bp_time
                        #     move_record['activity_code'] = 'MOVEMENT'
                        #     move_record['DR_NM'] = 'MOVEMENT_TO_BP'
                        #     move_record['duration_minutes'] = 5
                        #     move_record['is_actual_meal'] = False
                        #     move_record['confidence'] = 85
                            
                            # # DataFrame에 추가 (나중에 정렬 필요) - DISABLED
                            # daily_data = pd.concat([daily_data, pd.DataFrame([move_record])], ignore_index=True)
            
            # 시간순 재정렬
            daily_data = daily_data.sort_values('datetime').reset_index(drop=True)
            
            # duration_minutes 재계산 (M1/M2 태그와 Knox PIMS는 제외)
            # M1/M2 태그의 duration을 먼저 백업
            m1_m2_mask = daily_data['Tag_Code'].isin(['M1', 'M2'])
            m1_m2_durations = daily_data.loc[m1_m2_mask, 'duration_minutes'].copy()
            
            # Knox PIMS duration 백업
            knox_pims_mask = pd.Series([False] * len(daily_data))
            knox_durations = pd.Series(dtype='float64')
            if 'source' in daily_data.columns:
                knox_pims_mask = daily_data['source'] == 'knox_pims'
                knox_durations = daily_data.loc[knox_pims_mask, 'duration_minutes'].copy() if knox_pims_mask.any() else pd.Series(dtype='float64')
            
            daily_data['next_time'] = daily_data['datetime'].shift(-1)
            daily_data['duration_minutes'] = (daily_data['next_time'] - daily_data['datetime']).dt.total_seconds() / 60
            daily_data['duration_minutes'] = daily_data['duration_minutes'].fillna(5)
            
            # 🔍 Duration 계산 디버깅 (두 번째 계산)
            for idx in daily_data.index:
                if '탕맛기픈' in str(daily_data.loc[idx, 'DR_NM']):
                    self.logger.info(f"🔍 [2차 계산] 탕맛기픈 duration: {daily_data.loc[idx, 'datetime']} → {daily_data.loc[idx, 'duration_minutes']:.1f}분")
            
            # M1/M2 태그의 duration 복원
            if m1_m2_mask.any():
                daily_data.loc[m1_m2_mask, 'duration_minutes'] = m1_m2_durations
                self.logger.info(f"M1/M2 태그 duration 복원: {m1_m2_mask.sum()}건")
            
            # Knox PIMS duration 복원
            if knox_pims_mask.any() and not knox_durations.empty:
                daily_data.loc[knox_pims_mask, 'duration_minutes'] = knox_durations
                self.logger.info(f"Knox PIMS duration 복원: {knox_pims_mask.sum()}건")
            
            # 같은 위치에서 30분 이상 작업한 경우 집중근무로 분류
            focused_work_mask = (
                (daily_data['activity_code'] == 'WORK') & 
                (daily_data['duration_minutes'] >= 30) &
                (daily_data['DR_NM'].str.contains('WORK_AREA', case=False, na=False))
            )
            daily_data.loc[focused_work_mask, 'activity_code'] = 'FOCUSED_WORK'
            # 집중근무는 추론 기반이므로 약간 낮은 신뢰도
            daily_data.loc[focused_work_mask & (daily_data['confidence'] > 85), 'confidence'] = 83
            
            # 4. 꼬리물기 현상 처리
            # 작업 중 동료와 함께 게이트를 나간 후 식사하는 경우
            meal_indices = daily_data[daily_data['activity_code'].isin(['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL'])].index
            
            for meal_idx in meal_indices:
                if meal_idx > 0:
                    meal_time = daily_data.loc[meal_idx, 'datetime']
                    # 식사 30분 전부터 확인
                    time_window_start = meal_time - timedelta(minutes=30)
                    
                    # 해당 시간 범위의 레코드들
                    window_mask = (daily_data['datetime'] >= time_window_start) & (daily_data['datetime'] < meal_time)
                    window_data = daily_data[window_mask]
                    
                    # GATE_OUT이 있는지 확인
                    if not window_data.empty and 'INOUT_GB' in window_data.columns and window_data['INOUT_GB'].eq('T3').any():
                        # 출문 이후 첫 식사까지를 비근무로 처리
                        gate_out_idx = window_data[window_data['INOUT_GB'] == 'T3'].index[-1]
                        
                        # 출문부터 식사 직전까지 비근무로 표시
                        mask = (daily_data.index >= gate_out_idx) & (daily_data.index < meal_idx)
                        daily_data.loc[mask, 'activity_code'] = 'NON_WORK'
                        if 'is_tailgating' not in daily_data.columns:
                            daily_data['is_tailgating'] = False
                        daily_data.loc[mask, 'is_tailgating'] = True
            
            # 5. 활동 타입 매핑 (이전 버전과의 호환성)
            activity_type_mapping = {
                'WORK': 'work',
                'FOCUSED_WORK': 'work',
                'EQUIPMENT_OPERATION': 'work',
                'WORK_PREPARATION': 'work',
                'WORKING': 'work',
                'TRAINING': 'education',
                'MEETING': 'meeting',
                'G3_MEETING': 'meeting',  # Knox PIMS 회의 추가
                'MOVEMENT': 'movement',
                'COMMUTE_IN': 'commute',
                'COMMUTE_OUT': 'commute',
                'BREAKFAST': 'meal',
                'LUNCH': 'meal',
                'DINNER': 'meal',
                'MIDNIGHT_MEAL': 'meal',
                'REST': 'rest',
                'FITNESS': 'rest',
                'LEAVE': 'rest',
                'IDLE': 'rest',
                'NON_WORK': 'non_work',
                'UNKNOWN': 'work'
            }
            # Knox PIMS 보호된 항목의 activity_type은 건드리지 않음
            if 'is_knox_pims_protected' in daily_data.columns:
                non_protected_mask = ~daily_data['is_knox_pims_protected'].fillna(False)
                daily_data.loc[non_protected_mask, 'activity_type'] = daily_data.loc[non_protected_mask, 'activity_code'].map(activity_type_mapping).fillna('work')
            else:
                daily_data['activity_type'] = daily_data['activity_code'].map(activity_type_mapping).fillna('work')
            
            # 출문-재입문 패턴 감지 및 분류
            if 'Tag_Code' in daily_data.columns:
                # 출문(T3) - 재입문(T2) 패턴 찾기
                for i in range(1, len(daily_data)):
                    if (daily_data.iloc[i-1]['Tag_Code'] == 'T3' and 
                        daily_data.iloc[i]['Tag_Code'] == 'T2'):
                        
                        # 시간 차이 계산
                        time_diff = (daily_data.iloc[i]['datetime'] - 
                                   daily_data.iloc[i-1]['datetime']).total_seconds() / 3600
                        
                        exit_time = daily_data.iloc[i-1]['datetime'].time()
                        entry_time = daily_data.iloc[i]['datetime'].time()
                        
                        # 출문과 재입문 사이의 시간 분류 (태그 기반 시스템에서는 시간대 기반 식사 분류 제거)
                        if 0 < time_diff < 3:  # 3시간 이내의 외출
                            # 모든 단시간 외출은 비근무로 분류 (식사는 M1/M2 태그로만 분류)
                            daily_data.loc[daily_data.index[i-1]:daily_data.index[i], 'activity_code'] = 'NON_WORK'
                            daily_data.loc[daily_data.index[i-1]:daily_data.index[i], 'confidence'] = 90
                            daily_data.loc[daily_data.index[i-1]:daily_data.index[i], 'activity_type'] = 'non_work'
                            self.logger.info(f"외출: {exit_time} - {entry_time} ({time_diff:.1f}시간)")
                        else:
                            # 3시간 이상의 장시간 외출 -> 비근무
                            daily_data.loc[daily_data.index[i-1]:daily_data.index[i], 'activity_code'] = 'NON_WORK'
                            daily_data.loc[daily_data.index[i-1]:daily_data.index[i], 'confidence'] = 95
                            daily_data.loc[daily_data.index[i-1]:daily_data.index[i], 'activity_type'] = 'non_work'
                            self.logger.info(f"장시간 비근무: {exit_time} - {entry_time} ({time_diff:.1f}시간)")
            
            # 비근무지역에서 일정시간 이상 체류 시 비근무로 분류
            if 'work_area_type' in daily_data.columns:
                # 비근무지역(N) 태그를 그룹화
                daily_data['group_id'] = (daily_data['work_area_type'] != daily_data['work_area_type'].shift()).cumsum()
                
                for group_id, group in daily_data.groupby('group_id'):
                    if len(group) > 0 and group.iloc[0]['work_area_type'] == 'N':
                        # 그룹의 첫번째와 마지막 시간 차이 계산
                        if len(group) > 1:
                            duration = (group.iloc[-1]['datetime'] - group.iloc[0]['datetime']).total_seconds() / 60
                        else:
                            # 다음 태그까지의 시간 확인
                            next_idx = group.index[-1] + 1
                            if next_idx < len(daily_data):
                                duration = (daily_data.iloc[next_idx]['datetime'] - group.iloc[0]['datetime']).total_seconds() / 60
                            else:
                                duration = 5  # 기본값
                        
                        # 10분 이상 비근무지역에 체류한 경우 비근무로 분류
                        if duration >= 10:
                            daily_data.loc[group.index, 'activity_code'] = 'NON_WORK'
                            daily_data.loc[group.index, 'confidence'] = 85
                            daily_data.loc[group.index, 'activity_type'] = 'non_work'
                            self.logger.info(f"비근무지역 체류: {group.iloc[0]['datetime']} ({duration:.0f}분)")
                
                # 임시 컬럼 제거
                daily_data.drop('group_id', axis=1, inplace=True)
            
            # 마지막으로 한 번 더 식사 전후 출입문 처리 (HMM이 덮어쓴 경우 대비)
            self.logger.info("최종 식사 전후 출입문 처리 시작")
            
            # 1. 모든 출입문 태그 중 식사로 잘못 분류된 것 찾기
            entry_exit_mask = daily_data['INOUT_GB'].isin(['입문', '출문'])
            meal_activity_mask = daily_data['activity_code'].isin(['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL'])
            wrong_classification = entry_exit_mask & meal_activity_mask
            
            if wrong_classification.any():
                self.logger.info(f"잘못 분류된 출입문 {wrong_classification.sum()}개 발견")
                # 출입문은 절대 식사가 아님
                daily_data.loc[wrong_classification & (daily_data['INOUT_GB'] == '출문'), 'activity_code'] = 'MOVEMENT'
                daily_data.loc[wrong_classification & (daily_data['INOUT_GB'] == '출문'), 'activity_type'] = 'movement'
                
                # 입문의 경우, 이미 COMMUTE_IN으로 분류된 것을 보존하기 위해 추가 체크
                entry_mask = wrong_classification & (daily_data['INOUT_GB'] == '입문')
                for idx in daily_data[entry_mask].index:
                    # 근무 유형에 따라 출근 시간대 다르게 판단
                    hour = daily_data.loc[idx, 'datetime'].hour
                    dr_nm = daily_data.loc[idx, 'DR_NM']
                    is_gate = 'SPEED GATE' in str(dr_nm).upper() or '정문' in str(dr_nm)
                    
                    if is_gate:
                        if work_type == 'night_shift' and 17 <= hour <= 22:
                            # 야간 근무자의 저녁 출근
                            daily_data.loc[idx, 'activity_code'] = 'COMMUTE_IN'
                            daily_data.loc[idx, 'activity_type'] = 'commute'
                            self.logger.info(f"야간 출근 시간대 게이트 입문: {daily_data.loc[idx, 'datetime']} - {dr_nm}")
                        elif work_type != 'night_shift' and 5 <= hour < 10:
                            # 일반 근무자의 아침 출근
                            daily_data.loc[idx, 'activity_code'] = 'COMMUTE_IN'
                            daily_data.loc[idx, 'activity_type'] = 'commute'
                            self.logger.info(f"일반 출근 시간대 게이트 입문: {daily_data.loc[idx, 'datetime']} - {dr_nm}")
                        else:
                            daily_data.loc[idx, 'activity_code'] = 'WORK'
                            daily_data.loc[idx, 'activity_type'] = 'work'
                    else:
                        daily_data.loc[idx, 'activity_code'] = 'WORK'
                        daily_data.loc[idx, 'activity_type'] = 'work'
                
                daily_data.loc[wrong_classification, 'confidence'] = 100
            
            # 2. 추가로 정문/스피드게이트 입문이 조식으로 분류된 모든 케이스 확인
            gate_entry_mask = daily_data['INOUT_GB'] == '입문'
            gate_name_mask = daily_data['DR_NM'].str.contains('정문|SPEED GATE', case=False, na=False)
            
            # 근무 유형에 따라 출근 시간대 다르게 설정
            if work_type == 'night_shift':
                # 야간 근무자는 저녁 시간대를 출근으로
                commute_time_mask = daily_data['datetime'].dt.hour.between(17, 22)
            else:
                # 일반 근무자는 아침 시간대를 출근으로
                commute_time_mask = daily_data['datetime'].dt.hour.between(5, 10)
                
            gate_commute_entry = gate_entry_mask & gate_name_mask & commute_time_mask
            
            # 식사로 잘못 분류된 정문 입문 수정
            meal_gate_entries = gate_commute_entry & (daily_data['activity_code'].isin(['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL']))
            if meal_gate_entries.any():
                self.logger.info(f"식사로 잘못 분류된 정문 입문 {meal_gate_entries.sum()}개 발견 및 수정 (근무유형: {work_type})")
                daily_data.loc[meal_gate_entries, 'activity_code'] = 'COMMUTE_IN'
                daily_data.loc[meal_gate_entries, 'activity_type'] = 'commute'
                daily_data.loc[meal_gate_entries, 'confidence'] = 100
                
                # 로그 출력
                for idx in daily_data[meal_gate_entries].index:
                    self.logger.info(f"  - {daily_data.loc[idx, 'datetime']} at {daily_data.loc[idx, 'DR_NM']} : {daily_data.loc[idx, 'activity_code']} -> COMMUTE_IN")
            
            # 테이크아웃 정보 최종 확인 및 로깅
            if 'is_takeout' in daily_data.columns:
                takeout_meals = daily_data[(daily_data['INOUT_GB'] == '식사') & (daily_data['is_takeout'] == True)]
                if not takeout_meals.empty:
                    self.logger.info(f"테이크아웃 식사 {len(takeout_meals)}개 확인:")
                    for idx, row in takeout_meals.iterrows():
                        self.logger.info(f"  - {row['datetime']}: {row['DR_NM']}, activity={row['activity_code']}, is_takeout={row['is_takeout']}")
            
            # 최종 리턴 전에 한 번 더 정문 입문 체크
            if work_type == 'night_shift':
                # 야간 근무자는 저녁 시간대 체크
                final_check = daily_data[
                    (daily_data['INOUT_GB'] == '입문') & 
                    (daily_data['DR_NM'].str.contains('정문|SPEED GATE', case=False, na=False)) &
                    (daily_data['datetime'].dt.hour.between(17, 22)) &
                    (daily_data['activity_code'].isin(['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL']))
                ]
            else:
                # 일반 근무자는 아침 시간대 체크
                final_check = daily_data[
                    (daily_data['INOUT_GB'] == '입문') & 
                    (daily_data['DR_NM'].str.contains('정문|SPEED GATE', case=False, na=False)) &
                    (daily_data['datetime'].dt.hour.between(5, 10)) &
                    (daily_data['activity_code'].isin(['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL']))
                ]
            
            if not final_check.empty:
                self.logger.warning(f"최종 체크: 식사로 분류된 정문 입문 {len(final_check)}개 발견! (근무유형: {work_type})")
                daily_data.loc[final_check.index, 'activity_code'] = 'COMMUTE_IN'
                daily_data.loc[final_check.index, 'confidence'] = 100
                daily_data.loc[final_check.index, 'activity_type'] = 'commute'
                
                for idx in final_check.index:
                    self.logger.warning(f"  최종 수정: {daily_data.loc[idx, 'datetime']} - {daily_data.loc[idx, 'DR_NM']} : {daily_data.loc[idx, 'activity_code']} -> COMMUTE_IN")
            
            # 최종적으로 activity_type이 비어있는 경우 재매핑
            activity_type_mapping = {
                'WORK': 'work',
                'FOCUSED_WORK': 'work',
                'EQUIPMENT_OPERATION': 'work',
                'WORK_PREPARATION': 'work',
                'WORKING': 'work',
                'TRAINING': 'education',
                'MEETING': 'meeting',
                'G3_MEETING': 'meeting',  # Knox PIMS 회의 추가
                'MOVEMENT': 'movement',
                'COMMUTE_IN': 'commute',
                'COMMUTE_OUT': 'commute',
                'BREAKFAST': 'meal',
                'LUNCH': 'meal',
                'DINNER': 'meal',
                'MIDNIGHT_MEAL': 'meal',
                'REST': 'rest',
                'FITNESS': 'rest',
                'LEAVE': 'rest',
                'IDLE': 'rest',
                'NON_WORK': 'non_work',
                'UNKNOWN': 'work'
            }
            
            # activity_type이 비어있거나 None인 경우 재매핑
            empty_type_mask = daily_data['activity_type'].isna() | (daily_data['activity_type'] == '')
            if empty_type_mask.any():
                self.logger.info(f"activity_type이 비어있는 {empty_type_mask.sum()}개 발견, 재매핑 수행")
                daily_data.loc[empty_type_mask, 'activity_type'] = daily_data.loc[empty_type_mask, 'activity_code'].map(activity_type_mapping).fillna('work')
            
            # 최종 Tag_Code 기반 보호 (HMM이나 다른 로직이 덮어쓴 것을 복구)
            if 'Tag_Code' in daily_data.columns:
                # T2 태그 (출입포인트 IN) 보호 - 모든 T2는 출근
                t2_mask = daily_data['Tag_Code'] == 'T2'
                if t2_mask.any():
                    t2_wrong = t2_mask & (~daily_data['activity_code'].isin(['COMMUTE_IN']))
                    if t2_wrong.any():
                        self.logger.warning(f"최종 보호: T2 태그 {t2_wrong.sum()}건을 COMMUTE_IN으로 수정")
                        for idx in daily_data[t2_wrong].index:
                            prev_code = daily_data.loc[idx, 'activity_code']
                            daily_data.loc[idx, 'activity_code'] = 'COMMUTE_IN'
                            daily_data.loc[idx, 'activity_type'] = 'commute'
                            daily_data.loc[idx, 'confidence'] = 100
                            self.logger.info(f"  - {daily_data.loc[idx, 'datetime']}: {prev_code} -> COMMUTE_IN at {daily_data.loc[idx, 'DR_NM']}")
                
                # T3 태그 (출입포인트 OUT) 보호 - 모든 T3는 퇴근
                t3_mask = daily_data['Tag_Code'] == 'T3'
                if t3_mask.any():
                    t3_wrong = t3_mask & (~daily_data['activity_code'].isin(['COMMUTE_OUT']))
                    if t3_wrong.any():
                        self.logger.warning(f"최종 보호: T3 태그 {t3_wrong.sum()}건을 COMMUTE_OUT으로 수정")
                        for idx in daily_data[t3_wrong].index:
                            prev_code = daily_data.loc[idx, 'activity_code']
                            daily_data.loc[idx, 'activity_code'] = 'COMMUTE_OUT'
                            daily_data.loc[idx, 'activity_type'] = 'commute'
                            daily_data.loc[idx, 'confidence'] = 100
                            self.logger.info(f"  - {daily_data.loc[idx, 'datetime']}: {prev_code} -> COMMUTE_OUT at {daily_data.loc[idx, 'DR_NM']}")
            
            # 701-10-1-1 특별 확인
            if '701-10-1-1' in daily_data['DR_NO'].values:
                test_rows = daily_data[daily_data['DR_NO'] == '701-10-1-1']
                for idx, row in test_rows.iterrows():
                    self.logger.info(f"701-10-1-1 최종 상태: {row['datetime']} Tag_Code={row.get('Tag_Code', 'None')} activity={row['activity_code']}")
            
            return daily_data
            
        except Exception as e:
            self.logger.error(f"활동 분류 실패: {e}")
            # 오류 시에도 기본값 설정
            if 'activity_code' not in daily_data.columns:
                daily_data['activity_code'] = 'WORK'
            if 'activity_type' not in daily_data.columns:
                # activity_type_mapping 정의
                activity_type_mapping = {
                    'WORK': 'work',
                    'FOCUSED_WORK': 'work',
                    'EQUIPMENT_OPERATION': 'work',
                    'WORK_PREPARATION': 'work',
                    'WORKING': 'work',
                    'MEETING': 'meeting',
                    'BREAKFAST': 'meal',
                    'LUNCH': 'meal',
                    'DINNER': 'meal',
                    'MIDNIGHT_MEAL': 'meal',
                    'BREAK': 'rest',
                    'MOVEMENT': 'movement',
                    'COMMUTE_IN': 'commute',
                    'COMMUTE_OUT': 'commute',
                    'LEAVE': 'rest',
                    'IDLE': 'rest',
                    'NON_WORK': 'non_work',
                    'UNKNOWN': 'work'
                }
                # activity_code가 있으면 매핑
                if 'activity_code' in daily_data.columns:
                    # Knox PIMS 보호된 항목의 activity_type은 건드리지 않음
                    if 'is_knox_pims_protected' in daily_data.columns:
                        non_protected_mask = ~daily_data['is_knox_pims_protected'].fillna(False)
                        daily_data.loc[non_protected_mask, 'activity_type'] = daily_data.loc[non_protected_mask, 'activity_code'].map(activity_type_mapping).fillna('work')
                    else:
                        daily_data['activity_type'] = daily_data['activity_code'].map(activity_type_mapping).fillna('work')
                else:
                    daily_data['activity_type'] = 'work'
            if 'duration_minutes' not in daily_data.columns:
                daily_data['duration_minutes'] = 5
            if 'confidence' not in daily_data.columns:
                daily_data['confidence'] = 80
                
            # 분류 완료 후 Tag_Code 재확인
            if 'Tag_Code' in daily_data.columns:
                t2_count = (daily_data['Tag_Code'] == 'T2').sum()
                t3_count = (daily_data['Tag_Code'] == 'T3').sum()
                self.logger.info(f"최종 분류 결과: T2={t2_count}개, T3={t3_count}개")
                
                # T2 태그 확인
                t2_data = daily_data[daily_data['Tag_Code'] == 'T2']
                if not t2_data.empty:
                    for idx, row in t2_data.head().iterrows():
                        self.logger.info(f"T2 태그: {row['datetime']} - {row['DR_NM']}, activity={row['activity_code']}")
                        
                # 701-10-1-1 게이트 확인
                gate_701 = daily_data[daily_data['DR_NO'] == '701-10-1-1']
                if not gate_701.empty:
                    self.logger.info(f"701-10-1-1 게이트 {len(gate_701)}건:")
                    for idx, row in gate_701.head().iterrows():
                        self.logger.info(f"  - {row['datetime']}: Tag_Code={row.get('Tag_Code', 'N/A')}, activity={row['activity_code']}, work_area_type={row.get('work_area_type', 'N/A')}")
            
            # 최종 Knox PIMS 보호 - 마지막에 한번 더 확인
            if 'is_knox_pims_protected' in daily_data.columns:
                knox_protected_mask = daily_data['is_knox_pims_protected'].fillna(False)
                if knox_protected_mask.any():
                    # Knox PIMS 항목이 G3_MEETING이 아닌 경우 복원
                    wrong_activity_mask = knox_protected_mask & (daily_data['activity_code'] != 'G3_MEETING')
                    if wrong_activity_mask.any():
                        daily_data.loc[wrong_activity_mask, 'activity_code'] = 'G3_MEETING'
                        daily_data.loc[wrong_activity_mask, 'activity_type'] = 'meeting'
                        daily_data.loc[wrong_activity_mask, '활동분류'] = 'G3회의'
                        self.logger.warning(f"Knox PIMS {wrong_activity_mask.sum()}건이 잘못 변경되어 복원됨")
                    
                    # Knox PIMS duration 최종 확인
                    knox_with_duration = knox_protected_mask & daily_data['knox_duration'].notna()
                    if knox_with_duration.any():
                        daily_data.loc[knox_with_duration, 'duration_minutes'] = daily_data.loc[knox_with_duration, 'knox_duration']
                        
                    # 최종 상태 로그 - 더 상세하게
                    for idx in daily_data[knox_protected_mask].index:
                        row = daily_data.loc[idx]
                        self.logger.info(f"Knox PIMS 최종 상태 [{idx}]: {row['datetime']} - activity_code={row['activity_code']}, duration={row.get('duration_minutes', 'N/A')}분, knox_duration={row.get('knox_duration', 'N/A')}, is_protected={row.get('is_knox_pims_protected', False)}")
                        
            return daily_data
    
    def _apply_rule_based_classification(self, daily_data: pd.DataFrame, tag_location_master: pd.DataFrame) -> pd.DataFrame:
        """
        규칙 기반 활동 분류 (HMM 실패 시 폴백)
        """
        # 기존 규칙 기반 로직을 여기에 구현
        # 현재 코드에서는 이미 기본값이 설정되어 있으므로
        # 추가적인 규칙 기반 분류는 필요시 구현
        return daily_data
    
    def _apply_tag_based_rules(self, daily_data: pd.DataFrame, tag_location_master: pd.DataFrame) -> pd.DataFrame:
        """
        태그 기반 규칙 적용
        참조: /Users/hanskim/Project/SambioHR2/태그 기반 근무유형 분석 시스템 - 참조 문서.md
        """
        self.logger.info("태그 기반 규칙 적용 시작")
        
        # 1. T2 태그는 항상 COMMUTE_IN (출입(IN))
        t2_mask = daily_data['Tag_Code'] == 'T2'
        if t2_mask.any():
            activity_type = get_activity_type('COMMUTE_IN')
            daily_data.loc[t2_mask, 'activity_code'] = 'COMMUTE_IN'
            daily_data.loc[t2_mask, 'activity_type'] = 'commute'  # activity_type.category가 아니라 직접 'commute' 설정
            daily_data.loc[t2_mask, '활동분류'] = '출근'
            daily_data.loc[t2_mask, 'confidence'] = 100
            daily_data.loc[t2_mask, 'activity_label'] = ''  # YW 대신 빈 문자열로 설정
            self.logger.info(f"T2 태그 {t2_mask.sum()}개를 COMMUTE_IN으로 설정")
            
            # 디버깅: T2 태그 처리 결과 확인
            for idx in daily_data[t2_mask].index[:3]:  # 처음 3개만
                self.logger.info(f"  - {daily_data.loc[idx, 'datetime']}: activity_code={daily_data.loc[idx, 'activity_code']}, activity_type={daily_data.loc[idx, 'activity_type']}")
        
        # 2. T3 태그는 항상 COMMUTE_OUT (출입(OUT))
        t3_mask = daily_data['Tag_Code'] == 'T3'
        if t3_mask.any():
            daily_data.loc[t3_mask, 'activity_code'] = 'COMMUTE_OUT'
            daily_data.loc[t3_mask, 'activity_type'] = 'commute'  # 직접 설정
            daily_data.loc[t3_mask, '활동분류'] = '퇴근'
            daily_data.loc[t3_mask, 'confidence'] = 100
            self.logger.info(f"T3 태그 {t3_mask.sum()}개를 COMMUTE_OUT으로 설정")
        
        # 3. O 태그 (실제 업무 수행 로그) 처리
        o_mask = daily_data['Tag_Code'] == 'O'
        if o_mask.any():
            activity_type = get_activity_type('WORK')
            daily_data.loc[o_mask, 'activity_code'] = 'WORK'
            daily_data.loc[o_mask, 'activity_type'] = activity_type.category if activity_type else 'work'
            daily_data.loc[o_mask, '활동분류'] = activity_type.name_ko if activity_type else '작업'
            daily_data.loc[o_mask, 'confidence'] = 98
            self.logger.info(f"O 태그 {o_mask.sum()}개를 WORK로 설정")
        
        # 4. G1 태그 (주업무공간) 처리
        g1_mask = daily_data['Tag_Code'] == 'G1'
        if g1_mask.any():
            activity_type = get_activity_type('WORK')
            daily_data.loc[g1_mask, 'activity_code'] = 'WORK'
            daily_data.loc[g1_mask, 'activity_type'] = activity_type.category if activity_type else 'work'
            daily_data.loc[g1_mask, '활동분류'] = activity_type.name_ko if activity_type else '작업'
            daily_data.loc[g1_mask, 'confidence'] = 85
            self.logger.info(f"G1 태그 {g1_mask.sum()}개를 WORK로 설정")
        
        # 5. G2 태그 (준비공간) 처리
        g2_mask = daily_data['Tag_Code'] == 'G2'
        if g2_mask.any():
            activity_type = get_activity_type('WORK_PREPARATION')
            daily_data.loc[g2_mask, 'activity_code'] = 'WORK_PREPARATION'
            daily_data.loc[g2_mask, 'activity_type'] = activity_type.category if activity_type else 'work'
            daily_data.loc[g2_mask, '활동분류'] = activity_type.name_ko if activity_type else '준비'
            daily_data.loc[g2_mask, 'confidence'] = 90
            self.logger.info(f"G2 태그 {g2_mask.sum()}개를 WORK_PREPARATION으로 설정")
        
        # 6. G3 태그 (회의공간) 처리
        g3_mask = daily_data['Tag_Code'] == 'G3'
        if g3_mask.any():
            # Knox PIMS G3 태그는 G3_MEETING 유지
            if 'source' in daily_data.columns:
                knox_pims_mask = g3_mask & (daily_data['source'] == 'knox_pims')
                regular_g3_mask = g3_mask & (daily_data['source'] != 'knox_pims')
            else:
                knox_pims_mask = pd.Series([False] * len(daily_data))
                regular_g3_mask = g3_mask
            
            # Knox PIMS G3 태그 처리
            if knox_pims_mask.any():
                self.logger.info(f"[_apply_tag_based_rules] Knox PIMS G3 태그 처리 시작: {knox_pims_mask.sum()}개")
                activity_type = get_activity_type('G3_MEETING')
                if activity_type:
                    daily_data.loc[knox_pims_mask, 'activity_code'] = 'G3_MEETING'
                    daily_data.loc[knox_pims_mask, 'activity_type'] = 'meeting'
                    daily_data.loc[knox_pims_mask, '활동분류'] = activity_type.name_ko
                    self.logger.info(f"Knox PIMS activity_type 사용: {activity_type.name_ko}")
                else:
                    # get_activity_type이 None을 반환한 경우 기본값 사용
                    daily_data.loc[knox_pims_mask, 'activity_code'] = 'G3_MEETING'
                    daily_data.loc[knox_pims_mask, 'activity_type'] = 'meeting'
                    daily_data.loc[knox_pims_mask, '활동분류'] = 'G3회의'
                    self.logger.info(f"Knox PIMS 기본값 사용: G3회의")
                daily_data.loc[knox_pims_mask, 'confidence'] = 100
                # 보호 플래그 추가 - Knox PIMS 데이터가 나중에 변경되지 않도록
                daily_data.loc[knox_pims_mask, 'is_knox_pims_protected'] = True
                self.logger.info(f"Knox PIMS G3 태그 {knox_pims_mask.sum()}개를 G3_MEETING으로 설정")
                
                # 디버깅: Knox PIMS 설정 후 상태 확인
                for idx in daily_data[knox_pims_mask].index:
                    row = daily_data.loc[idx]
                    self.logger.info(f"Knox PIMS 설정 완료 [{idx}]: {row['datetime']} - activity_code={row['activity_code']}, duration={row.get('knox_duration', row.get('duration_minutes', 'N/A'))}분, is_protected=True")
            else:
                self.logger.info(f"[_apply_tag_based_rules] Knox PIMS 마스크 없음")
            
            # 일반 G3 태그 처리 (Knox PIMS 보호된 항목 제외)
            if regular_g3_mask.any():
                # Knox PIMS 보호된 항목은 제외
                if 'is_knox_pims_protected' in daily_data.columns:
                    regular_g3_mask = regular_g3_mask & (~daily_data['is_knox_pims_protected'].fillna(False))
                
                if regular_g3_mask.any():
                    activity_type = get_activity_type('MEETING')
                    daily_data.loc[regular_g3_mask, 'activity_code'] = 'MEETING'
                    daily_data.loc[regular_g3_mask, 'activity_type'] = activity_type.category if activity_type else 'meeting'
                    daily_data.loc[regular_g3_mask, '활동분류'] = activity_type.name_ko if activity_type else '회의'
                    daily_data.loc[regular_g3_mask, 'confidence'] = 95
                    self.logger.info(f"일반 G3 태그 {regular_g3_mask.sum()}개를 MEETING으로 설정")
        
        # 7. M1 태그 (바이오플라자 식사) 처리 - 확정적 규칙 엔진 사용
        m1_mask = daily_data['Tag_Code'] == 'M1'
        if m1_mask.any():
            # 확정적 규칙 엔진 가져오기
            rule_integration = get_rule_integration()
            
            # 시간대별로 식사 종류 결정
            for idx in daily_data[m1_mask].index:
                hour = daily_data.loc[idx, 'datetime'].hour
                minute = daily_data.loc[idx, 'datetime'].minute
                time_in_minutes = hour * 60 + minute
                
                # 다음 태그까지의 시간 계산
                next_idx = daily_data.index.get_loc(idx) + 1
                to_next_minutes = None
                if next_idx < len(daily_data):
                    time_diff = (daily_data.iloc[next_idx]['datetime'] - daily_data.loc[idx, 'datetime']).total_seconds() / 60
                    to_next_minutes = time_diff
                
                # 규칙 엔진을 통한 식사 시간 계산
                meal_duration = rule_integration.get_meal_duration('M1', to_next_minutes)
                daily_data.loc[idx, 'duration_minutes'] = meal_duration
                
                # M2 태그는 테이크아웃 식사로 분류하지만 시간대별 activity_code는 설정하지 않음
                daily_data.loc[idx, 'activity_code'] = 'MEAL'
                daily_data.loc[idx, 'activity_type'] = 'meal'
                daily_data.loc[idx, '활동분류'] = '식사중'
                
                daily_data.loc[idx, 'confidence'] = 100
                self.logger.info(f"M1 태그 - {daily_data.loc[idx, 'datetime']}: {daily_data.loc[idx, 'activity_code']} (duration: {meal_duration}분)")
            
            self.logger.info(f"M1 태그 {m1_mask.sum()}개를 시간대별 식사로 설정")
        
        # 7-1. M2 태그 (테이크아웃) 처리 - 확정적 규칙 엔진 사용
        m2_mask = daily_data['Tag_Code'] == 'M2'
        if m2_mask.any():
            # 확정적 규칙 엔진 가져오기
            rule_integration = get_rule_integration()
            
            # 시간대별로 식사 종류 결정
            for idx in daily_data[m2_mask].index:
                hour = daily_data.loc[idx, 'datetime'].hour
                minute = daily_data.loc[idx, 'datetime'].minute
                time_in_minutes = hour * 60 + minute
                
                # M2는 고정 10분
                meal_duration = rule_integration.get_meal_duration('M2', None)
                daily_data.loc[idx, 'duration_minutes'] = meal_duration
                
                # M2 태그는 테이크아웃 식사로 분류하지만 시간대별 activity_code는 설정하지 않음
                daily_data.loc[idx, 'activity_code'] = 'MEAL'
                daily_data.loc[idx, 'activity_type'] = 'meal'
                daily_data.loc[idx, '활동분류'] = '식사중'
                
                daily_data.loc[idx, 'confidence'] = 100
                daily_data.loc[idx, 'is_takeout'] = True
                self.logger.info(f"M2 테이크아웃 - {daily_data.loc[idx, 'datetime']}: {daily_data.loc[idx, 'activity_code']} (duration: {meal_duration}분)")
            
            self.logger.info(f"M2 태그 {m2_mask.sum()}개를 테이크아웃 식사로 설정")
        
        # 8. N1 태그 (휴게공간) 처리
        n1_mask = daily_data['Tag_Code'] == 'N1'
        if n1_mask.any():
            activity_type = get_activity_type('REST')
            daily_data.loc[n1_mask, 'activity_code'] = 'REST'
            daily_data.loc[n1_mask, 'activity_type'] = activity_type.category if activity_type else 'rest'
            daily_data.loc[n1_mask, '활동분류'] = activity_type.name_ko if activity_type else '휴식'
            daily_data.loc[n1_mask, 'confidence'] = 90
            self.logger.info(f"N1 태그 {n1_mask.sum()}개를 REST로 설정")
        
        # 9. 꼬리물기 감지 - 긴 T1 구간
        # T1 태그가 연속적으로 나타나는 구간 찾기
        t1_mask = daily_data['Tag_Code'] == 'T1'
        if t1_mask.any():
            # 시간순 정렬
            daily_data = daily_data.sort_values('datetime').reset_index(drop=True)
            
            # T1 태그 인덱스 찾기
            t1_indices = daily_data[t1_mask].index.tolist()
            
            # 연속된 T1 블록 찾기
            t1_blocks = []
            current_block = []
            
            for i, idx in enumerate(t1_indices):
                if not current_block:
                    current_block = [idx]
                else:
                    # 이전 인덱스와 연속되거나 시간이 가까운 경우
                    prev_idx = current_block[-1]
                    time_diff = (daily_data.loc[idx, 'datetime'] - daily_data.loc[prev_idx, 'datetime']).total_seconds() / 60
                    
                    if idx == prev_idx + 1 or time_diff <= 5:  # 연속이거나 5분 이내
                        current_block.append(idx)
                    else:
                        # 블록 종료
                        if len(current_block) > 1:
                            t1_blocks.append(current_block)
                        current_block = [idx]
            
            # 마지막 블록 처리
            if len(current_block) > 1:
                t1_blocks.append(current_block)
            
            # 각 T1 블록의 지속시간 계산 및 꼬리물기 판정
            for block in t1_blocks:
                start_time = daily_data.loc[block[0], 'datetime']
                end_time = daily_data.loc[block[-1], 'datetime']
                duration_minutes = (end_time - start_time).total_seconds() / 60
                
                if duration_minutes >= 30:  # 30분 이상 T1 구간
                    # 꼬리물기로 판정 - WORK로 변경
                    activity_type = get_activity_type('WORK')
                    for idx in block:
                        daily_data.loc[idx, 'activity_code'] = 'WORK'
                        daily_data.loc[idx, 'activity_type'] = activity_type.category if activity_type else 'work'
                        daily_data.loc[idx, '활동분류'] = activity_type.name_ko if activity_type else '작업'
                        
                        if duration_minutes >= 120:  # 2시간 이상
                            daily_data.loc[idx, 'confidence'] = 85
                        else:  # 30분-2시간
                            daily_data.loc[idx, 'confidence'] = 60
                    
                    self.logger.info(f"꼬리물기 감지: {start_time} ~ {end_time} ({duration_minutes:.1f}분) - {len(block)}개 태그를 WORK로 변경")
                else:
                    # 짧은 T1은 MOVEMENT로 유지
                    activity_type = get_activity_type('MOVEMENT')
                    for idx in block:
                        daily_data.loc[idx, 'activity_code'] = 'MOVEMENT'
                        daily_data.loc[idx, 'activity_type'] = activity_type.category if activity_type else 'movement'
                        daily_data.loc[idx, '활동분류'] = activity_type.name_ko if activity_type else '이동'
                        daily_data.loc[idx, 'confidence'] = 85
        
        # 10. 정문/스피드게이트 입문 최종 검증
        # T2가 아닌데 정문 입문으로 표시된 경우 수정
        gate_entry_mask = (
            (daily_data['INOUT_GB'] == '입문') & 
            (daily_data['DR_NM'].str.contains('정문|SPEED GATE', case=False, na=False)) &
            (daily_data['Tag_Code'] != 'T2')
        )
        if gate_entry_mask.any():
            activity_type = get_activity_type('COMMUTE_IN')
            daily_data.loc[gate_entry_mask, 'activity_code'] = 'COMMUTE_IN'
            daily_data.loc[gate_entry_mask, 'activity_type'] = activity_type.category if activity_type else 'movement'
            daily_data.loc[gate_entry_mask, '활동분류'] = activity_type.name_ko if activity_type else '출근'
            daily_data.loc[gate_entry_mask, 'confidence'] = 95
            self.logger.info(f"정문 입문 {gate_entry_mask.sum()}개를 COMMUTE_IN으로 수정")
        
        self.logger.info("태그 기반 규칙 적용 완료")
        return daily_data
    
    def _fill_time_gaps(self, data: pd.DataFrame) -> pd.DataFrame:
        """태그 사이의 시간 간격을 채워서 연속적인 활동 데이터 생성"""
        if data.empty:
            return data
            
        # 결과를 저장할 리스트
        filled_data = []
        
        # 시간순으로 정렬
        data = data.sort_values('datetime').reset_index(drop=True)
        
        # 마지막 태그 시간 확인 (야간 근무자 처리를 위해)
        last_tag_time = data.iloc[-1]['datetime']
        
        for i in range(len(data)):
            current_row = data.iloc[i].copy()
            
            # Knox PIMS 보호 - 이미 duration이 설정된 경우 유지
            if (current_row.get('is_knox_pims_protected', False) and 
                pd.notna(current_row.get('knox_duration'))):
                duration = current_row.get('knox_duration')
                self.logger.info(f"Knox PIMS duration 보존: {current_row['datetime']} - {duration}분")
            else:
                # 다음 태그까지의 시간 계산
                if i < len(data) - 1:
                    next_time = data.iloc[i + 1]['datetime']
                    duration = (next_time - current_row['datetime']).total_seconds() / 60
                    
                    # 60분을 초과하는 간격은 5분으로 제한 (비정상적인 gap 방지)
                    if duration > 60:
                        self.logger.warning(f"긴 시간 간격 감지: {current_row['datetime']} ~ {next_time} ({duration:.0f}분) -> 5분으로 제한")
                        duration = 5
                else:
                    # 마지막 태그는 5분으로 설정
                    duration = 5
            
            # O 태그(장비 사용)의 경우 최소 10분, 최대 30분으로 제한
            if current_row.get('INOUT_GB') == 'O' or current_row.get('activity_code') == 'EQUIPMENT_OPERATION':
                duration = min(max(duration, 10), 30)
            
            # 식사 활동의 duration 설정
            if current_row.get('activity_code') in ['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL']:
                # 실제 식사 태그가 있는 경우에만 식사로 처리
                if current_row.get('is_actual_meal', False):
                    # 테이크아웃 여부 확인
                    is_takeout = current_row.get('is_takeout', False)
                    if is_takeout:
                        # 테이크아웃은 10분 고정
                        duration = 10
                    else:
                        # 식당 식사는 다음 이동태그까지 (최대 1시간)
                        # duration은 이미 다음 태그까지의 시간으로 계산됨
                        if duration > 60:
                            duration = 60  # 최대 1시간으로 제한
                else:
                    # 식사 태그가 없는데 식사로 분류된 경우 WORK로 변경
                    # 단, EQUIPMENT_OPERATION은 보존
                    if current_row.get('activity_code') != 'EQUIPMENT_OPERATION':
                        current_row['activity_code'] = 'WORK'
                        current_row['activity_type'] = 'work'
                        current_row['confidence'] = 85
            
            # Knox PIMS 보호 - duration_minutes 덮어쓰기 방지
            if not (current_row.get('is_knox_pims_protected', False) and pd.notna(current_row.get('knox_duration'))):
                current_row['duration_minutes'] = duration
            else:
                current_row['duration_minutes'] = current_row.get('knox_duration')
                self.logger.info(f"Knox PIMS duration_minutes 보존: {current_row['datetime']} - {current_row['duration_minutes']}분")
            filled_data.append(current_row)
            
            # 출문(T3) 후 재입문(T2) 사이의 시간을 채우기
            if (i < len(data) - 1 and 
                'Tag_Code' in data.columns and
                current_row['Tag_Code'] == 'T3' and 
                data.iloc[i + 1]['Tag_Code'] == 'T2'):
                
                # 출문과 재입문 사이의 전체 시간
                gap_start = current_row['datetime']
                gap_end = data.iloc[i + 1]['datetime']
                gap_duration = (gap_end - gap_start).total_seconds() / 60
                
                # 5분 이상의 간격이 있으면 비근무 시간으로 채우기
                if gap_duration > 5:
                    # 출문 시간을 5분으로 제한
                    filled_data[-1]['duration_minutes'] = 5
                    
                    # 나머지 시간을 비근무로 채우기
                    gap_row = current_row.copy()
                    gap_row['datetime'] = gap_start + pd.Timedelta(minutes=5)
                    gap_row['duration_minutes'] = gap_duration - 10  # 출문 5분, 재입문 5분 제외
                    
                    # 이미 활동이 분류된 경우 (점심 등) 그대로 유지
                    if data.iloc[i + 1].get('activity_code') not in ['LUNCH', 'BREAKFAST', 'DINNER', 'MIDNIGHT_MEAL']:
                        gap_row['activity_code'] = 'NON_WORK'
                        gap_row['activity_type'] = 'non_work'
                        gap_row['confidence'] = 90
                    
                    filled_data.append(gap_row)
        
        return pd.DataFrame(filled_data)
    
    def analyze_daily_data(self, employee_id: str, selected_date: date, classified_data: pd.DataFrame):
        """일일 데이터 분석"""
        try:
            # 근무제 유형 확인
            work_type = self.get_employee_work_type(employee_id, selected_date)
            
            # 야간 근무자의 경우 근무 종료 시간 이후 데이터 제거
            if work_type == 'night_shift' and len(classified_data) > 0:
                # COMMUTE_OUT (퇴근) 태그 찾기
                commute_out_mask = classified_data['activity_code'] == 'COMMUTE_OUT'
                if commute_out_mask.any():
                    # 마지막 퇴근 시간
                    last_commute_out_idx = classified_data[commute_out_mask].index[-1]
                    last_commute_out_time = classified_data.loc[last_commute_out_idx, 'datetime']
                    
                    # 퇴근 후 1시간까지만 데이터 유지 (식사 등을 위해)
                    cutoff_time = last_commute_out_time + timedelta(hours=1)
                    classified_data = classified_data[classified_data['datetime'] <= cutoff_time].copy()
                    self.logger.info(f"야간 근무자 데이터 필터링: {last_commute_out_time} 퇴근 후 {cutoff_time}까지만 유지")
            
            # 시간 간격 채우기 (태그 사이의 빈 시간을 활동으로 채움)
            classified_data = self._fill_time_gaps(classified_data)
            
            # activity_type이 비어있는 경우 매핑
            if 'activity_type' not in classified_data.columns or classified_data['activity_type'].isna().any():
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
                    'BREAKFAST': 'meal',
                    'LUNCH': 'meal',
                    'DINNER': 'meal',
                    'MIDNIGHT_MEAL': 'meal',
                    'REST': 'rest',
                    'FITNESS': 'rest',
                    'LEAVE': 'rest',
                    'IDLE': 'rest',
                    'NON_WORK': 'non_work',
                    'UNKNOWN': 'work'
                }
                if 'activity_type' not in classified_data.columns:
                    classified_data['activity_type'] = classified_data['activity_code'].map(activity_type_mapping).fillna('work')
                else:
                    empty_mask = classified_data['activity_type'].isna() | (classified_data['activity_type'] == '')
                    classified_data.loc[empty_mask, 'activity_type'] = classified_data.loc[empty_mask, 'activity_code'].map(activity_type_mapping).fillna('work')
            
            # 근무 유형 확인
            work_type = self.get_employee_work_type(employee_id, selected_date)
            
            # 근무시간 계산
            if work_type == 'night_shift':
                # 야간 근무자의 경우 출근 태그 기준으로 계산
                commute_in_tags = classified_data[classified_data['activity_code'] == 'COMMUTE_IN']
                commute_out_tags = classified_data[classified_data['activity_code'] == 'COMMUTE_OUT']
                
                if not commute_in_tags.empty:
                    work_start = commute_in_tags['datetime'].min()
                else:
                    # 18시 이후 첫 태그를 출근으로 간주
                    evening_tags = classified_data[classified_data['datetime'].dt.hour >= 18]
                    if not evening_tags.empty:
                        work_start = evening_tags['datetime'].min()
                    else:
                        work_start = classified_data['datetime'].min()
                
                # 퇴근은 다음날 오전의 마지막 태그
                if not commute_out_tags.empty:
                    work_end = commute_out_tags['datetime'].max()
                else:
                    work_end = classified_data['datetime'].max()
                    
                # 야간 근무자의 경우 work_end가 12시를 넘으면 12시로 제한
                if work_end.hour >= 12 and work_end.date() == selected_date:
                    work_end = datetime.combine(selected_date, time(12, 0))
                    self.logger.info(f"야간 근무자 work_end를 12시로 제한: {work_end}")
            else:
                # 일반 근무자
                work_start = classified_data['datetime'].min()
                work_end = classified_data['datetime'].max()
                
            # 디버깅: 실제 데이터 범위 로깅
            self.logger.info(f"근무 유형: {work_type}")
            self.logger.info(f"분석 데이터 범위: {work_start} ~ {work_end}")
            self.logger.info(f"데이터 첫 태그: {classified_data['datetime'].min()}")
            self.logger.info(f"데이터 마지막 태그: {classified_data['datetime'].max()}")
            
            total_hours = (work_end - work_start).total_seconds() / 3600
            
            # 활동별 시간 집계 (새로운 activity_code 기준)
            if 'duration_minutes' in classified_data.columns:
                # Knox PIMS 데이터 상태 확인
                knox_pims_data = classified_data[
                    (classified_data['source'] == 'knox_pims') | 
                    (classified_data['activity_code'] == 'G3_MEETING') |
                    (classified_data.get('is_knox_pims_protected', False) == True)
                ]
                if not knox_pims_data.empty:
                    self.logger.info(f"[analyze_daily_data] Knox PIMS 데이터 상태:")
                    for idx, row in knox_pims_data.iterrows():
                        self.logger.info(f"  - [{idx}] {row['datetime']}: activity_code={row['activity_code']}, duration={row['duration_minutes']}분, source={row.get('source', 'N/A')}")
                
                activity_summary = classified_data.groupby('activity_code')['duration_minutes'].sum()
                activity_type_summary = classified_data.groupby('activity_type')['duration_minutes'].sum()
                
                # Knox PIMS 관련 집계 확인
                if 'G3_MEETING' in activity_summary:
                    self.logger.info(f"[analyze_daily_data] G3_MEETING 집계: {activity_summary['G3_MEETING']}분")
                if 'MEETING' in activity_summary:
                    self.logger.info(f"[analyze_daily_data] MEETING 집계: {activity_summary['MEETING']}분")
                
                # 디버깅: 식사 활동 집계 확인
                meal_activities = classified_data[classified_data['activity_code'].isin(['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL'])]
                if not meal_activities.empty:
                    self.logger.info(f"[activity_summary] 식사 활동 {len(meal_activities)}건:")
                    for idx, row in meal_activities.iterrows():
                        self.logger.info(f"  - {row['datetime']}: {row['activity_code']}, duration={row.get('duration_minutes', 0):.1f}분, "
                                       f"Tag_Code={row.get('Tag_Code', 'N/A')}, DR_NM={row.get('DR_NM', 'N/A')}")
                    for code in ['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL']:
                        if code in activity_summary:
                            self.logger.info(f"  - {code} 합계: {activity_summary[code]:.1f}분")
                
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
            
            # 먼저 식사 데이터를 activity_segments에 추가
            if employee_id and selected_date:
                meal_data_for_segments = self.get_meal_data(employee_id, selected_date)
                if meal_data_for_segments is not None and not meal_data_for_segments.empty:
                    date_column = 'meal_datetime' if 'meal_datetime' in meal_data_for_segments.columns else '취식일시'
                    category_column = 'meal_category' if 'meal_category' in meal_data_for_segments.columns else '식사대분류'
                    service_point_column = '배식구' if '배식구' in meal_data_for_segments.columns else 'service_point'
                    takeout_column = 'is_takeout' if 'is_takeout' in meal_data_for_segments.columns else '테이크아웃'
                    
                    for _, meal in meal_data_for_segments.iterrows():
                        meal_time = pd.to_datetime(meal[date_column])
                        meal_category = meal.get(category_column, '')
                        restaurant_info = meal.get(service_point_column, meal.get('식당명', ''))
                        
                        # 테이크아웃 판단
                        takeout_from_data = meal.get(takeout_column, False)
                        takeout_from_location = '테이크아웃' in str(restaurant_info)
                        is_takeout = takeout_from_data == 'Y' or takeout_from_location
                        
                        # 식사 종류별 activity_code
                        meal_code_map = {
                            '조식': 'BREAKFAST',
                            '중식': 'LUNCH',
                            '석식': 'DINNER',
                            '야식': 'MIDNIGHT_MEAL'
                        }
                        activity_code = meal_code_map.get(meal_category, 'LUNCH')
                        
                        # M1/M2 태그 결정
                        Tag_Code = 'M2' if is_takeout else 'M1'
                        
                        # 식사 세그먼트 직접 추가
                        activity_segments.append({
                            'start_time': meal_time,
                            'end_time': meal_time + timedelta(minutes=10),  # 테이크아웃 10분
                            'activity': 'meal',
                            'activity_code': activity_code,
                            'location': restaurant_info,
                            'duration_minutes': None,  # 나중에 다음 태그와의 시간 차이로 계산
                            'confidence': 100,
                            'is_actual_meal': True,
                            'is_takeout': is_takeout,
                            'Tag_Code': Tag_Code  # M1/M2 태그 추가
                        })
                        self.logger.info(f"식사 세그먼트 직접 추가: {meal_time} - {meal_category} @ {restaurant_info}, takeout={is_takeout}, code={activity_code}")
            
            # 나머지 활동 정리
            for idx, row in classified_data.iterrows():
                # Knox PIMS 회의의 경우 종료시간 사용
                if row.get('source') == 'knox_pims' and pd.notna(row.get('knox_end_time')):
                    end_time = row['knox_end_time']
                    duration_minutes = row.get('knox_duration', 60)  # Knox에서 계산된 duration 사용
                else:
                    # next_time이 NaT인 경우 처리
                    end_time = row.get('next_time')
                    if pd.isna(end_time):
                        end_time = row['datetime'] + timedelta(minutes=5)
                    duration_minutes = None  # 나중에 계산
                
                # 태그 기반 규칙이 적용된 후에는 activity_code를 건드리지 않음
                # T2/T3 태그는 이미 COMMUTE_IN/COMMUTE_OUT으로 설정됨
                inout_gb = row.get('INOUT_GB', '')
                activity_code = row.get('activity_code', '')
                
                # activity_code를 기반으로 올바른 activity_type 설정
                if activity_code == 'COMMUTE_IN':
                    activity_type = 'commute'
                elif activity_code == 'COMMUTE_OUT':
                    activity_type = 'commute'
                elif activity_code in ['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL']:
                    activity_type = 'meal'
                elif activity_code in ['MEETING']:
                    activity_type = 'meeting'
                elif activity_code in ['REST', 'FITNESS']:
                    activity_type = 'rest'
                elif activity_code in ['MOVEMENT']:
                    activity_type = 'movement'
                elif activity_code in ['WORK', 'FOCUSED_WORK', 'EQUIPMENT_OPERATION', 'WORK_PREPARATION']:
                    activity_type = 'work'
                elif activity_code in ['NON_WORK']:
                    activity_type = 'non_work'
                else:
                    activity_type = row.get('activity_type', 'work')
                
                # 디버깅: T2 태그 확인
                if row.get('Tag_Code') == 'T2' or (row.get('DR_NM') and 'SPEED GATE' in str(row['DR_NM'])):
                    self.logger.info(f"[SEGMENT생성] T2/GATE 태그 발견: {row['datetime']} - {row['DR_NM']}")
                    self.logger.info(f"  - Tag_Code: {row.get('Tag_Code')}, activity_code: {activity_code}, 활동분류: {row.get('활동분류')}")
                
                # 태그 기반 규칙으로 이미 설정된 COMMUTE_IN/COMMUTE_OUT은 보호
                if activity_code in ['COMMUTE_IN', 'COMMUTE_OUT']:
                    # 이미 태그 기반 규칙으로 설정된 경우 변경하지 않음
                    pass
                # 입문/출문인데 식사로 잘못 분류된 경우만 수정 (태그 기반 규칙에서 버려진 경우)
                elif inout_gb == '출문' and activity_code in ['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL']:
                    activity_code = 'MOVEMENT'
                    activity_type = 'movement'
                    self.logger.info(f"출문 수정: {row['datetime']} - 식사 -> {activity_code}")
                elif inout_gb == '입문' and activity_code in ['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL']:
                    activity_code = 'WORK'
                    activity_type = 'work'
                    self.logger.info(f"입문 수정: {row['datetime']} - 식사 -> {activity_code}")
                
                # 디버깅: 테이크아웃 식사 확인
                is_takeout_value = row.get('is_takeout', False)
                if '테이크아웃' in str(row.get('DR_NM', '')):
                    self.logger.info(f"테이크아웃 위치 - is_takeout={is_takeout_value}, INOUT_GB={inout_gb}, activity={activity_code} - {row['datetime']}: {row['DR_NM']}")
                
                # 식사 태그 디버깅
                if inout_gb == '식사':
                    self.logger.info(f"식사 세그먼트 추가: {row['datetime']} - {row['DR_NM']}, activity={activity_code}")
                
                # 출퇴근 태그 디버깅
                if activity_code in ['COMMUTE_IN', 'COMMUTE_OUT']:
                    self.logger.info(f"출퇴근 세그먼트 추가: {row['datetime']} - {row['DR_NM']}, activity_code={activity_code}, activity_type={activity_type}")
                
                # T2 태그가 WORK로 잘못 설정되는 경우 추가 디버깅
                if row.get('Tag_Code') == 'T2' and activity_code != 'COMMUTE_IN':
                    self.logger.error(f"[ERROR] T2 태그가 COMMUTE_IN이 아님! activity_code={activity_code}")
                    self.logger.error(f"  - row 전체 데이터: {row.to_dict()}")
                
                # activity_code가 빈 문자열이면 기본값 설정
                if not activity_code:
                    activity_code = 'WORK'
                    self.logger.warning(f"[WARNING] activity_code가 비어있음: {row['datetime']} - {row['DR_NM']}")
                
                # 디버깅: 실제로 추가되는 값 확인
                if row.get('Tag_Code') == 'T2' or 'SPEED GATE' in str(row.get('DR_NM', '')):
                    self.logger.info(f"[SEGMENT추가] T2/GATE: activity_code={activity_code}, activity_type={activity_type}")
                    # T2 태그인데 activity_code가 COMMUTE_IN이 아니면 강제 설정
                    if row.get('Tag_Code') == 'T2' and activity_code != 'COMMUTE_IN':
                        self.logger.warning(f"[WARNING] T2 태그인데 activity_code가 COMMUTE_IN이 아님! 강제 설정")
                        activity_code = 'COMMUTE_IN'
                        activity_type = 'commute'
                
                # 테이크아웃 식사 체크
                if '테이크아웃' in str(row.get('DR_NM', '')):
                    if not row.get('Tag_Code'):
                        # Tag_Code가 없으면 M2로 설정
                        row['Tag_Code'] = 'M2'
                    is_takeout_value = True
                
                segment_data = {
                    'start_time': row['datetime'],
                    'end_time': end_time,
                    'activity': activity_code,  # activity_type 대신 activity_code 사용
                    'activity_code': activity_code,
                    'location': row['DR_NM'],
                    'duration_minutes': duration_minutes if duration_minutes is not None else row.get('duration_minutes', 5),
                    'confidence': row.get('confidence', 80),  # 신뢰도 추가
                    'is_actual_meal': row.get('is_actual_meal', False),  # 실제 식사 여부
                    'is_takeout': is_takeout_value,  # 테이크아웃 여부
                    'Tag_Code': row.get('Tag_Code', ''),  # Tag_Code도 전달
                    'source': row.get('source', '')  # source 정보도 전달
                }
                
                # 디버깅: T2 태그(출근) 세그먼트 생성 확인
                if row.get('Tag_Code') == 'T2' or activity_code == 'COMMUTE_IN':
                    self.logger.info(f"[SEGMENT추가] 출근 세그먼트: {segment_data['start_time']} - activity_code={activity_code}, Tag_Code={row.get('Tag_Code')}")
                
                # 디버깅: G3 태그(회의) 세그먼트 생성 확인
                if row.get('Tag_Code') == 'G3' or activity_code in ['MEETING', 'G3_MEETING']:
                    self.logger.info(f"[SEGMENT추가] 회의 세그먼트: {segment_data['start_time']} - activity_code={activity_code}, Tag_Code={row.get('Tag_Code')}, source={row.get('source', 'N/A')}")
                
                activity_segments.append(segment_data)
            
            # activity_segments를 시간순으로 정렬
            activity_segments = sorted(activity_segments, key=lambda x: x['start_time'])
            
            # 디버깅: 전체 세그먼트 확인
            self.logger.info(f"총 {len(activity_segments)}개의 세그먼트 생성됨")
            
            # 활동 코드별 집계
            activity_code_counts = {}
            for seg in activity_segments:
                code = seg.get('activity_code', 'UNKNOWN')
                activity_code_counts[code] = activity_code_counts.get(code, 0) + 1
                
                if seg['activity_code'] in ['COMMUTE_IN', 'COMMUTE_OUT']:
                    self.logger.info(f"출퇴근 세그먼트: {seg['start_time']} - {seg['activity_code']} @ {seg['location']}")
                elif seg['activity_code'] in ['MEETING', 'G3_MEETING']:
                    self.logger.info(f"회의 세그먼트: {seg['start_time']} - {seg['activity_code']} @ {seg['location']}")
            
            self.logger.info(f"활동 코드별 세그먼트 수: {activity_code_counts}")
            
            # Knox PIMS 회의 후 WORK 세그먼트 추가
            new_segments = []
            knox_meeting_count = 0
            work_segment_added = 0
            
            for i in range(len(activity_segments)):
                segment = activity_segments[i]
                new_segments.append(segment)
                
                # Knox PIMS 회의 세그먼트 확인
                if segment.get('source') == 'knox_pims':
                    knox_meeting_count += 1
                    self.logger.info(f"Knox PIMS 회의 발견 [{i}]: {segment['start_time']} ~ {segment['end_time']}, " +
                                   f"activity_code={segment.get('activity_code')}, duration={segment.get('duration_minutes')}분")
                
                # Knox PIMS 회의 세그먼트인 경우
                if (segment.get('source') == 'knox_pims' and 
                    segment.get('activity_code') == 'G3_MEETING' and
                    i < len(activity_segments) - 1):
                    
                    # 회의 종료 시간과 다음 세그먼트 시작 시간 사이에 간격이 있는 경우
                    meeting_end = segment['end_time']
                    next_start = activity_segments[i+1]['start_time']
                    gap_minutes = (next_start - meeting_end).total_seconds() / 60
                    
                    self.logger.info(f"Knox PIMS 회의 종료: {meeting_end}, 다음 태그: {next_start}, 간격: {gap_minutes:.1f}분")
                    
                    if gap_minutes > 5:  # 5분 이상의 간격이 있으면 WORK 세그먼트 추가
                        work_segment = {
                            'start_time': meeting_end,
                            'end_time': next_start,
                            'activity': 'WORK',
                            'activity_code': 'WORK',
                            'location': '작업장',
                            'duration_minutes': gap_minutes,
                            'confidence': 70,
                            'is_actual_meal': False,
                            'is_takeout': False,
                            'Tag_Code': '',
                            'source': 'inferred'
                        }
                        new_segments.append(work_segment)
                        work_segment_added += 1
                        self.logger.info(f"회의 종료 후 WORK 세그먼트 추가: {meeting_end} ~ {next_start} ({gap_minutes:.1f}분)")
            
            self.logger.info(f"Knox PIMS 회의 {knox_meeting_count}건 발견, WORK 세그먼트 {work_segment_added}건 추가")
            
            activity_segments = new_segments
            # 다시 시간순으로 정렬
            activity_segments = sorted(activity_segments, key=lambda x: x['start_time'])
            
            # 정렬 후 duration_minutes 재계산
            for i in range(len(activity_segments)):
                # Knox PIMS 회의는 이미 duration이 설정되어 있으므로 건너뛰기
                if (activity_segments[i].get('source') == 'knox_pims' and 
                    activity_segments[i]['duration_minutes'] is not None):
                    self.logger.info(f"Knox PIMS 회의 duration 유지: {activity_segments[i]['start_time']} - {activity_segments[i]['duration_minutes']}분")
                    continue
                    
                if activity_segments[i]['duration_minutes'] is None:
                    if i < len(activity_segments) - 1:
                        # 다음 세그먼트까지의 시간 계산
                        duration = (activity_segments[i+1]['start_time'] - activity_segments[i]['start_time']).total_seconds() / 60
                        
                        # 식사 세그먼트의 경우 특별 처리
                        if activity_segments[i].get('activity_code') in ['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL']:
                            if activity_segments[i].get('is_takeout', False):
                                # 테이크아웃은 10분 고정
                                duration = 10
                            else:
                                # 식당 식사는 다음 태그까지의 시간 사용 (최대 1시간)
                                if duration > 60:
                                    duration = 60
                        
                        activity_segments[i]['duration_minutes'] = duration
                        # end_time도 업데이트
                        activity_segments[i]['end_time'] = activity_segments[i]['start_time'] + timedelta(minutes=duration)
                    else:
                        # 마지막 세그먼트인 경우
                        is_takeout = activity_segments[i].get('is_takeout', False)
                        if activity_segments[i].get('activity_code') in ['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL']:
                            # 식사인 경우 30분 고정
                            default_duration = 30
                        else:
                            default_duration = 30  # 기본값 30분
                        activity_segments[i]['duration_minutes'] = default_duration
                        activity_segments[i]['end_time'] = activity_segments[i]['start_time'] + timedelta(minutes=default_duration)
            
            # Claim 데이터 가져오기
            claim_data = self.get_daily_claim_data(employee_id, selected_date)
            
            # 데이터 품질 분석
            data_quality = self.analyze_data_quality(classified_data)
            
            # 신뢰지수 기반 근무시간 계산
            work_hours, avg_confidence, activity_breakdown = self.confidence_calculator.calculate_work_time(classified_data)
            
            # 디버깅: 항상 activity_code 분포 출력
            self.logger.info(f"calculate_work_time 호출 전 activity_code 분포: {classified_data['activity_code'].value_counts().to_dict()}")
            self.logger.info(f"calculate_work_time 결과: work_hours={work_hours:.2f}, avg_confidence={avg_confidence:.2f}")
            self.logger.info(f"activity_breakdown: {activity_breakdown}")
            
            # 작업시간이 0인 경우 디버깅
            if work_hours == 0:
                self.logger.warning(f"작업시간이 0으로 계산됨")
                self.logger.info(f"classified_data 샘플 (처음 5개):")
                for i, row in classified_data.head(5).iterrows():
                    self.logger.info(f"  {row['datetime']} - {row['DR_NM'][:30]} - {row['activity_code']} ({row.get('duration_minutes', 0):.1f}분)")
                work_activities = classified_data[classified_data['activity_code'].isin(['WORK', 'FOCUSED_WORK', 'EQUIPMENT_OPERATION', 'WORKING', 'WORK_PREPARATION', 'MEETING'])]
                self.logger.info(f"작업 관련 활동 수: {len(work_activities)}")
                if not work_activities.empty:
                    self.logger.info(f"작업 활동 샘플:")
                    for idx, row in work_activities.head().iterrows():
                        self.logger.info(f"  - {row['datetime']}: {row['activity_code']} at {row['DR_NM']}")
            
            # work_status별 시간 집계 (참고용)
            if 'work_status' in classified_data.columns:
                status_summary = classified_data.groupby('work_status')['duration_minutes'].sum()
            else:
                status_summary = pd.Series()
            
            work_time_analysis = {
                'actual_work_hours': work_hours,
                'claimed_work_hours': claim_data['claim_hours'] if claim_data else 8.0,
                'efficiency_ratio': 0,
                'work_breakdown': activity_breakdown,
                'status_breakdown': {},  # work_status별 시간 추가
                'confidence_score': avg_confidence  # 전체 신뢰도 추가
            }
            
            # 효율성 계산
            if work_time_analysis['claimed_work_hours'] > 0:
                efficiency = work_time_analysis['actual_work_hours'] / work_time_analysis['claimed_work_hours'] * 100
                work_time_analysis['efficiency_ratio'] = round(efficiency, 1)
            
            # 활동별 시간 분석
            for activity_type, minutes in activity_type_summary.items():
                work_time_analysis['work_breakdown'][activity_type] = minutes / 60
            
            # work_status별 시간 분석
            for status, minutes in status_summary.items():
                work_time_analysis['status_breakdown'][status] = minutes / 60
            
            # 근무제 유형 추가
            work_type = self.get_employee_work_type(employee_id, selected_date)
            
            # 식사 시간 분석
            meal_time_analysis = self.analyze_meal_times(classified_data)
            
            # 최종 반환 전 Gantt 차트용 데이터 다시 한 번 확인
            self.logger.info("=== 최종 analysis_result activity_segments 확인 ===")
            commute_segments = [seg for seg in activity_segments if seg.get('activity_code') in ['COMMUTE_IN', 'COMMUTE_OUT']]
            if commute_segments:
                self.logger.info(f"출퇴근 세그먼트 {len(commute_segments)}개 발견:")
                for seg in commute_segments:
                    self.logger.info(f"  - {seg['start_time']} : {seg['activity_code']} @ {seg.get('location', 'N/A')}")
            else:
                self.logger.warning("출퇴근 세그먼트가 없습니다!")
            
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
                'work_time_analysis': work_time_analysis,
                'work_type': work_type,
                'meal_time_analysis': meal_time_analysis
            }
            
        except Exception as e:
            self.logger.error(f"일일 데이터 분석 실패: {e}")
            return None
    
    def analyze_meal_times(self, classified_data: pd.DataFrame) -> dict:
        """식사 시간 분석"""
        meal_patterns = {
            '조식': {'frequency': 0, 'avg_duration': 0, 'times': [], 'actual_count': 0},
            '중식': {'frequency': 0, 'avg_duration': 0, 'times': [], 'actual_count': 0},
            '석식': {'frequency': 0, 'avg_duration': 0, 'times': [], 'actual_count': 0},
            '야식': {'frequency': 0, 'avg_duration': 0, 'times': [], 'actual_count': 0}
        }
        
        meal_types = {
            'breakfast': '조식',
            'lunch': '중식',
            'dinner': '석식',
            'midnight_meal': '야식'
        }
        
        actual_meal_count = 0
        estimated_meal_count = 0
        
        # 식사 활동 찾기
        for idx, row in classified_data.iterrows():
            if row.get('activity_type') in meal_types:
                meal_name = meal_types[row['activity_type']]
                meal_patterns[meal_name]['frequency'] += 1
                meal_patterns[meal_name]['times'].append(row['datetime'].strftime('%H:%M'))
                
                # 실제 식사 데이터인지 확인
                if row.get('is_actual_meal', False):
                    meal_patterns[meal_name]['actual_count'] += 1
                    actual_meal_count += 1
                else:
                    estimated_meal_count += 1
                
                # 지속 시간
                duration = row.get('duration_minutes', 30)
                meal_patterns[meal_name]['avg_duration'] += duration
        
        # 평균 지속 시간 계산
        for meal in meal_patterns:
            if meal_patterns[meal]['frequency'] > 0:
                meal_patterns[meal]['avg_duration'] /= meal_patterns[meal]['frequency']
                meal_patterns[meal]['avg_duration'] = round(meal_patterns[meal]['avg_duration'], 1)
        
        # 총 식사 시간
        total_meal_time = sum(
            pattern['frequency'] * pattern['avg_duration'] 
            for pattern in meal_patterns.values()
        )
        
        return {
            'meal_patterns': meal_patterns,
            'total_meal_time': round(total_meal_time, 1),
            'actual_meal_count': actual_meal_count,
            'estimated_meal_count': estimated_meal_count,
            'meal_regularity': self._calculate_meal_regularity(meal_patterns)
        }
    
    def _calculate_meal_regularity(self, meal_patterns: dict) -> float:
        """식사 규칙성 계산 (0-100)"""
        # 각 식사별 규칙성 점수
        scores = []
        
        # 조식 (주 3회 이상이면 규칙적)
        if meal_patterns['조식']['frequency'] >= 3:
            scores.append(100)
        else:
            scores.append(meal_patterns['조식']['frequency'] / 3 * 100)
        
        # 중식 (주 5회 이상이면 규칙적)
        if meal_patterns['중식']['frequency'] >= 5:
            scores.append(100)
        else:
            scores.append(meal_patterns['중식']['frequency'] / 5 * 100)
        
        # 석식과 야식은 근무 패턴에 따라 평가
        dinner_midnight_total = meal_patterns['석식']['frequency'] + meal_patterns['야식']['frequency']
        if dinner_midnight_total >= 3:
            scores.append(100)
        else:
            scores.append(dinner_midnight_total / 3 * 100)
        
        return round(sum(scores) / len(scores), 1)
    
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
        # 신뢰도가 100을 초과하는 경우 100으로 제한
        avg_confidence = confidence_values.mean() if len(confidence_values) > 0 else 80
        overall_score = min(round(avg_confidence, 1), 100.0)
        
        # 태그 데이터 완성도 (태그 코드가 있는 비율)
        if 'Tag_Code' in classified_data.columns:
            completeness = (classified_data['Tag_Code'].notna().sum() / total * 100) if total > 0 else 0
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
        
        # 최근 조회 관리자 초기화
        if 'recent_views_manager' not in st.session_state:
            st.session_state.recent_views_manager = RecentViewsManager()
        
        # 직원 선택 및 기간 설정
        self.render_controls()
        
        # 빠른 조회가 트리거된 경우 자동 실행
        if st.session_state.get('quick_load_triggered'):
            st.session_state.quick_load_triggered = False
            self.execute_analysis()
        
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
                ["목록에서 선택", "조직에서 선택", "직접 입력"],
                key="employee_selection_method"
            )
            
            if selection_method == "목록에서 선택":
                if employee_list:
                    # 세션 상태에서 선택된 직원 확인
                    default_index = 0
                    if 'selected_employee' in st.session_state and st.session_state.selected_employee:
                        # 선택된 직원 ID로 리스트에서 매칭되는 항목 찾기
                        for idx, emp in enumerate(employee_list):
                            if " - " in emp:
                                emp_id = emp.split(" - ")[0]
                                if emp_id == st.session_state.selected_employee:
                                    default_index = idx
                                    break
                            elif emp == st.session_state.selected_employee:
                                default_index = idx
                                break
                    
                    selected_employee = st.selectbox(
                        f"직원 선택 (총 {len(employee_list)}명)",
                        employee_list,
                        index=default_index,
                        key="individual_employee_select"
                    )
                    # "사번 - 이름" 형식에서 사번과 이름 추출
                    if " - " in selected_employee:
                        employee_id = selected_employee.split(" - ")[0]
                        employee_name = selected_employee.split(" - ")[1]
                        st.session_state.selected_employee_name = employee_name
                    else:
                        employee_id = selected_employee
                        st.session_state.selected_employee_name = None
                else:
                    st.warning("로드된 직원 데이터가 없습니다.")
                    employee_id = st.text_input("직원 ID 입력", key="manual_employee_input")
            
            elif selection_method == "조직에서 선택":
                # 조직 계층 구조 기반 선택
                employee_id = self.render_organization_selection()
            
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
                
                # 세션 상태에서 날짜 확인, 없으면 기본값 설정
                if 'analysis_date' in st.session_state and st.session_state.analysis_date:
                    default_date = st.session_state.analysis_date
                    # 데이터 범위 내에 있는지 확인
                    if default_date < date_range_info['min_date'] or default_date > date_range_info['max_date']:
                        default_date = min(date_range_info['max_date'], date.today())
                else:
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
                if 'analysis_date' in st.session_state and st.session_state.analysis_date:
                    default_date = st.session_state.analysis_date
                else:
                    default_date = date.today()
                    
                selected_date = st.date_input(
                    "날짜 선택",
                    value=default_date,
                    key="individual_analysis_date_default"
                )
            
            st.session_state.analysis_date = selected_date
        
        with col3:
            # 최근 조회 섹션
            st.markdown("**최근 조회**")
            
            recent_views = st.session_state.recent_views_manager.get_recent_views()
            
            if not recent_views:
                st.info("최근 조회 기록이 없습니다.")
            else:
                # 최근 조회 리스트 표시
                for idx, view in enumerate(recent_views):
                    # 사번 - 이름 형식으로 표시
                    display_text = f"{view['employee_id']} - {view['employee_name']}"
                    
                    if st.button(
                        display_text,
                        key=f"recent_{idx}",
                        use_container_width=True,
                        help=f"📅 {view['analysis_date']} | 🏢 {view.get('department', 'N/A')}"
                    ):
                        # 세션 상태에 선택된 정보 저장
                        st.session_state['selected_employee'] = view['employee_id']
                        st.session_state['selected_employee_name'] = view['employee_name']
                        st.session_state['analysis_date'] = datetime.fromisoformat(view['analysis_date']).date()
                        st.session_state['quick_load_triggered'] = True
                        st.rerun()
                
                # 전체 삭제 버튼
                if st.button("🗑️ 전체 삭제", key="clear_all_recent", use_container_width=True):
                    st.session_state.recent_views_manager.clear_all()
                    st.rerun()
    
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
                
                # 장비 데이터 로드
                equipment_data = self.get_employee_equipment_data(employee_id, selected_date)
                if equipment_data is not None and not equipment_data.empty:
                    st.info(f"🔧 장비 사용 데이터: {len(equipment_data)}건 발견")
                
                # 근태 데이터 로드
                attendance_data = self.get_employee_attendance_data(employee_id, selected_date)
                if attendance_data is not None and not attendance_data.empty:
                    st.info(f"📋 근태 정보: {len(attendance_data)}건 발견")
                
                # Knox/Equipment 데이터 확인
                knox_tags = daily_data[daily_data['Tag_Code'] == 'G3']
                if not knox_tags.empty:
                    self.logger.info(f"[분류 전] G3 태그 {len(knox_tags)}건 발견:")
                    for idx, row in knox_tags.iterrows():
                        self.logger.info(f"  - {row['datetime']}: Tag_Code={row.get('Tag_Code')}, source={row.get('source', 'N/A')}, " +
                                       f"activity_code={row.get('activity_code', 'N/A')}, 활동분류={row.get('활동분류', 'N/A')}")
                
                # 활동 분류 수행 (employee_id와 selected_date 전달)
                classified_data = self.classify_activities(daily_data, employee_id, selected_date)
                
                # 분류 후 T2 태그 상태 확인
                t2_classified = classified_data[classified_data['Tag_Code'] == 'T2']
                if not t2_classified.empty:
                    self.logger.info(f"[classify_activities 후] T2 태그 {len(t2_classified)}건:")
                    for idx, row in t2_classified.head(3).iterrows():
                        self.logger.info(f"  - {row['datetime']}: activity_code={row.get('activity_code')}, activity_type={row.get('activity_type')}, DR_NM={row['DR_NM']}")
                
                # 분류 후 G3 태그 상태 확인
                g3_classified = classified_data[classified_data['Tag_Code'] == 'G3']
                if not g3_classified.empty:
                    self.logger.info(f"[classify_activities 후] G3 태그 {len(g3_classified)}건:")
                    for idx, row in g3_classified.iterrows():
                        self.logger.info(f"  - {row['datetime']}: activity_code={row.get('activity_code', 'N/A')}, " +
                                       f"활동분류={row.get('활동분류', 'N/A')}, source={row.get('source', 'N/A')}")
                
                # 분석 결과 생성
                analysis_result = self.analyze_daily_data(employee_id, selected_date, classified_data)
                
                # analyze_daily_data가 실패한 경우 기본 결과 생성
                if analysis_result is None:
                    st.error("데이터 분석 중 오류가 발생했습니다. 기본 정보만 표시합니다.")
                    analysis_result = self.create_sample_analysis_result(employee_id, (selected_date, selected_date))
                
                # 장비 데이터를 분석 결과에 추가
                if equipment_data is not None and not equipment_data.empty:
                    analysis_result['equipment_data'] = equipment_data
                
                # 근태 데이터를 분석 결과에 추가
                if attendance_data is not None and not attendance_data.empty:
                    analysis_result['attendance_data'] = attendance_data
                
                # 직원 정보 추가 (최근 조회 기록 저장용)
                employee_info = self.get_employee_info(employee_id)
                analysis_result['employee_info'] = employee_info
                
                # 최근 조회 기록에 추가
                if 'recent_views_manager' in st.session_state:
                    employee_name = employee_info.get('name', employee_id)
                    department = employee_info.get('department', 'N/A')
                    st.session_state.recent_views_manager.add_view(
                        employee_id=employee_id,
                        employee_name=employee_name,
                        analysis_date=selected_date.isoformat(),
                        department=department
                    )
                
                # 결과 렌더링
                self.render_analysis_results(analysis_result)
                
        except Exception as e:
            st.error(f"분석 중 오류 발생: {e}")
            self.logger.error(f"개인 분석 오류: {e}")
            import traceback
            self.logger.error(f"전체 스택 트레이스:\n{traceback.format_exc()}")
    
    def create_sample_analysis_result(self, employee_id: str, date_range: tuple):
        """샘플 분석 결과 생성"""
        return {
            'employee_id': employee_id,
            'analysis_date': date_range[0],
            'total_hours': 8.5,
            'work_start': '08:00',
            'work_end': '17:30',
            'activity_summary': {
                'WORK': 390,  # 6.5시간 * 60분
                'MEETING': 72,  # 1.2시간 * 60분
                'MOVEMENT': 48,  # 0.8시간 * 60분
                'LUNCH': 60,
                'BREAKFAST': 30,
                'REST': 30
            },
            'area_summary': {},
            'activity_segments': [],
            'raw_data': [],
            'total_records': 0,
            'claim_data': {},
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
            },
            'work_type': 'day_shift'
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
        # 근태 정보 표시 (있는 경우)
        if 'attendance_data' in analysis_result:
            self.render_attendance_info(analysis_result['attendance_data'])
        
        # 활동별 시간 요약 렌더링
        self.render_activity_summary(analysis_result)
        
        
        # 상세 Gantt 차트
        st.markdown("### 📊 활동 시퀀스 타임라인")
        # 개선된 Gantt 차트 사용
        improved_chart = render_improved_gantt_chart(analysis_result)
        
        if improved_chart:
            st.plotly_chart(improved_chart, use_container_width=True)
        else:
            # fallback to original chart
            self.render_detailed_gantt_chart(analysis_result)
        
        # 장비 사용 데이터 (있을 경우에만 타임라인 아래에 표시)
        equipment_data = self.get_employee_equipment_data(analysis_result['employee_id'], analysis_result['analysis_date'])
        if equipment_data is not None and not equipment_data.empty:
            # 필요 시 equipment_data를 analysis_result에 추가
            analysis_result['equipment_data'] = equipment_data
            st.markdown("### 🔧 장비 사용 현황")
            self.render_equipment_usage(analysis_result)
        
        # 네트워크 분석 (이동 경로)
        st.markdown("### 🔄 Movement Path Network Analysis")
        self.render_network_analysis(analysis_result)
        
        # 상세 태그 기록
        st.markdown("### 📋 상세 태그 기록")
        self.render_detailed_records(analysis_result)
    
    def render_daily_summary(self, analysis_result: dict):
        """일일 활동 요약 렌더링 (UI 참조자료 기반)"""
        st.markdown("### 📈 일일 활동 요약")
        
        work_analysis = analysis_result['work_time_analysis']
        claim_data = analysis_result.get('claim_data', {})
        
        # 주요 지표 대시보드 - 첫 번째 줄
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric(
                "실제 근무시간",
                f"{work_analysis['actual_work_hours']:.1f}h",
                f"{work_analysis['actual_work_hours'] - work_analysis['claimed_work_hours']:+.1f}h"
            )
        
        with col2:
            # 회의 시간 계산 - 여러 소스에서 확인
            meeting_hours = 0
            
            # 1. work_breakdown에서 meeting 시간
            meeting_hours += work_analysis.get('work_breakdown', {}).get('meeting', 0)
            
            # 2. activity_summary에서 G3_MEETING과 MEETING 시간 추가
            if 'activity_summary' in analysis_result:
                activity_summary = analysis_result['activity_summary']
                g3_meeting_minutes = activity_summary.get('G3_MEETING', 0)
                meeting_minutes = activity_summary.get('MEETING', 0)
                meeting_hours += g3_meeting_minutes / 60  # 분을 시간으로 변환
                meeting_hours += meeting_minutes / 60     # 분을 시간으로 변환
                
                # 디버깅 로그
                if g3_meeting_minutes > 0 or meeting_minutes > 0:
                    self.logger.info(f"회의 시간 집계: G3_MEETING={g3_meeting_minutes}분, MEETING={meeting_minutes}분, 총 회의시간={meeting_hours:.1f}시간")
            
            st.metric(
                "회의 시간",
                f"{meeting_hours:.1f}h",
                ""
            )
        
        with col3:
            # 식사 시간 계산
            meal_minutes = 0
            if 'activity_summary' in analysis_result:
                for meal_type in ['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL']:
                    meal_minutes += analysis_result['activity_summary'].get(meal_type, 0)
            meal_hours = meal_minutes / 60
            st.metric(
                "식사 시간",
                f"{meal_hours:.1f}h",
                ""
            )
        
        with col4:
            st.metric(
                "업무 효율성",
                f"{work_analysis['efficiency_ratio']:.1f}%",
                "2.3%"
            )
        
        with col5:
            # 초과근무 표시
            overtime = claim_data.get('overtime', 0)
            st.metric(
                "초과근무",
                f"{overtime:.1f}h" if overtime > 0 else "없음",
                ""
            )
        
        # 두 번째 줄 - 부가 정보
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            # 근무 형태 표시 (WORKSCHDTYPNM 필드 사용)
            work_type = claim_data.get('claim_type', '선택근무제')
            st.metric(
                "근무 형태",
                work_type,
                ""
            )
        
        with col2:
            st.metric(
                "데이터 신뢰도",
                f"{analysis_result['data_quality']['overall_quality_score']}%",
                "1.5%"
            )
        
        with col3:
            # 이동 시간 추가
            movement_hours = work_analysis.get('work_breakdown', {}).get('movement', 0)
            st.metric(
                "이동 시간",
                f"{movement_hours:.1f}h",
                ""
            )
        
        with col4:
            # 휴식 시간 추가
            rest_hours = work_analysis.get('work_breakdown', {}).get('rest', 0)
            st.metric(
                "휴식 시간",
                f"{rest_hours:.1f}h",
                ""
            )
        
        with col5:
            # 집중근무 시간
            if 'activity_summary' in analysis_result:
                focused_minutes = analysis_result['activity_summary'].get('FOCUSED_WORK', 0)
                focused_hours = focused_minutes / 60
                st.metric(
                    "집중근무",
                    f"{focused_hours:.1f}h",
                    ""
                )
            else:
                st.metric("집중근무", "0.0h", "")
        
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
        st.markdown("""
        <div style="background: #f8f9fa; 
                    border-left: 3px solid #6c757d; 
                    padding: 0.8rem 1.2rem; 
                    border-radius: 0 6px 6px 0; 
                    margin: 1rem 0 0.5rem 0;">
            <h4 style="margin: 0; color: #495057; font-weight: 600; font-size: 1.1rem;">
                Detailed Analysis
            </h4>
        </div>
        """, unsafe_allow_html=True)
        
        # 탭으로 구분하여 표시
        tab1, tab2, tab3 = st.tabs(["교대근무", "효율성", "트렌드"])
        
        with tab1:
            self.render_shift_analysis(analysis_result)
        
        with tab2:
            self.render_efficiency_analysis(analysis_result)
        
        with tab3:
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
        
        # 실제 식사 데이터 사용 여부 표시
        if 'actual_meal_count' in meal_analysis:
            actual_count = meal_analysis['actual_meal_count']
            estimated_count = meal_analysis.get('estimated_meal_count', 0)
            if actual_count > 0:
                st.success(f"✅ 실제 식사 기록 {actual_count}건 / 추정 {estimated_count}건")
        
        for meal, data in meal_patterns.items():
            actual_indicator = ""
            if 'is_actual' in data and data['is_actual']:
                actual_indicator = " ✓"
            st.write(f"• {meal}: {data['frequency']}회, 평균 {data['avg_duration']}분{actual_indicator}")
    
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
    
    def render_attendance_info(self, attendance_data: pd.DataFrame):
        """근태 정보 표시"""
        st.markdown("### 📋 근태 정보")
        
        with st.expander("근태 상세 정보", expanded=True):
            for idx, row in attendance_data.iterrows():
                col1, col2, col3 = st.columns([2, 3, 2])
                
                with col1:
                    # 근태 유형과 상태
                    status_icon = "✅" if row.get('approval_status') == '완결' else "⏳"
                    st.write(f"**{row.get('attendance_name', '')}** {status_icon}")
                    st.caption(f"코드: {row.get('attendance_code', '')}")
                
                with col2:
                    # 기간 정보
                    start_date = row.get('start_date')
                    end_date = row.get('end_date')
                    if pd.notna(start_date) and pd.notna(end_date):
                        st.write(f"**기간**: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
                        st.write(f"**일수**: {row.get('attendance_days', 0)}일")
                    
                    # 시간 정보가 있는 경우
                    start_time = row.get('start_time')
                    end_time = row.get('end_time')
                    if pd.notna(start_time) and pd.notna(end_time):
                        st.write(f"**시간**: {start_time} ~ {end_time}")
                
                with col3:
                    # 결재 정보
                    st.write(f"**결재상태**: {row.get('approval_status', '')}")
                    if pd.notna(row.get('first_approver')):
                        st.caption(f"1차: {row.get('first_approver', '')}")
                    if pd.notna(row.get('second_approver')):
                        st.caption(f"2차: {row.get('second_approver', '')}")
                
                # 사유가 있는 경우
                if pd.notna(row.get('reason_detail')):
                    st.info(f"📝 **사유**: {row.get('reason_detail', '')}")
                
                if idx < len(attendance_data) - 1:
                    st.markdown("---")
    
    def render_activity_summary(self, analysis_result: dict):
        """활동별 시간 요약 패널 렌더링"""
        activity_summary = analysis_result['activity_summary']
        claim_data = analysis_result.get('claim_data', {})
        work_time_analysis = analysis_result.get('work_time_analysis', {})
        
        # 디버깅: activity_summary 전체 내용 출력
        self.logger.info(f"[render_activity_summary] activity_summary 전체 내용:")
        for activity_code, minutes in activity_summary.items():
            if minutes > 0:
                self.logger.info(f"  - {activity_code}: {minutes}분")
        
        # 주요 지표 계산 - 체류시간 사용
        total_minutes = analysis_result.get('total_hours', 0) * 60  # 체류시간을 분으로 변환
        
        # 작업시간 - work_time_analysis의 결과 우선 사용
        if 'actual_work_hours' in work_time_analysis:
            # 신뢰지수 계산기의 결과 사용
            actual_work_hours = work_time_analysis['actual_work_hours']
            work_minutes = actual_work_hours * 60
            self.logger.info(f"[render_activity_summary] work_time_analysis 사용: {actual_work_hours:.2f}시간")
        else:
            # 폴백: activity_summary에서 직접 계산
            work_codes = ['WORK', 'FOCUSED_WORK', 'EQUIPMENT_OPERATION', 'WORK_PREPARATION', 
                         'WORKING', 'MEETING', 'TRAINING']
            work_minutes = sum(activity_summary.get(code, 0) for code in work_codes)
            actual_work_hours = work_minutes / 60
            self.logger.info(f"[render_activity_summary] activity_summary에서 계산: {actual_work_hours:.2f}시간")
        
        # 식사시간 (모든 식사 활동 합계)
        meal_codes = ['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL']
        meal_minutes = sum(activity_summary.get(code, 0) for code in meal_codes)
        
        # 실제 식사 데이터에서 직접 계산
        meal_data = self.get_meal_data(analysis_result.get('employee_id'), analysis_result.get('analysis_date'))
        if meal_data is not None and not meal_data.empty:
            # 실제 식사별로 시간 계산
            calculated_meal_minutes = 0
            date_column = '취식일시' if '취식일시' in meal_data.columns else 'meal_datetime'
            
            for _, meal in meal_data.iterrows():
                meal_type = meal.get('식사대분류', meal.get('meal_category', ''))
                배식구 = meal.get('배식구', '')
                테이크아웃 = meal.get('테이크아웃', '')
                
                # 배식구 기준 테이크아웃 판단
                is_takeout = False
                if 배식구:
                    if any(keyword in str(배식구).lower() for keyword in ['테이크아웃', 'takeout', 'take out', 'to go']):
                        is_takeout = True
                if str(테이크아웃).lower() in ['y', 'yes', '1', 'true']:
                    is_takeout = True
                
                if is_takeout:
                    # 테이크아웃은 10분으로 계산
                    calculated_meal_minutes += 10
                    self.logger.info(f"[render_activity_summary] 테이크아웃 식사: 10분")
                else:
                    # 일반 식사는 30분으로 계산
                    calculated_meal_minutes += 30
                    self.logger.info(f"[render_activity_summary] 일반 식사: 30분")
            
            self.logger.info(f"[render_activity_summary] 식사 데이터 기준 총 식사시간: {calculated_meal_minutes}분")
            # 실제 식사 데이터 기준으로 사용
            meal_minutes = calculated_meal_minutes
        
        # 디버깅: 식사시간 계산 상세
        self.logger.info(f"[render_activity_summary] 식사시간 계산:")
        for code in meal_codes:
            if code in activity_summary:
                self.logger.info(f"  - {code}: {activity_summary.get(code, 0):.1f}분")
        self.logger.info(f"  - 총 식사시간: {meal_minutes:.1f}분 = {meal_minutes/60:.2f}시간")
        
        # 이동시간 (출퇴근 제외)
        movement_minutes = activity_summary.get('MOVEMENT', 0)
        self.logger.info(f"🔍 MOVEMENT 시간 분석: {movement_minutes:.1f}분 = {movement_minutes/60:.2f}시간")
        
        # MOVEMENT로 분류된 세그먼트들의 상세 분석
        if hasattr(analysis_result, 'get') and 'activity_segments' in analysis_result:
            movement_segments = [seg for seg in analysis_result['activity_segments'] 
                               if seg.get('activity_code') == 'MOVEMENT']
            if movement_segments:
                self.logger.info(f"🔍 MOVEMENT 세그먼트 수: {len(movement_segments)}개")
                total_movement_from_segments = sum(seg.get('duration_minutes', 0) for seg in movement_segments)
                self.logger.info(f"🔍 세그먼트 기반 MOVEMENT 시간: {total_movement_from_segments:.1f}분")
                
                # 상위 5개 MOVEMENT 세그먼트 로깅
                sorted_segments = sorted(movement_segments, key=lambda x: x.get('duration_minutes', 0), reverse=True)
                for i, seg in enumerate(sorted_segments[:5]):
                    self.logger.info(f"🔍 MOVEMENT #{i+1}: {seg.get('duration_minutes', 0):.1f}분 @ {seg.get('location', 'N/A')} ({seg.get('start_time', 'N/A')})")
        
        # 휴식시간
        rest_codes = ['REST', 'FITNESS']
        rest_minutes = sum(activity_summary.get(code, 0) for code in rest_codes)
        
        # 출퇴근 시간
        commute_in_minutes = activity_summary.get('COMMUTE_IN', 0)
        commute_out_minutes = activity_summary.get('COMMUTE_OUT', 0)
        commute_minutes = commute_in_minutes + commute_out_minutes
        
        # 기타시간 (체류시간에서 다른 모든 활동 시간을 뺀 것)
        accounted_minutes = work_minutes + meal_minutes + movement_minutes + rest_minutes + commute_minutes
        other_minutes = total_minutes - accounted_minutes
        if other_minutes < 0:
            other_minutes = 0
        
        # 비업무시간 (비근무 + 휴식)
        non_work_minutes = activity_summary.get('NON_WORK', 0) + activity_summary.get('REST', 0)
        
        # 근태기록시간
        if claim_data:
            claim_hours = claim_data.get('claim_hours', 0)
            claim_minutes = claim_hours * 60
        else:
            claim_hours = 0
            claim_minutes = 0
        
        # actual_work_hours는 위에서 이미 계산됨
        
        # 작업시간 + 식사시간이 체류시간을 초과하는 경우 조정
        if (work_minutes + meal_minutes) > total_minutes:
            # 체류시간에서 식사시간을 먼저 보장하고 남은 시간을 작업시간으로
            work_minutes = max(0, total_minutes - meal_minutes - rest_minutes - movement_minutes)
            actual_work_hours = work_minutes / 60
            non_work_total = (meal_minutes + rest_minutes + movement_minutes + commute_minutes) / 60
            actual_work_hours = max(0, analysis_result['total_hours'] - non_work_total)
        
        # 업무 효율성 (실제 업무시간 / 근태기록시간)
        efficiency = (actual_work_hours * 60 / claim_minutes * 100) if claim_minutes > 0 else 0
        
        # 일일 활동 요약 스타일
        st.markdown("""
        <style>
        .summary-panel {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .summary-title {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 20px;
        }
        .summary-main {
            display: flex;
            align-items: center;
            margin-bottom: 30px;
        }
        .summary-bar {
            flex: 1;
            height: 40px;
            background: linear-gradient(to right, #2196F3 0%, #4CAF50 100%);
            border-radius: 20px;
            position: relative;
            overflow: hidden;
        }
        .summary-bar-fill {
            position: absolute;
            left: 0;
            top: 0;
            height: 100%;
            background-color: rgba(255, 255, 255, 0.3);
        }
        .summary-metrics {
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 15px;
            margin-bottom: 20px;
        }
        .metric-card {
            background-color: white;
            padding: 15px 10px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .metric-value {
            font-size: 28px;
            font-weight: bold;
            margin-bottom: 5px;
        }
        .metric-label {
            font-size: 14px;
            color: #666;
        }
        .metric-percent {
            font-size: 12px;
            color: #999;
        }
        .non-work-section {
            background-color: #ffebee;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #f44336;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Summary Panel

        st.markdown('<div class="summary-title">일일 활동 요약</div>', unsafe_allow_html=True)
        
        # 근무제 정보 및 컴플라이언스 체크
        work_compliance = self.check_work_hour_compliance(
            analysis_result['employee_id'], 
            analysis_result['analysis_date'], 
            actual_work_hours
        )
        
        # 근무제 정보와 주요 지표를 하나의 박스에 통합 표시
        actual_work_type = claim_data.get('claim_type', '선택근무제')
        work_type_color = '#4CAF50' if work_compliance['is_compliant'] else '#F44336'
        
        # 근무제 정보 박스
        st.markdown(f"""
            <div style="background: {work_type_color}22; padding: 12px; border-radius: 8px; margin-bottom: 15px;">
                <strong style="font-size: 1.1rem;">근무제:</strong> 
                <span style="font-size: 1.1rem;">{actual_work_type}</span>
                {' ✅' if work_compliance['is_compliant'] else ' ⚠️ ' + ', '.join(work_compliance['violations'])}
            </div>
        """, unsafe_allow_html=True)
        
        # 4개 메트릭 표시 (근무 형태 제외)
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("출근 시각", analysis_result['work_start'].strftime('%H:%M'))
        with col2:
            st.metric("퇴근 시각", analysis_result['work_end'].strftime('%H:%M'))
        with col3:
            # 체류시간을 HH:MM 형식으로 변환
            total_hours = analysis_result.get('total_hours', 0)
            hours = int(total_hours)
            minutes = int((total_hours - hours) * 60)
            st.metric("총 체류시간", f"{hours:02d}:{minutes:02d}")
        with col4:
            st.metric("태그 기록 수", f"{analysis_result['total_records']}건")
        
        st.markdown("---")  # 구분선 추가
        
        # 메인 진행 바
        col1, col2, col3, col4 = st.columns([1, 3, 1, 1])
        
        with col1:
            if claim_hours > 0:
                st.markdown(f"**근태기록시간:** {claim_hours:.1f}h")
            else:
                st.markdown("**근태기록시간:** 데이터 없음")
        
        with col2:
            # 진행 바 HTML
            bar_html = f"""
            <div class="summary-bar">
                <div class="summary-bar-fill" style="width: {min(efficiency, 100):.1f}%"></div>
            </div>
            """
            st.markdown(bar_html, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"**실제 업무시간:** <span style='color: #2196F3; font-weight: bold;'>{actual_work_hours:.1f}h</span>", 
                       unsafe_allow_html=True)
        
        with col4:
            if claim_minutes > 0:
                color = '#4CAF50' if efficiency >= 80 else '#FF9800' if efficiency >= 60 else '#F44336'
                st.markdown(f"**업무 효율성:** <span style='color: {color}; font-weight: bold;'>{efficiency:.1f}%</span>", 
                           unsafe_allow_html=True)
            else:
                st.markdown("**업무 효율성:** -", unsafe_allow_html=True)
        
        # 회의시간 계산
        meeting_codes = ['G3_MEETING', 'MEETING']
        meeting_minutes = sum(activity_summary.get(code, 0) for code in meeting_codes)
        
        # Knox PIMS 회의 시간 직접 보정 - 60분 회의가 5분으로 잘못 집계되는 문제 해결
        if 'raw_data' in analysis_result:
            raw_data = analysis_result['raw_data']
            if isinstance(raw_data, pd.DataFrame) and not raw_data.empty:
                # Knox PIMS 회의 데이터 찾기
                knox_meetings = raw_data[
                    (raw_data.get('source') == 'knox_pims') | 
                    (raw_data.get('DR_NO') == 'G3_KNOX_PIMS') |
                    ((raw_data.get('Tag_Code') == 'G3') & (raw_data.get('DR_NM', '').str.contains('Knox PIMS', na=False)))
                ]
                if not knox_meetings.empty:
                    knox_total_minutes = 0
                    for idx, meeting in knox_meetings.iterrows():
                        knox_duration = meeting.get('knox_duration')
                        if pd.notna(knox_duration) and knox_duration > 0:
                            knox_total_minutes += knox_duration
                            self.logger.info(f"Knox PIMS 회의 직접 보정: {meeting['datetime']} - {knox_duration}분")
                    
                    if knox_total_minutes > 0:
                        # 기존 회의시간에서 Knox PIMS 잘못 집계된 부분을 빼고 정확한 시간 추가
                        meeting_minutes = knox_total_minutes  # 간단히 Knox PIMS 시간으로 교체
                        self.logger.info(f"Knox PIMS 회의 시간 보정 완료: {knox_total_minutes}분")
                    else:
                        # Knox PIMS 데이터가 있지만 knox_duration이 없는 경우 60분으로 가정
                        meeting_minutes = 60
                        self.logger.info(f"Knox PIMS 회의 시간 기본값 적용: 60분")
        
        # 디버깅 로그 - 항상 표시
        self.logger.info(f"[render_activity_summary] 회의시간 집계:")
        for code in meeting_codes:
            minutes = activity_summary.get(code, 0)
            self.logger.info(f"  - {code}: {minutes}분")
        self.logger.info(f"  - 총 회의시간: {meeting_minutes}분 = {meeting_minutes/60:.1f}시간")
        
        # activity_summary의 모든 G3 관련 키 확인
        g3_related = {k: v for k, v in activity_summary.items() if 'G3' in k or 'MEETING' in k}
        if g3_related:
            self.logger.info(f"[render_activity_summary] G3/MEETING 관련 모든 키: {g3_related}")
        
        
        # 주요 지표들 - 6개 카드를 한 행으로
        st.markdown("<div class='summary-metrics'>", unsafe_allow_html=True)
        
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        with col1:
            # actual_work_hours를 사용하여 표시
            work_percent = (actual_work_hours * 60 / total_minutes * 100) if total_minutes > 0 else 0
            work_percent = min(work_percent, 100.0)  # 100% 초과 방지
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value" style="color: #2196F3;">{actual_work_hours:.1f}h</div>
                    <div class="metric-label">작업시간</div>
                    <div class="metric-percent">{work_percent:.1f}%</div>
                </div>
            """, unsafe_allow_html=True)
        
        with col2:
            meeting_percent = (meeting_minutes / total_minutes * 100) if total_minutes > 0 else 0
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value" style="color: #7B1FA2;">{meeting_minutes/60:.1f}h</div>
                    <div class="metric-label">회의시간</div>
                    <div class="metric-percent">{meeting_percent:.1f}%</div>
                </div>
            """, unsafe_allow_html=True)
        
        with col3:
            meal_percent = (meal_minutes / total_minutes * 100) if total_minutes > 0 else 0
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value" style="color: #FF9800;">{meal_minutes/60:.1f}h</div>
                    <div class="metric-label">식사시간</div>
                    <div class="metric-percent">{meal_percent:.1f}%</div>
                </div>
            """, unsafe_allow_html=True)
        
        with col4:
            movement_percent = (movement_minutes / total_minutes * 100) if total_minutes > 0 else 0
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value" style="color: #00BCD4;">{movement_minutes/60:.1f}h</div>
                    <div class="metric-label">이동시간</div>
                    <div class="metric-percent">{movement_percent:.1f}%</div>
                </div>
            """, unsafe_allow_html=True)
        
        with col5:
            rest_percent = (rest_minutes / total_minutes * 100) if total_minutes > 0 else 0
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value" style="color: #4CAF50;">{rest_minutes/60:.1f}h</div>
                    <div class="metric-label">휴식시간</div>
                    <div class="metric-percent">{rest_percent:.1f}%</div>
                </div>
            """, unsafe_allow_html=True)
        
        with col6:
            # 데이터 품질 점수 사용 (analyze_data_quality에서 계산된 값)
            data_quality_score = analysis_result.get('data_quality', {}).get('overall_quality_score', 80)
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value" style="color: #4CAF50;">{data_quality_score:.0f}%</div>
                    <div class="metric-label">데이터 신뢰도</div>
                    <div class="metric-percent">태그 품질</div>
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # 시간 합계 확인 (디버깅용 - 숨김 처리 가능)
        total_calculated = (actual_work_hours * 60 + meal_minutes + movement_minutes + 
                           rest_minutes + other_minutes + commute_minutes)
        if abs(total_calculated - total_minutes) > 1:  # 1분 이상 차이가 나는 경우
            st.markdown(f"""
                <div style="background-color: #ffecb3; padding: 10px; border-radius: 5px; margin-top: 10px;">
                    <small>
                    총 체류시간: {total_minutes/60:.1f}h ({total_minutes:.0f}분)<br>
                    계산된 합계: {total_calculated/60:.1f}h ({total_calculated:.0f}분)<br>
                    차이: {(total_minutes - total_calculated):.0f}분
                    </small>
                </div>
            """, unsafe_allow_html=True)
        
        # 비업무시간 섹션
        if non_work_minutes > 0:
            st.markdown(f"""
                <div class="non-work-section">
                    <strong style="color: #f44336;">비업무시간 ({non_work_minutes/60:.1f}h)</strong><br>
                    점심시간: {activity_summary.get('LUNCH', 0)/60:.1f}h | 
                    휴게시간: {activity_summary.get('REST', 0)/60:.1f}h | 
                    개인용무: {activity_summary.get('NON_WORK', 0)/60:.1f}h
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def render_timeline_view(self, analysis_result: dict):
        """시계열 타임라인 뷰 렌더링 - Gantt 차트 형태"""
        segments = analysis_result['activity_segments']
        
        # Y축 레이블 (improved_gantt_chart와 동일)
        y_labels = ['퇴근', '휴게', '식사', '회의', '이동', '작업', '준비', '출근']
        
        # 활동 코드를 Y축 위치로 매핑
        activity_to_y_pos = {
            'COMMUTE_IN': 7,  # 출근
            'WORK_PREPARATION': 6,  # 준비
            'WORK': 5,  # 작업
            'FOCUSED_WORK': 5,
            'EQUIPMENT_OPERATION': 5,
            'WORKING': 5,
            'MOVEMENT': 4,  # 이동
            'MEETING': 3,  # 회의
            'BREAKFAST': 2,  # 식사
            'LUNCH': 2,
            'DINNER': 2,
            'MIDNIGHT_MEAL': 2,
            'REST': 1,  # 휴게
            'FITNESS': 1,
            'NON_WORK': 1,
            'COMMUTE_OUT': 0,  # 퇴근
            'UNKNOWN': 4  # 기타는 이동과 같은 레벨
        }
        
        # Gantt 차트를 위한 Figure 생성
        fig = go.Figure()
        
        # 시간 범위 설정
        work_start = analysis_result['work_start']
        work_end = analysis_result['work_end']
        
        # 각 세그먼트를 막대로 추가
        for segment in segments:
            if pd.notna(segment['start_time']) and pd.notna(segment['end_time']):
                activity_code = segment.get('activity_code', 'UNKNOWN')
                
                # activity_type을 activity_code로 변환 (필요시)
                if activity_code in ['work', 'meeting', 'movement', 'rest', 'breakfast', 'lunch', 'dinner', 'midnight_meal', 'commute', 'non_work']:
                    type_to_code = {
                        'work': 'WORK',
                        'meeting': 'MEETING',
                        'movement': 'MOVEMENT',
                        'rest': 'REST',
                        'breakfast': 'BREAKFAST',
                        'lunch': 'LUNCH',
                        'dinner': 'DINNER',
                        'midnight_meal': 'MIDNIGHT_MEAL',
                        'commute': 'COMMUTE_IN',
                        'non_work': 'NON_WORK'
                    }
                    activity_code = type_to_code.get(activity_code, activity_code)
                
                # Y축 위치 결정
                y_pos = activity_to_y_pos.get(activity_code, 4)
                
                # 색상 결정
                color = get_activity_color(activity_code)
                
                # 호버 텍스트
                hover_text = (
                    f"<b>{get_activity_name(activity_code, 'ko')}</b><br>" +
                    f"시간: {segment['start_time'].strftime('%H:%M')} - {segment['end_time'].strftime('%H:%M')}<br>" +
                    f"위치: {segment.get('location', 'N/A')}<br>" +
                    f"지속: {segment.get('duration_minutes', 0):.0f}분"
                )
                
                # 막대 추가
                fig.add_trace(go.Scatter(
                    x=[segment['start_time'], segment['end_time']],
                    y=[y_pos, y_pos],
                    mode='lines',
                    line=dict(color=color, width=15),
                    hovertemplate=hover_text + "<extra></extra>",
                    showlegend=False
                ))
        
        # 레전드 추가 (실제 데이터에 있는 활동만)
        legend_added = set()
        for segment in segments:
            activity_code = segment.get('activity_code', 'UNKNOWN')
            if activity_code not in legend_added and pd.notna(segment['start_time']):
                # activity_type 변환
                if activity_code in ['work', 'meeting', 'movement', 'rest', 'breakfast', 'lunch', 'dinner', 'midnight_meal', 'commute', 'non_work']:
                    type_to_code = {
                        'work': 'WORK',
                        'meeting': 'MEETING',
                        'movement': 'MOVEMENT',
                        'rest': 'REST',
                        'breakfast': 'BREAKFAST',
                        'lunch': 'LUNCH',
                        'dinner': 'DINNER',
                        'midnight_meal': 'MIDNIGHT_MEAL',
                        'commute': 'COMMUTE_IN',
                        'non_work': 'NON_WORK'
                    }
                    activity_code = type_to_code.get(activity_code, activity_code)
                
                fig.add_trace(go.Scatter(
                    x=[None],
                    y=[None],
                    mode='markers',
                    marker=dict(size=10, color=get_activity_color(activity_code)),
                    name=get_activity_name(activity_code, 'ko'),
                    showlegend=True
                ))
                legend_added.add(activity_code)
        
        # 레이아웃 설정
        fig.update_layout(
            title="일일 활동 타임라인 (Gantt Chart)",
            height=600,
            xaxis=dict(
                title="시간",
                tickformat='%H:%M',
                dtick=3600000,  # 1시간 간격
                range=[work_start - timedelta(minutes=30), work_end + timedelta(minutes=30)],
                showgrid=True,
                gridcolor='rgba(200, 200, 200, 0.15)',  # 더 흐린 회색
                gridwidth=0.5
            ),
            yaxis=dict(
                title="",
                tickmode='array',
                tickvals=list(range(len(y_labels))),
                ticktext=y_labels,
                range=[-0.5, 7.5],
                showgrid=True,
                gridcolor='rgba(200, 200, 200, 0.2)',  # 매우 흐린 회색
                gridwidth=0.5
            ),
            plot_bgcolor='white',
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.3,
                xanchor="center",
                x=0.5
            ),
            hovermode='closest'
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
            'rest': self.colors['rest'],
            'non_work': '#FF6B6B'  # 빨간색 계열로 비근무 표시
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
            'rest': '휴식',
            'non_work': '비근무'
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
                
                # 테이크아웃 여부 확인
                is_takeout = seg.get('is_takeout', False)
                activity_name = get_activity_name(seg.get('activity_code', 'WORK'), 'ko')
                if is_takeout:
                    activity_name += ' (테이크아웃)'
                    
                segment_data.append({
                    '시작': start_str,
                    '종료': end_str,
                    '활동': activity_name,
                    '위치': seg['location'],
                    '체류시간': f"{int(seg.get('duration_minutes', 0))}분"
                })
            
            df_segments = pd.DataFrame(segment_data)
            st.dataframe(df_segments, use_container_width=True, hide_index=True)
    
    def render_detailed_records(self, analysis_result: dict):
        """상세 태그 기록 렌더링"""
        # daily_analysis가 있으면 우선 사용 (classify_activities의 결과)
        if 'daily_analysis' in analysis_result and not analysis_result['daily_analysis'].empty:
            raw_data = analysis_result['daily_analysis'].copy()
        else:
            raw_data = analysis_result['raw_data'].copy()
        
        # Tag_Code 컬럼 초기화
        if 'Tag_Code' not in raw_data.columns:
            raw_data['Tag_Code'] = None
        
        # 식사 데이터와 병합
        employee_id = analysis_result.get('employee_id')
        selected_date = analysis_result.get('analysis_date')
        
        # 식사 태그를 독립적인 행으로 추가
        if employee_id and selected_date:
            meal_data = self.get_meal_data(employee_id, selected_date)
            if meal_data is not None and not meal_data.empty:
                # 식사 데이터 키 컬럼 확인
                date_column = 'meal_datetime' if 'meal_datetime' in meal_data.columns else '취식일시'
                category_column = 'meal_category' if 'meal_category' in meal_data.columns else '식사대분류'
                restaurant_column = 'restaurant' if 'restaurant' in meal_data.columns else '식당명'
                takeout_column = 'is_takeout' if 'is_takeout' in meal_data.columns else '테이크아웃'
                
                # 식사 데이터 타임스탬프 변환
                if date_column in meal_data.columns:
                    meal_data[date_column] = pd.to_datetime(meal_data[date_column])
                    
                    # 각 식사 레코드를 독립적인 행으로 추가
                    meal_rows = []
                    for _, meal in meal_data.iterrows():
                        meal_time = meal[date_column]
                        meal_category = meal.get(category_column, '')
                        
                        # 식사 태그 행 생성
                        # 세부 식당 정보 가져오기 - 배식구가 있으면 우선 사용
                        service_point_column = '배식구' if '배식구' in meal_data.columns else 'service_point'
                        restaurant_info = meal.get(service_point_column, meal.get(restaurant_column, ''))
                        
                        # 테이크아웃 판단: meal_data의 컬럼 또는 위치명에서 판단
                        takeout_from_data = meal.get(takeout_column, False)
                        takeout_from_location = '테이크아웃' in str(restaurant_info)
                        is_takeout = takeout_from_data or takeout_from_location
                        
                        meal_row = {
                            'datetime': meal_time,
                            'DR_NO': '',
                            'DR_NM': restaurant_info,
                            'INOUT_GB': '식사',  # 식사로 표시
                            'activity_code': '',
                            'activity_type': 'meal',
                            'work_area_type': 'N',
                            'work_status': 'M',
                            'activity_label': '',
                            'Tag_Code': 'M2' if is_takeout else 'M1',  # M1/M2 태그 추가
                            'duration_minutes': 10 if is_takeout else None,  # 테이크아웃은 10분 고정
                            'meal_type': '',
                            'meal_time': '',  # 여기는 비워둠 - 나중에 duration으로 채움
                            'restaurant': restaurant_info,
                            'is_takeout': is_takeout
                        }
                        
                        # 식사 종류 매핑
                        if meal_category == '조식':
                            meal_row['activity_code'] = 'BREAKFAST'
                            meal_row['meal_type'] = 'breakfast'
                        elif meal_category == '중식':
                            meal_row['activity_code'] = 'LUNCH'
                            meal_row['meal_type'] = 'lunch'
                        elif meal_category == '석식':
                            meal_row['activity_code'] = 'DINNER'
                            meal_row['meal_type'] = 'dinner'
                        elif meal_category == '야식':
                            meal_row['activity_code'] = 'MIDNIGHT_MEAL'
                            meal_row['meal_type'] = 'midnight'
                        
                        meal_rows.append(meal_row)
                    
                    # 식사 태그를 raw_data에 추가
                    if meal_rows:
                        meal_df = pd.DataFrame(meal_rows)
                        raw_data = pd.concat([raw_data, meal_df], ignore_index=True)
                        # 시간순 정렬
                        raw_data = raw_data.sort_values('datetime').reset_index(drop=True)
                        
                        # 식사 태그의 duration 계산 (다음 태그까지의 시간)
                        for i in range(len(raw_data) - 1):
                            if pd.isna(raw_data.iloc[i]['duration_minutes']):
                                # 다음 태그까지의 시간 계산
                                duration = (raw_data.iloc[i+1]['datetime'] - raw_data.iloc[i]['datetime']).total_seconds() / 60
                                raw_data.at[raw_data.index[i], 'duration_minutes'] = duration
                        
                        # 마지막 행의 duration이 None인 경우 기본값 설정
                        if pd.isna(raw_data.iloc[-1]['duration_minutes']):
                            # 테이크아웃이면 10분, 아니면 30분 (식당 식사는 실제 다음 태그까지의 시간으로 계산됨)
                            is_takeout = raw_data.iloc[-1].get('is_takeout', False)
                            raw_data.at[raw_data.index[-1], 'duration_minutes'] = 10 if is_takeout else 30
        
        # ========== Tag_Code 할당 시작 ==========
        self.logger.info("===== Tag_Code 할당 시작 =====")
        
        # 1단계: 기본 태그들 - DR_NM과 마스터의 게이트명 매칭
        tag_location_master = self.get_tag_location_master()
        if tag_location_master is not None and not tag_location_master.empty:
            # DR_NO와 DR_NM으로 조인 준비
            raw_data['DR_NO_str'] = raw_data['DR_NO'].astype(str)
            if 'DR_NO' in tag_location_master.columns:
                tag_location_master['DR_NO_str'] = tag_location_master['DR_NO'].astype(str)
            elif '기기번호' in tag_location_master.columns:
                tag_location_master['DR_NO_str'] = tag_location_master['기기번호'].astype(str)
            
            # 조인할 컬럼 선택 (Tag_Code, INOUT_GB 추가)
            join_columns = ['DR_NO_str', 'INOUT_GB', '위치', '표기명', '근무구역여부', '근무', '라벨링', 'Tag_Code']
            available_join_columns = [col for col in join_columns if col in tag_location_master.columns]
            
            # INOUT_GB 값 표준화
            if 'INOUT_GB' in raw_data.columns and 'INOUT_GB' in tag_location_master.columns:
                # 데이터와 마스터의 INOUT_GB 값 형식 확인
                data_inout_values = set(raw_data['INOUT_GB'].dropna().unique())
                master_inout_values = set(tag_location_master['INOUT_GB'].dropna().unique())
                
                self.logger.info(f"데이터 INOUT_GB 값: {data_inout_values}")
                self.logger.info(f"마스터 INOUT_GB 값: {master_inout_values}")
                
                # 값 형식이 다른 경우 변환
                if '입문' in data_inout_values and 'IN' in master_inout_values:
                    # 한글 -> 영문 변환
                    raw_data['INOUT_GB'] = raw_data['INOUT_GB'].replace({'입문': 'IN', '출문': 'OUT'})
                    self.logger.info("INOUT_GB 값 변환: 입문->IN, 출문->OUT")
                elif 'IN' in data_inout_values and '입문' in master_inout_values:
                    # 영문 -> 한글 변환
                    raw_data['INOUT_GB'] = raw_data['INOUT_GB'].replace({'IN': '입문', 'OUT': '출문'})
                    self.logger.info("INOUT_GB 값 변환: IN->입문, OUT->출문")
            
            # 🚨 DR_NM 기반 매칭 시도 (게이트명, 표기명 순서로)
            Tag_Code_matched = False
            
            # 1. DR_NM과 표기명으로 매칭 시도
            if 'DR_NM' in raw_data.columns and '표기명' in tag_location_master.columns:
                self.logger.info("🔍 DR_NM과 표기명으로 Tag_Code 조회 시도")
                
                # 샘플 데이터 로깅
                self.logger.info(f"raw_data DR_NM 샘플: {raw_data['DR_NM'].head(3).tolist()}")
                self.logger.info(f"마스터 표기명 샘플: {tag_location_master['표기명'].head(3).tolist()}")
                
                # 필요한 컬럼 확인
                display_columns = ['표기명', 'Tag_Code']
                for col in ['위치', '게이트명', '근무구역여부', '근무', '라벨링', 'INOUT_GB']:
                    if col in tag_location_master.columns:
                        display_columns.append(col)
                
                # DR_NM과 표기명으로 매칭
                raw_data_temp = raw_data.merge(
                    tag_location_master[display_columns],
                    left_on='DR_NM',
                    right_on='표기명',
                    how='left',
                    suffixes=('', '_display')
                )
                
                # 표기명으로 매칭된 경우 Tag_Code 업데이트
                display_matched = raw_data_temp['Tag_Code_display'].notna()
                if display_matched.any():
                    raw_data.loc[display_matched, 'Tag_Code'] = raw_data_temp.loc[display_matched, 'Tag_Code_display']
                    self.logger.info(f"✅ 표기명 매칭으로 {display_matched.sum()}건의 Tag_Code 찾음")
                    Tag_Code_matched = True
                    
                    # 매칭된 다른 정보도 업데이트
                    for col in ['위치', '게이트명', '근무구역여부', '근무', '라벨링']:
                        if f'{col}_display' in raw_data_temp.columns:
                            raw_data.loc[display_matched, col] = raw_data_temp.loc[display_matched, f'{col}_display']
            
            # 2. 표기명으로 못 찾은 경우 게이트명으로 매칭 시도
            if not Tag_Code_matched and 'DR_NM' in raw_data.columns and '게이트명' in tag_location_master.columns:
                self.logger.info("🔍 DR_NM과 게이트명으로 Tag_Code 조회 시도")
                
                # 필요한 컬럼 확인
                gate_columns = ['게이트명', 'Tag_Code']
                for col in ['위치', '표기명', '근무구역여부', '근무', '라벨링']:
                    if col in tag_location_master.columns:
                        gate_columns.append(col)
                
                # DR_NM과 게이트명으로 매칭
                raw_data_temp = raw_data.merge(
                    tag_location_master[gate_columns],
                    left_on='DR_NM',
                    right_on='게이트명',
                    how='left',
                    suffixes=('', '_gate')
                )
                
                # 게이트명으로 매칭된 경우 Tag_Code 업데이트
                gate_matched = raw_data_temp['Tag_Code_gate'].notna()
                if gate_matched.any():
                    # Tag_Code가 없는 것만 업데이트
                    no_tag_mask = raw_data['Tag_Code'].isna() if 'Tag_Code' in raw_data.columns else pd.Series([True] * len(raw_data))
                    update_mask = gate_matched & no_tag_mask
                    
                    raw_data.loc[update_mask, 'Tag_Code'] = raw_data_temp.loc[update_mask, 'Tag_Code_gate']
                    self.logger.info(f"✅ 게이트명 매칭으로 {update_mask.sum()}건의 Tag_Code 찾음")
                    
                    # 매칭된 다른 정보도 업데이트
                    for col in ['위치', '표기명', '근무구역여부', '근무', '라벨링']:
                        if f'{col}_gate' in raw_data_temp.columns:
                            raw_data.loc[update_mask, col] = raw_data_temp.loc[update_mask, f'{col}_gate']
            
            # DR_NO + INOUT_GB 조합으로 추가 매칭 (게이트명으로 못 찾은 경우)
            if 'INOUT_GB' in raw_data.columns and 'INOUT_GB' in tag_location_master.columns:
                # Tag_Code가 없는 경우만 DR_NO + INOUT_GB로 조인
                missing_tag_mask = raw_data['Tag_Code'].isna() if 'Tag_Code' in raw_data.columns else pd.Series([True] * len(raw_data))
                
                if missing_tag_mask.any():
                    self.logger.info(f"🔍 남은 {missing_tag_mask.sum()}건에 대해 DR_NO + INOUT_GB 조합으로 Tag_Code 조회")
                    raw_data_missing = raw_data[missing_tag_mask].merge(
                        tag_location_master[available_join_columns],
                        on=['DR_NO_str', 'INOUT_GB'],
                        how='left',
                        suffixes=('', '_master')
                    )
                    
                    # 업데이트
                    raw_data.loc[missing_tag_mask] = raw_data_missing
                
                # 조회 결과 확인
                Tag_Code_found = raw_data['Tag_Code'].notna().sum()
                Tag_Code_missing = raw_data['Tag_Code'].isna().sum()
                self.logger.info(f"✅ Tag_Code 조회 결과: 찾음 {Tag_Code_found}건, 못찾음 {Tag_Code_missing}건")
                
                # 이동 태그 Tag_Code 확인
                movement_tags = raw_data[raw_data['DR_NO_str'].str.startswith('701', na=False)].head(5)
                if not movement_tags.empty:
                    self.logger.info("이동 태그 Tag_Code 조회 결과:")
                    for idx, row in movement_tags.iterrows():
                        self.logger.info(f"  - DR_NO={row['DR_NO_str']}, INOUT_GB={row.get('INOUT_GB', 'N/A')}, Tag_Code={row.get('Tag_Code', 'N/A')}")
            else:
                # INOUT_GB가 없으면 DR_NO만으로 조인 (fallback)
                raw_data = raw_data.merge(
                    tag_location_master[available_join_columns],
                    on='DR_NO_str',
                    how='left',
                    suffixes=('', '_master')
                )
                self.logger.info(f"🔍 DR_NO만으로 Tag_Code 조회 (fallback)")
            
            # 마스터 정보로 업데이트
            if '표기명' in raw_data.columns:
                raw_data['DR_NM'] = raw_data['표기명'].fillna(raw_data['DR_NM'])
            if '위치' in raw_data.columns:
                raw_data['location_info'] = raw_data['위치']
            if 'Tag_Code' in raw_data.columns:
                raw_data['Tag_Code'] = raw_data['Tag_Code']  # Tag_Code 우선 사용
        
        # ========== Tag_Code 체계적 할당 ==========
        self.logger.info("===== Tag_Code 체계적 할당 시작 =====")
        
        # 1단계 완료 로그
        basic_tag_count = raw_data['Tag_Code'].notna().sum() - raw_data[raw_data['Tag_Code'].isin(['M1', 'M2'])].shape[0]
        self.logger.info(f"✅ 1단계: 기본 태그 Tag_Code 할당 완료 - {basic_tag_count}건")
        
        # 2단계: 식사 데이터는 이미 M1/M2가 할당되어 있음
        meal_count = raw_data[raw_data['Tag_Code'].isin(['M1', 'M2'])].shape[0]
        self.logger.info(f"✅ 2단계: 식사 데이터 Tag_Code 확인 - M1/M2: {meal_count}건")
        
        # 3단계: 장비 데이터 - O 태그 할당
        # source 컬럼이 없을 수 있으므로 체크
        if 'source' in raw_data.columns:
            equipment_mask = (
                raw_data['DR_NO'].str.startswith('O.', na=False) | 
                raw_data['source'].str.contains('equipment', na=False)
            )
        else:
            equipment_mask = raw_data['DR_NO'].str.startswith('O.', na=False)
        
        equipment_no_tag = equipment_mask & raw_data['Tag_Code'].isna()
        if equipment_no_tag.any():
            raw_data.loc[equipment_no_tag, 'Tag_Code'] = 'O'
            self.logger.info(f"✅ 3단계: 장비 데이터 Tag_Code 할당 - O: {equipment_no_tag.sum()}건")
        
        # 4단계: Knox 데이터 처리
        if 'source' in raw_data.columns:
            # Knox 회의(PIMS) - G4 태그
            knox_pims_mask = (
                (raw_data['source'].str.contains('knox_pims', na=False) | 
                 raw_data['DR_NO'].str.contains('G3_KNOX_PIMS', na=False)) & 
                raw_data['Tag_Code'].isna()
            )
            if knox_pims_mask.any():
                raw_data.loc[knox_pims_mask, 'Tag_Code'] = 'G3'
                self.logger.info(f"✅ 4단계: Knox PIMS(회의) Tag_Code 할당 - G3: {knox_pims_mask.sum()}건")
            
            # Knox 결재승인 - O 태그
            knox_approval_mask = (
                (raw_data['source'].str.contains('knox_approval', na=False) | 
                 raw_data['DR_NO'].str.contains('O_KNOX_APPROVAL', na=False)) & 
                raw_data['Tag_Code'].isna()
            )
            if knox_approval_mask.any():
                raw_data.loc[knox_approval_mask, 'Tag_Code'] = 'O'
                self.logger.info(f"✅ 4단계: Knox Approval(결재) Tag_Code 할당 - O: {knox_approval_mask.sum()}건")
            
            # Knox 메일 - O 태그
            knox_mail_mask = (
                (raw_data['source'].str.contains('knox_mail', na=False) | 
                 raw_data['DR_NO'].str.contains('O_KNOX_MAIL', na=False)) & 
                raw_data['Tag_Code'].isna()
            )
            if knox_mail_mask.any():
                raw_data.loc[knox_mail_mask, 'Tag_Code'] = 'O'
                self.logger.info(f"✅ 4단계: Knox Mail Tag_Code 할당 - O: {knox_mail_mask.sum()}건")
        
        # 최종 검증
        total_records = len(raw_data)
        with_Tag_Code = raw_data['Tag_Code'].notna().sum()
        without_Tag_Code = raw_data['Tag_Code'].isna().sum()
        self.logger.info(f"===== Tag_Code 할당 완료 =====")
        self.logger.info(f"전체: {total_records}건, Tag_Code 있음: {with_Tag_Code}건, Tag_Code 없음: {without_Tag_Code}건")
        
        # Tag_Code가 없는 레코드 샘플 확인
        if without_Tag_Code > 0:
            missing_sample = raw_data[raw_data['Tag_Code'].isna()].head(5)
            self.logger.warning("⚠️ Tag_Code가 없는 레코드 샘플:")
            for idx, row in missing_sample.iterrows():
                self.logger.warning(f"  - DR_NO: {row.get('DR_NO', 'N/A')}, DR_NM: {row.get('DR_NM', 'N/A')}, INOUT_GB: {row.get('INOUT_GB', 'N/A')}, source: {row.get('source', 'N/A')}")
        else:
            self.logger.info(f"✅ Tag_Code 조회 성공: {len(raw_data)}건 모두 매핑됨")
        
        # 🚨 Tag_Code 기반 work_area_type 올바른 매핑
        raw_data['work_area_type'] = 'Y'  # 기본값: 근무구역
        raw_data.loc[raw_data['Tag_Code'].str.startswith('N', na=False), 'work_area_type'] = 'N'  # 비근무구역
        raw_data.loc[raw_data['Tag_Code'].str.startswith('T', na=False), 'work_area_type'] = 'T'  # 이동구간
        raw_data.loc[raw_data['Tag_Code'].str.startswith('G', na=False), 'work_area_type'] = 'Y'  # 근무구역
        raw_data.loc[raw_data['Tag_Code'].str.startswith('M', na=False), 'work_area_type'] = 'Y'  # 식사구역 = 근무구역
        
        # Tag_Code는 마스터 데이터 기준으로만 사용 - 임의 변경 금지
        if '근무구역여부' in raw_data.columns:
            # work_area_type이 설정되지 않은 것만 업데이트
            no_work_area_mask = raw_data['work_area_type'].isna() | (raw_data['work_area_type'] == 'Y')
            raw_data.loc[no_work_area_mask, 'work_area_type'] = raw_data.loc[no_work_area_mask, '근무구역여부'].fillna('Y')
            if '근무' in raw_data.columns:
                raw_data['work_status'] = raw_data['근무'].fillna(raw_data.get('work_status', ''))
            if '라벨링' in raw_data.columns:
                raw_data['activity_label'] = raw_data['라벨링'].fillna(raw_data.get('activity_label', ''))
        
        # 표시할 컬럼 선택 ('활동분류' 컬럼과 Tag_Code 추가)
        display_columns = ['datetime', 'DR_NO', 'DR_NM', 'location_info', 'INOUT_GB', 'Tag_Code', 'activity_code', '활동분류',
                          'work_area_type', 'work_status', 'activity_label', 'duration_minutes', 
                          'meal_time', 'restaurant']
        
        # 일부 컬럼이 없을 수 있으므로 확인
        available_columns = [col for col in display_columns if col in raw_data.columns]
        
        # 컬럼명 한글화
        column_names = {
            'datetime': '시각',
            'DR_NO': '게이트 번호',
            'DR_NM': '위치',
            'location_info': '구역/동/층',
            'INOUT_GB': '태그종류',  # 입/출에서 태그종류로 변경
            'Tag_Code': 'Tag_Code',  # Tag_Code는 그대로 표시
            'activity_code': '활동코드',
            '활동분류': '활동분류',  # 이미 한글인 경우 그대로 사용
            'activity_type': '활동분류',
            'work_area_type': '구역코드',  # 구역코드 (Y/N/T)
            'work_status': '공간분류',
            'activity_label': '허용활동',
            'duration_minutes': '체류시간(분)',
            'meal_time': '식사시간',
            'restaurant': '식당'
        }
        
        # 데이터프레임 준비
        df_display = raw_data[available_columns].copy()
        df_display['datetime'] = df_display['datetime'].dt.strftime('%H:%M:%S')
        # None 값을 0으로 처리한 후 반올림
        df_display['duration_minutes'] = df_display['duration_minutes'].fillna(0).round(1)
        
        # 원본 activity_code를 먼저 저장 (모든 경우에 대비)
        original_codes = None
        if 'activity_code' in df_display.columns:
            original_codes = df_display['activity_code'].copy()
        
        # 활동분류 필드가 있으면 그것을 사용, 없으면 activity_code를 한글로 변환
        if '활동분류' in df_display.columns and df_display['활동분류'].notna().any():
            # 이미 한글로 설정된 활동봠6류 필드가 있으면 그것을 사용
            self.logger.info("활동분류 필드를 사용")
            # 테이크아웃 표시만 추가
            def add_takeout_indicator(row):
                activity = row['활동분류']
                # 식사 태그이고 테이크아웃인 경우만 (T) 추가
                if (activity in ['조식', '중식', '석식', '야식'] and
                    'is_takeout' in row and row['is_takeout'] and
                    'INOUT_GB' in row and row['INOUT_GB'] == '식사'):
                    activity += '(T)'
                return activity
            
            df_display['activity_code'] = df_display.apply(add_takeout_indicator, axis=1)
        else:
            # 활동분류 필드가 없으면 activity_code를 한글로 변환
            self.logger.info("activity_code를 한글로 변환")
            
            if original_codes is not None:
                def format_activity_code(row):
                    # 원본 activity_code 가져오기
                    idx = row.name
                    if idx < len(original_codes):
                        original_code = original_codes.iloc[idx]
                    else:
                        original_code = row['activity_code']
                    
                    activity = get_activity_name(original_code, 'ko')
                    
                    # 식사 태그이고 테이크아웃인 경우만 (T) 추가
                    if (original_code in ['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL'] and
                        'is_takeout' in row and row['is_takeout'] and
                        'INOUT_GB' in row and row['INOUT_GB'] == '식사'):
                        activity += '(T)'
                    
                    return activity
                
                df_display['activity_code'] = df_display.apply(format_activity_code, axis=1)
        
        # 입/출 컬럼을 태그 종류로 변환
        if 'INOUT_GB' in df_display.columns:
            # 태그 코드와 위치에 따른 태그 종류 설정
            if 'Tag_Code' in df_display.columns:
                # G3: 협업공간 -> 회의
                df_display.loc[df_display['Tag_Code'] == 'G3', 'INOUT_GB'] = '회의'
                # N1, N2: 휴게/복지공간 -> 휴게
                df_display.loc[df_display['Tag_Code'].isin(['N1', 'N2']), 'INOUT_GB'] = '휴게'
            
            # 장비실 태그
            if 'DR_NM' in df_display.columns:
                equipment_mask = df_display['DR_NM'].str.contains('EQUIPMENT|장비|기계실', case=False, na=False)
                df_display.loc[equipment_mask, 'INOUT_GB'] = '장비'
            
            # O 태그 처리
            o_tag_mask = df_display['INOUT_GB'] == 'O'
            if o_tag_mask.any():
                df_display.loc[o_tag_mask, 'INOUT_GB'] = '장비사용'
        
        # 식사 정보 처리와 테이크아웃 통합
        if 'meal_type' in df_display.columns:
            # 식사 종류 한글화
            meal_type_map = {'breakfast': '조식', 'lunch': '중식', 'dinner': '석식', 'midnight': '야식'}
            df_display['meal_type'] = df_display['meal_type'].map(meal_type_map).fillna('')
        
        if 'meal_time' in df_display.columns:
            # 식사 시간을 체류시간으로 표시
            for idx, row in df_display.iterrows():
                if row['INOUT_GB'] == '식사' and pd.notna(row['duration_minutes']):
                    # 테이크아웃 여부 확인
                    is_takeout = ('is_takeout' in raw_data.columns and raw_data.loc[idx, 'is_takeout']) or '테이크아웃' in str(row.get('DR_NM', ''))
                    if is_takeout:
                        df_display.at[idx, 'meal_time'] = '10'  # 테이크아웃은 10분 고정
                    else:
                        # 식당 식사는 체류시간 표시 (최대 60분)
                        duration = row['duration_minutes']
                        if duration > 60:
                            duration = 60
                        df_display.at[idx, 'meal_time'] = f"{duration:.1f}"
                else:
                    df_display.at[idx, 'meal_time'] = ''
        
        if 'restaurant' in df_display.columns:
            # 식당 이름 축약 및 세부 정보 유지
            def format_restaurant(x):
                if pd.notna(x) and x:
                    # SBL 제거하고 세부 정보 유지
                    x = x.replace('SBL ', '')
                    # 비어있는 경우 빈 문자열로
                    return x if x else ''
                return ''
            
            df_display['restaurant'] = df_display['restaurant'].apply(format_restaurant)
            
            # 식사 태그가 아닌 경우 식당명 비워두기
            non_meal_mask = df_display['INOUT_GB'] != '식사'
            df_display.loc[non_meal_mask, 'restaurant'] = ''
        
        # 테이크아웃 여부 표시 - 식사 태그에만 표시
        if 'is_takeout' in df_display.columns:
            # 식사 태그가 아닌 경우 테이크아웃 비워두기
            non_meal_mask = df_display['INOUT_GB'] != '식사'
            df_display.loc[non_meal_mask, 'is_takeout'] = ''
            
            # 식사 태그인 경우만 체크 표시
            meal_mask = df_display['INOUT_GB'] == '식사'
            df_display.loc[meal_mask, 'is_takeout'] = df_display.loc[meal_mask, 'is_takeout'].apply(
                lambda x: '✓' if x else ''
            )
        
        # 구역 타입 표시 - work_area_type이 이미 설정되어 있으므로 추가 변경 불필요
        # work_area_type은 이미 Tag_Code로 설정되어 있음 (line 4174)
        if 'work_area_type' in df_display.columns:
            # work_area_type이 제대로 설정되었는지 확인
            unique_codes = df_display['work_area_type'].unique()
            self.logger.info(f"work_area_type 값 확인: {unique_codes}")
            
            # 특정 시간대 디버깅
            if '07:35' in df_display['datetime'].values:
                problem_row = df_display[df_display['datetime'].str.contains('07:35')]
                if not problem_row.empty:
                    self.logger.info(f"07:35 데이터 확인: work_area_type={problem_row['work_area_type'].values[0]}, DR_NM={problem_row['위치'].values[0]}")
        
        # 상태 한글 변환 (확장) - 현재 activity_code 기반으로 상태 업데이트
        if 'work_status' in df_display.columns:
            # 활동분류 필드가 있으면 그것을 매핑, 없으면 원본 activity_code 사용
            for idx in df_display.index:
                # 현재 활동 분류 확인
                if '활동분류' in df_display.columns and pd.notna(df_display.loc[idx, '활동분류']):
                    # 활동분류를 기반으로 activity_code 매핑
                    activity_name = df_display.loc[idx, '활동분류']
                    # 한글명을 activity_code로 역매핑
                    activity_mapping = {
                        '출근': 'COMMUTE_IN',
                        '퇴근': 'COMMUTE_OUT',
                        '근무': 'WORK',
                        '작업': 'WORK',
                        '준비': 'WORK_PREPARATION',
                        '회의': 'MEETING',
                        '이동': 'MOVEMENT',
                        '조식': 'BREAKFAST',
                        '중식': 'LUNCH',
                        '석식': 'DINNER',
                        '야식': 'MIDNIGHT_MEAL',
                        '휴식': 'REST'
                    }
                    activity_code = activity_mapping.get(activity_name, 'WORK')
                elif original_codes is not None and idx < len(original_codes):
                    activity_code = original_codes.iloc[idx]
                else:
                    continue
                    
                # 근무 상태
                if activity_code in ['WORK', 'WORKING']:
                    df_display.loc[idx, 'work_status'] = '근무중'
                elif activity_code == 'FOCUSED_WORK':
                    df_display.loc[idx, 'work_status'] = '집중작업'
                elif activity_code == 'MEETING':
                    df_display.loc[idx, 'work_status'] = '회의중'
                elif activity_code == 'EQUIPMENT_OPERATION':
                    df_display.loc[idx, 'work_status'] = '장비조작'
                elif activity_code == 'WORK_PREPARATION':
                    df_display.loc[idx, 'work_status'] = '작업준비'
                # 이동 상태
                elif activity_code == 'MOVEMENT':
                    df_display.loc[idx, 'work_status'] = '이동중'
                elif activity_code == 'COMMUTE_IN':
                    df_display.loc[idx, 'work_status'] = '출근중'
                elif activity_code == 'COMMUTE_OUT':
                    df_display.loc[idx, 'work_status'] = '퇴근중'
                # 휴식 상태
                elif activity_code == 'REST':
                    df_display.loc[idx, 'work_status'] = '휴식중'
                elif activity_code in ['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL']:
                    df_display.loc[idx, 'work_status'] = '식사중'
                elif activity_code == 'FITNESS':
                    df_display.loc[idx, 'work_status'] = '운동중'
            else:
                # 기본 매핑
                status_map = {'W': '근무', 'M': '이동', 'N': '비근무'}
                df_display['work_status'] = df_display['work_status'].map(status_map).fillna(df_display['work_status'])
        
        df_display = df_display.rename(columns=column_names)
        
        # 필터링 옵션
        col1, col2 = st.columns(2)
        with col1:
            # 활동분류 컬럼이 존재하는지 확인
            if '활동분류' in df_display.columns:
                activity_filter = st.multiselect(
                    "활동 유형 필터",
                    options=df_display['활동분류'].unique(),
                    default=df_display['활동분류'].unique()
                )
            else:
                activity_filter = []
        
        with col2:
            location_filter = st.text_input("위치 검색", "")
        
        # 필터 적용
        if '활동분류' in df_display.columns and activity_filter:
            filtered_df = df_display[df_display['활동분류'].isin(activity_filter)]
        else:
            filtered_df = df_display
        if location_filter:
            filtered_df = filtered_df[filtered_df['위치'].str.contains(location_filter, case=False, na=False)]
        
        # 데이터 개수에 따라 높이 동적 설정 (행당 35px + 헤더 50px)
        dynamic_height = min(35 * len(filtered_df) + 50, 2000)  # 최대 2000px로 제한
        
        # 데이터 표시 (동적 높이 적용)
        st.dataframe(
            filtered_df, 
            use_container_width=True, 
            hide_index=True,
            height=dynamic_height
        )
        
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
        
        # 근무시간을 시간 단위로 표시
        def format_hours_to_hhmm(hours):
            """시간을 H.h 형식으로 변환"""
            if isinstance(hours, (int, float)):
                return f"{hours:.1f}h"
            return str(hours)
        
        # 실제 근무시간과 근태기록시간 비교
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**🏷️ 근태기록 데이터**")
            st.write(f"• 신고 출근: {claim_data['claim_start']}")
            st.write(f"• 신고 퇴근: {claim_data['claim_end']}")
            st.write(f"• 신고 근무시간: {format_hours_to_hhmm(claim_data['claim_hours'])}")
            
            # 근무유형 표시 (WORKSCHDTYPNM 직접 사용)
            st.write(f"• 근무유형: {claim_data.get('claim_type', '선택근무제')}")
            
            if claim_data.get('overtime', 0) > 0:
                st.write(f"• 초과근무: {format_hours_to_hhmm(claim_data['overtime'])}")
        
        with col2:
            st.markdown("**📍 실제 태그 데이터**")
            st.write(f"• 실제 출근: {analysis_result['work_start'].strftime('%H:%M')}")
            st.write(f"• 실제 퇴근: {analysis_result['work_end'].strftime('%H:%M')}")
            st.write(f"• 실제 체류시간: {format_hours_to_hhmm(analysis_result['total_hours'])}")
            
            # 실제 활동 시간 계산
            activity_summary = analysis_result['activity_summary']
            work_codes = ['WORK', 'FOCUSED_WORK', 'EQUIPMENT_OPERATION', 'WORK_PREPARATION', 
                         'WORKING', 'MEETING', 'TRAINING']
            actual_work_minutes = sum(activity_summary.get(code, 0) for code in work_codes)
            actual_work_hours = actual_work_minutes / 60
            st.write(f"• 순수 업무시간: {format_hours_to_hhmm(actual_work_hours)}")
        
        # 시간대별 비교 차트
        st.markdown("**📈 시간대별 비교**")
        self.render_time_comparison_chart(analysis_result, claim_data)
    
    def render_time_comparison_chart(self, analysis_result: dict, claim_data: dict):
        """시간대별 비교 차트"""
        fig = go.Figure()
        
        # 근태기록 시간대
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
        
        # 근태기록 근무시간
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
            name='근태기록',
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
    
    def render_equipment_usage(self, analysis_result: dict):
        """장비 사용 현황 렌더링"""
        equipment_data = analysis_result.get('equipment_data')
        
        if equipment_data is None or equipment_data.empty:
            st.info("장비 사용 데이터가 없습니다.")
            return
        
        # 시스템별 통계
        system_counts = equipment_data['system_type'].value_counts()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            lams_count = system_counts.get('LAMS', 0)
            st.metric("LAMS(품질시스템)", f"{lams_count}건")
        
        with col2:
            mes_count = system_counts.get('MES', 0)
            st.metric("MES(생산시스템)", f"{mes_count}건")
        
        with col3:
            eam_count = system_counts.get('EAM', 0)
            st.metric("EAM(안전설비시스템)", f"{eam_count}건")
        
        # 시간대별 장비 사용 현황
        equipment_data['hour'] = pd.to_datetime(equipment_data['timestamp']).dt.hour
        hourly_usage = equipment_data.groupby(['hour', 'system_type']).size().unstack(fill_value=0)
        
        fig = px.bar(
            hourly_usage.T,
            title="시간대별 장비 사용 현황",
            labels={'value': '사용 횟수', 'index': '시스템', 'hour': '시간'},
            color_discrete_map={
                'LAMS': '#FF6B6B',
                'MES': '#4ECDC4',
                'EAM': '#45B7D1'
            }
        )
        
        fig.update_layout(
            xaxis_title="시간",
            yaxis_title="사용 횟수",
            height=300
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 상세 장비 사용 내역
        with st.expander("🔍 상세 장비 사용 내역"):
            # 표시할 컬럼 선택
            display_columns = ['timestamp', 'system_type', 'action_type', 'equipment_type']
            available_columns = [col for col in display_columns if col in equipment_data.columns]
            
            # 컬럼명 한글화
            column_names = {
                'timestamp': '시간',
                'system_type': '시스템',
                'action_type': '작업유형',
                'equipment_type': '장비유형'
            }
            
            # 데이터 준비
            df_display = equipment_data[available_columns].copy()
            df_display = df_display.rename(columns=column_names)
            
            # 시간 형식 변경
            if '시간' in df_display.columns:
                df_display['시간'] = pd.to_datetime(df_display['시간']).dt.strftime('%H:%M:%S')
            
            # 데이터프레임 표시
            st.dataframe(df_display, use_container_width=True, hide_index=True)
    
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
    
    def render_network_analysis(self, analysis_result: dict):
        """이동 경로 네트워크 분석 렌더링"""
        try:
            # NetworkAnalyzer 초기화
            # 데이터베이스 경로 직접 지정
            db_path = "data/sambio_human.db"
            network_analyzer = NetworkAnalyzer(db_path)
            
            # 분석 파라미터 가져오기
            employee_id = st.session_state.get('selected_employee', '')
            # analysis_date를 사용해야 함 (execute_analysis와 동일하게)
            selected_date = st.session_state.get('analysis_date', date.today())
            employee_name = analysis_result.get('employee_info', {}).get('name', employee_id)
            
            
            # NetworkAnalyzer의 get_employee_movements 메서드 사용
            # 이렇게 하면 식사 데이터가 포함된 완전한 이동 데이터를 얻을 수 있음
            self.logger.info(f"네트워크 분석 시작 - 직원: {employee_id}, 날짜: {selected_date}")
            movements_df = network_analyzer.get_employee_movements(
                employee_id, 
                selected_date.strftime('%Y-%m-%d'),
                selected_date.strftime('%Y-%m-%d'),
                include_meal_data=True
            )
            
            # movements_df가 None인지 확인
            if movements_df is None:
                self.logger.error("movements_df가 None입니다")
                movements_df = pd.DataFrame()  # 빈 DataFrame으로 초기화
            
            # HMM으로 분류된 식사 활동도 추가
            if 'raw_data' in analysis_result and not analysis_result['raw_data'].empty:
                classified_data = analysis_result['raw_data']
                meal_activities = ['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL']
                
                # 식사 활동 필터링
                meal_data = classified_data[classified_data['activity_code'].isin(meal_activities)]
                
                
                if not meal_data.empty:
                    # 🚨 가상 MOVEMENT_TO_BP 태그 생성 중단 - 불필요한 이동시간 추가 방지  
                    # 식사 활동을 이동 데이터로 변환
                    for _, meal in meal_data.iterrows():
                        # 식사 태그만 추가 (이동 태그는 제외)
                        # activity_name이 없을 수 있으므로 activity_code 사용하여 한글명 변환
                        activity_code = meal['activity_code']
                        activity_name_ko = {
                            'BREAKFAST': '조식',
                            'LUNCH': '중식', 
                            'DINNER': '석식',
                            'MIDNIGHT_MEAL': '야식'
                        }.get(activity_code, activity_code)
                        
                        meal_tag = pd.DataFrame({
                            'timestamp': [meal['datetime']],
                            'tag_location': ['BP_CAFETERIA'],
                            'gate_name': [f"{activity_name_ko} at BP"],
                            'work_area_type': ['N'],
                            'building': ['BP']
                        })
                        
                        # 기존 movements_df에 추가
                        try:
                            if movements_df is not None and not movements_df.empty:
                                movements_df = pd.concat([movements_df, meal_tag], ignore_index=True)
                            else:
                                movements_df = meal_tag
                        except Exception as concat_error:
                            self.logger.error(f"DataFrame 병합 중 오류: {concat_error}")
                            # movements_df가 None이면 새로 생성
                            if movements_df is None:
                                movements_df = meal_tag
            
            # movements_df가 None이거나 비어있는지 확인
            if movements_df is None or movements_df.empty:
                st.info("네트워크 분석할 이동 데이터가 없습니다.")
                self.logger.warning(f"movements_df 상태: {type(movements_df)}, None 여부: {movements_df is None}")
                return
            
            # 시간순 정렬
            movements_df = movements_df.sort_values('timestamp').reset_index(drop=True)
            
            # 디버깅 정보 표시 (축소)
            with st.expander("Data Check", expanded=False):
                st.write(f"Total records: {len(movements_df)}")
                
                # 식사 데이터 확인
                meal_records = movements_df[movements_df.get('is_meal', False) == True] if 'is_meal' in movements_df.columns else pd.DataFrame()
                st.write(f"Meal records: {len(meal_records)}")
                
                # BP 관련 레코드 확인
                bp_related = movements_df[movements_df['building'] == 'BP'] if 'building' in movements_df.columns else pd.DataFrame()
                st.write(f"BP-related records: {len(bp_related)}")
                
                if not movements_df.empty:
                    # 샘플 데이터 표시
                    st.write("Sample data (first 5):")
                    display_df = movements_df[['timestamp', 'tag_location', 'building']].head()
                    st.dataframe(display_df)
                    
                    # 건물 매핑 확인
                    building_mapping = movements_df[['tag_location', 'building']].drop_duplicates()
                    st.write("Location-Building Mapping:")
                    st.dataframe(building_mapping)
            
            # 이동 패턴 분석
            movement_analysis = network_analyzer.analyze_movement_patterns(movements_df)
            
            if not movement_analysis:
                st.info("No analyzable movement patterns found.")
                return
            
            # 분석 결과 표시
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Transitions", movement_analysis.get('total_transitions', 0))
            
            with col2:
                building_count = len(movement_analysis.get('building_visits', {}))
                st.metric("Buildings Visited", building_count)
            
            with col3:
                # 가장 많이 방문한 건물
                visits = movement_analysis.get('building_visits', {})
                if visits:
                    most_visited = max(visits.items(), key=lambda x: x[1]['visit_count'])
                    st.metric("Most Visited", f"{most_visited[0]} ({most_visited[1]['visit_count']})")
            
            # 네트워크 시각화
            facility_image_path = Path(__file__).parent.parent.parent.parent / 'data' / 'Sambio.png'
            
            fig = network_analyzer.visualize_movement_network(
                movement_analysis,
                employee_name,
                selected_date.strftime('%Y-%m-%d'),
                str(facility_image_path)
            )
            
            # 고정 크기로 표시 (use_container_width=False)
            # 차트를 중앙에 배치하기 위해 columns 사용
            col1, col2, col3 = st.columns([1, 3, 1])
            with col2:
                st.pyplot(fig, use_container_width=False)
            plt.close()
            
            # 주요 이동 경로
            st.subheader("📍 Frequent Movement Paths")
            frequent_paths = network_analyzer.get_frequent_paths(movement_analysis, top_n=5)
            
            if frequent_paths:
                path_df = pd.DataFrame(frequent_paths)
                st.dataframe(path_df, use_container_width=True)
            else:
                st.info("No frequent paths found.")
            
            
        except Exception as e:
            import traceback
            self.logger.error(f"네트워크 분석 렌더링 중 오류: {str(e)}")
            self.logger.error(f"오류 타입: {type(e).__name__}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            
            # 더 자세한 오류 정보 표시
            error_msg = str(e)
            if error_msg == "Falsev" or "False" in error_msg:
                st.error("네트워크 분석 중 데이터 처리 오류가 발생했습니다.")
                st.info("데이터가 올바르게 로드되었는지 확인해주세요.")
            else:
                st.error(f"네트워크 분석 중 오류가 발생했습니다: {error_msg}")
            
            with st.expander("오류 상세 정보"):
                st.code(traceback.format_exc())
                st.write("오류 발생 시점의 데이터 상태:")
                st.write(f"- analysis_result keys: {list(analysis_result.keys()) if analysis_result else 'None'}")
                if 'raw_data' in analysis_result:
                    st.write(f"- raw_data shape: {analysis_result['raw_data'].shape if hasattr(analysis_result['raw_data'], 'shape') else 'N/A'}")
                    st.write(f"- raw_data columns: {list(analysis_result['raw_data'].columns) if hasattr(analysis_result['raw_data'], 'columns') else 'N/A'}")