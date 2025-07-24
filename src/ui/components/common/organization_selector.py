"""
조직 선택 공통 컴포넌트
개인분석, 네트워크 분석 등에서 재사용 가능한 조직 선택 UI
"""

import streamlit as st
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

class OrganizationSelector:
    """조직 계층 구조 기반 선택 UI 컴포넌트"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._org_data_cache = None
        self._hierarchy_cache = None
    
    @property
    def org_data(self):
        """조직 데이터 캐싱"""
        if self._org_data_cache is None:
            try:
                from ....data_processing import PickleManager
                pickle_manager = PickleManager()
                self._org_data_cache = pickle_manager.load_dataframe(name='organization_data')
            except Exception as e:
                self.logger.error(f"조직 데이터 로드 실패: {e}")
                self._org_data_cache = pd.DataFrame()
        return self._org_data_cache
    
    def get_organization_hierarchy(self) -> Optional[Dict]:
        """조직 계층 구조 가져오기"""
        if self._hierarchy_cache is not None:
            return self._hierarchy_cache
            
        try:
            if self.org_data.empty:
                return None
            
            # 조직 계층 구조 생성
            hierarchy = {
                'centers': sorted(self.org_data['센터'].dropna().unique().tolist()),
                'by_center': {}
            }
            
            # 센터별로 하위 조직 구조 생성
            for center in hierarchy['centers']:
                center_data = self.org_data[self.org_data['센터'] == center]
                
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
                                'parts': sorted(group_data['파트'].dropna().unique().tolist())
                            }
            
            self._hierarchy_cache = hierarchy
            return hierarchy
            
        except Exception as e:
            self.logger.error(f"조직 계층 구조 생성 실패: {e}")
            return None
    
    def render_selection(self, key_prefix: str = "org", 
                        allow_multiple: bool = False,
                        show_employee_count: bool = True) -> Dict:
        """
        조직 선택 UI 렌더링
        
        Args:
            key_prefix: Streamlit 위젯 키 접두사
            allow_multiple: 복수 선택 허용 여부
            show_employee_count: 직원 수 표시 여부
            
        Returns:
            선택된 조직 정보 딕셔너리
        """
        if self.org_data.empty:
            st.warning("조직 데이터가 없습니다.")
            return {}
        
        selected = {}
        
        # 센터 선택
        centers = ["전체"] + sorted(self.org_data['센터'].dropna().unique().tolist())
        
        if allow_multiple:
            selected_centers = st.multiselect(
                "센터 선택",
                centers[1:],  # "전체" 제외
                key=f"{key_prefix}_center_multi"
            )
            selected['centers'] = selected_centers
            
            # 복수 선택 시 하위 조직은 선택하지 않음
            if show_employee_count and selected_centers:
                count = len(self.org_data[self.org_data['센터'].isin(selected_centers)])
                st.info(f"선택된 센터의 총 직원 수: {count}명")
                
        else:
            selected_center = st.selectbox(
                "센터 선택",
                centers,
                key=f"{key_prefix}_center"
            )
            selected['center'] = selected_center
            
            # BU 선택
            if selected_center != "전체":
                filtered_data = self.org_data[self.org_data['센터'] == selected_center]
                bus = ["전체"] + sorted(filtered_data['BU'].dropna().unique().tolist())
            else:
                bus = ["전체"]
            
            selected_bu = st.selectbox(
                "BU 선택",
                bus,
                key=f"{key_prefix}_bu"
            )
            selected['bu'] = selected_bu
            
            # 팀 선택
            if selected_bu != "전체" and selected_center != "전체":
                filtered_data = self.org_data[
                    (self.org_data['센터'] == selected_center) & 
                    (self.org_data['BU'] == selected_bu)
                ]
                teams = ["전체"] + sorted(filtered_data['팀'].dropna().unique().tolist())
            else:
                teams = ["전체"]
            
            selected_team = st.selectbox(
                "팀 선택",
                teams,
                key=f"{key_prefix}_team"
            )
            selected['team'] = selected_team
            
            # 그룹 선택
            if selected_team != "전체" and selected_bu != "전체" and selected_center != "전체":
                filtered_data = self.org_data[
                    (self.org_data['센터'] == selected_center) & 
                    (self.org_data['BU'] == selected_bu) &
                    (self.org_data['팀'] == selected_team)
                ]
                groups = ["전체"] + sorted(filtered_data['그룹'].dropna().unique().tolist())
            else:
                groups = ["전체"]
            
            selected_group = st.selectbox(
                "그룹 선택",
                groups,
                key=f"{key_prefix}_group"
            )
            selected['group'] = selected_group
            
            # 파트 선택
            if selected_group != "전체" and selected_team != "전체" and selected_bu != "전체" and selected_center != "전체":
                filtered_data = self.org_data[
                    (self.org_data['센터'] == selected_center) & 
                    (self.org_data['BU'] == selected_bu) &
                    (self.org_data['팀'] == selected_team) &
                    (self.org_data['그룹'] == selected_group)
                ]
                parts = ["전체"] + sorted(filtered_data['파트'].dropna().unique().tolist())
            else:
                parts = ["전체"]
            
            selected_part = st.selectbox(
                "파트 선택",
                parts,
                key=f"{key_prefix}_part"
            )
            selected['part'] = selected_part
            
            # 선택된 조직의 직원 수 표시
            if show_employee_count:
                count = self.get_employee_count(selected)
                if count > 0:
                    st.info(f"선택된 조직의 직원 수: {count}명")
        
        return selected
    
    def get_employees_by_selection(self, selection: Dict) -> List[Dict]:
        """선택된 조직의 직원 목록 가져오기"""
        try:
            if self.org_data.empty:
                return []
            
            filtered_data = self.org_data
            
            # 복수 선택인 경우
            if 'centers' in selection and selection['centers']:
                filtered_data = filtered_data[filtered_data['센터'].isin(selection['centers'])]
            # 단일 선택인 경우
            else:
                if selection.get('center') and selection['center'] != "전체":
                    filtered_data = filtered_data[filtered_data['센터'] == selection['center']]
                
                if selection.get('bu') and selection['bu'] != "전체":
                    filtered_data = filtered_data[filtered_data['BU'] == selection['bu']]
                
                if selection.get('team') and selection['team'] != "전체":
                    filtered_data = filtered_data[filtered_data['팀'] == selection['team']]
                
                if selection.get('group') and selection['group'] != "전체":
                    filtered_data = filtered_data[filtered_data['그룹'] == selection['group']]
                
                if selection.get('part') and selection['part'] != "전체":
                    filtered_data = filtered_data[filtered_data['파트'] == selection['part']]
            
            # 직원 목록 생성
            employees = []
            for _, row in filtered_data.iterrows():
                employees.append({
                    'id': str(row['사번']),
                    'name': row['성명'],
                    'position': row.get('직급명', ''),
                    'department': row.get('팀', ''),
                    'display': f"{row['사번']} - {row['성명']} ({row.get('직급명', '')})"
                })
            
            return sorted(employees, key=lambda x: x['id'])
            
        except Exception as e:
            self.logger.error(f"직원 목록 가져오기 실패: {e}")
            return []
    
    def get_employee_count(self, selection: Dict) -> int:
        """선택된 조직의 직원 수 가져오기"""
        return len(self.get_employees_by_selection(selection))
    
    def get_selection_display_name(self, selection: Dict) -> str:
        """선택된 조직의 표시 이름 생성"""
        if 'centers' in selection and selection['centers']:
            return f"센터: {', '.join(selection['centers'])}"
        
        parts = []
        if selection.get('center') and selection['center'] != "전체":
            parts.append(selection['center'])
        if selection.get('bu') and selection['bu'] != "전체":
            parts.append(selection['bu'])
        if selection.get('team') and selection['team'] != "전체":
            parts.append(selection['team'])
        if selection.get('group') and selection['group'] != "전체":
            parts.append(selection['group'])
        if selection.get('part') and selection['part'] != "전체":
            parts.append(selection['part'])
        
        if parts:
            return " > ".join(parts)
        else:
            return "전체 조직"