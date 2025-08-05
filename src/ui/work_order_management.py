"""
작업지시 관리 시스템 UI 모듈
Phase 4: 작업지시 생성, 편집, 할당 및 추적 기능
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
import json
import logging

from ..database import get_database_manager
from ..utils.work_order_utils import WorkOrderManager

logger = logging.getLogger(__name__)


class WorkOrderManagementUI:
    """작업지시 관리 UI 클래스"""
    
    def __init__(self):
        self.db_manager = get_database_manager()
        self.work_order_manager = WorkOrderManager(self.db_manager)
        
    def render(self):
        """메인 렌더링"""
        st.title("작업지시 관리 시스템")
        
        # 탭 생성
        tab1, tab2, tab3, tab4 = st.tabs([
            "작업지시 목록", 
            "새 작업지시 생성", 
            "내 작업지시", 
            "진행 현황"
        ])
        
        with tab1:
            self.render_work_order_list()
            
        with tab2:
            self.render_create_work_order()
            
        with tab3:
            self.render_my_work_orders()
            
        with tab4:
            self.render_progress_dashboard()
    
    def render_work_order_list(self):
        """작업지시 목록 화면"""
        st.subheader("작업지시 목록")
        
        # 필터링 옵션
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            status_filter = st.selectbox(
                "상태",
                ["전체", "대기", "승인", "할당", "진행중", "완료"],
                key="list_status_filter"
            )
        
        with col2:
            priority_filter = st.selectbox(
                "우선순위",
                ["전체", "긴급", "높음", "보통", "낮음"],
                key="list_priority_filter"
            )
        
        with col3:
            date_filter = st.date_input(
                "기한",
                value=None,
                key="list_date_filter"
            )
        
        with col4:
            search_text = st.text_input(
                "검색",
                placeholder="제목, 요청자 검색",
                key="list_search"
            )
        
        # 작업지시 목록 조회
        work_orders = self.get_filtered_work_orders(
            status_filter, priority_filter, date_filter, search_text
        )
        
        if work_orders:
            # 목록 표시
            for order in work_orders:
                with st.container():
                    self.render_work_order_card(order)
        else:
            st.info("조건에 맞는 작업지시가 없습니다.")
    
    def render_work_order_card(self, order: Dict):
        """작업지시 카드 렌더링"""
        # 우선순위 색상
        priority_colors = {
            'urgent': '#FF4444',
            'high': '#FF8844',
            'medium': '#4488FF',
            'low': '#888888'
        }
        
        # 상태 색상
        status_colors = {
            'draft': '#888888',
            'approved': '#4488FF',
            'assigned': '#FF8844',
            'in_progress': '#44FF88',
            'completed': '#44FF44',
            'cancelled': '#FF4444'
        }
        
        priority_color = priority_colors.get(order['priority'], '#888888')
        status_color = status_colors.get(order['status'], '#888888')
        
        # 카드 렌더링
        st.markdown(
            f"""
            <div style="
                border: 1px solid #ddd;
                border-radius: 10px;
                padding: 15px;
                margin: 10px 0;
                background-color: #f9f9f9;
            ">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h4 style="margin: 0; color: #333;">
                            {order['order_number']} - {order['title']}
                        </h4>
                        <p style="margin: 5px 0; color: #666;">
                            요청자: {order['requester_name']} | 
                            요청일: {order['request_date']} | 
                            기한: {order['due_date'] or '미정'}
                        </p>
                        <p style="margin: 5px 0; color: #666;">
                            대상: {order['center_name']} 
                            {f"> {order['group_name']}" if order['group_name'] else ""}
                            {f"> {order['team_name']}" if order['team_name'] else ""}
                        </p>
                    </div>
                    <div style="text-align: right;">
                        <span style="
                            background-color: {priority_color};
                            color: white;
                            padding: 5px 10px;
                            border-radius: 5px;
                            font-size: 12px;
                            margin-right: 5px;
                        ">{self.get_priority_label(order['priority'])}</span>
                        <span style="
                            background-color: {status_color};
                            color: white;
                            padding: 5px 10px;
                            border-radius: 5px;
                            font-size: 12px;
                        ">{self.get_status_label(order['status'])}</span>
                    </div>
                </div>
                <div style="margin-top: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="color: #666;">
                            담당자: {order.get('assignee_count', 0)}명 | 
                            항목: {order.get('item_count', 0)}개 | 
                            진행률: {order.get('completion_rate', 0):.0f}%
                        </span>
                        <div>
                            <button style="
                                background-color: #4CAF50;
                                color: white;
                                border: none;
                                padding: 5px 15px;
                                border-radius: 5px;
                                cursor: pointer;
                            " onclick="window.location.href='#detail_{order['order_id']}'">
                                상세보기
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # 상세보기 버튼
        if st.button(f"상세보기", key=f"detail_{order['order_id']}"):
            st.session_state.selected_order_id = order['order_id']
            st.session_state.current_page = "작업지시 상세"
    
    def render_create_work_order(self):
        """새 작업지시 생성 화면"""
        st.subheader("새 작업지시 생성")
        
        with st.form("create_work_order_form"):
            # 기본 정보
            st.markdown("### 기본 정보")
            col1, col2 = st.columns(2)
            
            with col1:
                title = st.text_input("제목", placeholder="작업지시 제목을 입력하세요")
                order_type = st.selectbox(
                    "유형",
                    ["analysis", "report", "improvement", "etc"],
                    format_func=lambda x: {
                        "analysis": "분석 요청",
                        "report": "보고서 작성",
                        "improvement": "개선 활동",
                        "etc": "기타"
                    }.get(x, x)
                )
                priority = st.selectbox(
                    "우선순위",
                    ["urgent", "high", "medium", "low"],
                    index=2,
                    format_func=lambda x: self.get_priority_label(x)
                )
            
            with col2:
                due_date = st.date_input(
                    "기한",
                    value=date.today() + timedelta(days=7),
                    min_value=date.today()
                )
                requester_name = st.text_input(
                    "요청자",
                    value=st.session_state.get('user_name', ''),
                    disabled=True
                )
            
            description = st.text_area(
                "설명",
                placeholder="작업지시 내용을 상세히 입력하세요",
                height=100
            )
            
            # 대상 조직 선택
            st.markdown("### 대상 조직")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                target_type = st.selectbox(
                    "대상 유형",
                    ["center", "group", "team", "individual"],
                    format_func=lambda x: {
                        "center": "센터",
                        "group": "그룹",
                        "team": "팀",
                        "individual": "개인"
                    }.get(x, x)
                )
            
            # 조직 데이터 로드
            org_data = self.load_organization_data()
            
            with col2:
                centers = ["전체"] + sorted(org_data['센터'].unique().tolist())
                center_name = st.selectbox("센터", centers)
            
            with col3:
                if center_name != "전체" and target_type in ["group", "team"]:
                    groups = ["전체"] + sorted(
                        org_data[org_data['센터'] == center_name]['그룹'].unique().tolist()
                    )
                    group_name = st.selectbox("그룹", groups)
                else:
                    group_name = None
            
            with col4:
                if group_name and group_name != "전체" and target_type == "team":
                    teams = sorted(
                        org_data[
                            (org_data['센터'] == center_name) & 
                            (org_data['그룹'] == group_name)
                        ]['팀'].unique().tolist()
                    )
                    team_name = st.selectbox("팀", teams)
                else:
                    team_name = None
            
            # 세부 항목
            st.markdown("### 세부 항목")
            
            # 동적 항목 추가
            if 'work_order_items' not in st.session_state:
                st.session_state.work_order_items = []
            
            # 항목 추가 버튼
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.form_submit_button("항목 추가", use_container_width=True):
                    st.session_state.work_order_items.append({
                        'item_type': 'analysis',
                        'description': '',
                        'target_date_start': date.today(),
                        'target_date_end': date.today()
                    })
            
            # 항목 목록 표시
            for i, item in enumerate(st.session_state.work_order_items):
                with st.container():
                    st.markdown(f"#### 항목 {i+1}")
                    col1, col2, col3 = st.columns([2, 2, 1])
                    
                    with col1:
                        item['item_type'] = st.selectbox(
                            "유형",
                            ["analysis", "action", "report"],
                            key=f"item_type_{i}",
                            format_func=lambda x: {
                                "analysis": "분석",
                                "action": "조치",
                                "report": "보고서"
                            }.get(x, x)
                        )
                    
                    with col2:
                        item['description'] = st.text_input(
                            "설명",
                            key=f"item_desc_{i}"
                        )
                    
                    with col3:
                        if st.button("삭제", key=f"del_item_{i}"):
                            st.session_state.work_order_items.pop(i)
                            st.rerun()
                    
                    if item['item_type'] == 'analysis':
                        col1, col2 = st.columns(2)
                        with col1:
                            item['target_date_start'] = st.date_input(
                                "시작일",
                                key=f"item_start_{i}"
                            )
                        with col2:
                            item['target_date_end'] = st.date_input(
                                "종료일",
                                key=f"item_end_{i}"
                            )
            
            # 제출 버튼
            submitted = st.form_submit_button("작업지시 생성", type="primary", use_container_width=True)
            
            if submitted:
                if not title:
                    st.error("제목을 입력해주세요.")
                elif not description:
                    st.error("설명을 입력해주세요.")
                elif center_name == "전체":
                    st.error("대상 조직을 선택해주세요.")
                else:
                    # 작업지시 생성
                    result = self.work_order_manager.create_work_order(
                        title=title,
                        description=description,
                        order_type=order_type,
                        priority=priority,
                        due_date=due_date,
                        requester_id=st.session_state.get('user_id', 'system'),
                        requester_name=requester_name or 'System',
                        target_type=target_type,
                        center_name=center_name if center_name != "전체" else None,
                        group_name=group_name if group_name != "전체" else None,
                        team_name=team_name,
                        items=st.session_state.work_order_items
                    )
                    
                    if result['success']:
                        st.success(f"작업지시가 생성되었습니다. (번호: {result['order_number']})")
                        st.session_state.work_order_items = []
                    else:
                        st.error(f"작업지시 생성 실패: {result['error']}")
    
    def render_my_work_orders(self):
        """내 작업지시 화면"""
        st.subheader("내 작업지시")
        
        # 사용자 ID (실제로는 로그인 정보에서 가져와야 함)
        user_id = st.session_state.get('user_id', 'test_user')
        
        # 역할별 탭
        tab1, tab2, tab3 = st.tabs(["담당 작업", "요청한 작업", "참조 작업"])
        
        with tab1:
            # 담당 작업지시 목록
            assigned_orders = self.work_order_manager.get_assigned_work_orders(user_id)
            
            if assigned_orders:
                for order in assigned_orders:
                    self.render_assigned_order_card(order)
            else:
                st.info("담당하고 있는 작업지시가 없습니다.")
        
        with tab2:
            # 요청한 작업지시 목록
            requested_orders = self.work_order_manager.get_requested_work_orders(user_id)
            
            if requested_orders:
                for order in requested_orders:
                    self.render_work_order_card(order)
            else:
                st.info("요청한 작업지시가 없습니다.")
        
        with tab3:
            # 참조 작업지시 목록
            st.info("참조 중인 작업지시가 없습니다.")
    
    def render_assigned_order_card(self, order: Dict):
        """담당 작업지시 카드"""
        with st.expander(f"{order['order_number']} - {order['title']}", expanded=True):
            # 기본 정보
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("우선순위", self.get_priority_label(order['priority']))
            with col2:
                st.metric("기한", order['due_date'] or "미정")
            with col3:
                st.metric("진행률", f"{order.get('completion_rate', 0):.0f}%")
            
            # 설명
            st.markdown("**설명:**")
            st.write(order['description'])
            
            # 항목별 진행 상황
            items = self.work_order_manager.get_work_order_items(order['order_id'])
            
            if items:
                st.markdown("**세부 항목:**")
                for item in items:
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.write(f"• {item['description']}")
                    with col2:
                        progress = st.number_input(
                            "진행률",
                            min_value=0,
                            max_value=100,
                            value=item['progress_rate'],
                            key=f"progress_{item['item_id']}"
                        )
                    with col3:
                        if st.button("저장", key=f"save_{item['item_id']}"):
                            self.work_order_manager.update_item_progress(
                                item['item_id'],
                                progress
                            )
                            st.success("저장되었습니다.")
            
            # 작업 완료 버튼
            if st.button("작업 완료", key=f"complete_{order['order_id']}"):
                if self.work_order_manager.complete_assignment(order['order_id'], user_id):
                    st.success("작업이 완료 처리되었습니다.")
                    st.rerun()
    
    def render_progress_dashboard(self):
        """진행 현황 대시보드"""
        st.subheader("작업지시 진행 현황")
        
        # 전체 통계
        stats = self.work_order_manager.get_overall_statistics()
        
        if stats:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("전체 작업지시", stats['total_orders'])
            with col2:
                st.metric("진행중", stats['in_progress_orders'])
            with col3:
                st.metric("완료", stats['completed_orders'])
            with col4:
                st.metric("평균 진행률", f"{stats['avg_completion_rate']:.0f}%")
        
        # 조직별 현황
        st.markdown("### 조직별 현황")
        org_stats = self.work_order_manager.get_organization_statistics()
        
        if org_stats:
            df = pd.DataFrame(org_stats)
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )
        
        # 담당자별 현황
        st.markdown("### 담당자별 현황")
        assignee_stats = self.work_order_manager.get_assignee_statistics()
        
        if assignee_stats:
            df = pd.DataFrame(assignee_stats)
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )
    
    # 유틸리티 메서드
    def get_filtered_work_orders(self, status_filter, priority_filter, date_filter, search_text):
        """필터링된 작업지시 목록 조회"""
        query = """
        SELECT * FROM v_work_order_summary
        WHERE 1=1
        """
        params = {}
        
        if status_filter != "전체":
            status_map = {
                "대기": "draft",
                "승인": "approved",
                "할당": "assigned",
                "진행중": "in_progress",
                "완료": "completed"
            }
            query += " AND status = :status"
            params['status'] = status_map.get(status_filter, status_filter)
        
        if priority_filter != "전체":
            priority_map = {
                "긴급": "urgent",
                "높음": "high",
                "보통": "medium",
                "낮음": "low"
            }
            query += " AND priority = :priority"
            params['priority'] = priority_map.get(priority_filter, priority_filter)
        
        if date_filter:
            query += " AND due_date <= :due_date"
            params['due_date'] = date_filter.isoformat()
        
        if search_text:
            query += " AND (title LIKE :search OR requester_name LIKE :search)"
            params['search'] = f"%{search_text}%"
        
        query += " ORDER BY priority DESC, due_date ASC"
        
        return self.db_manager.execute_query(query, params)
    
    def load_organization_data(self):
        """조직 데이터 로드"""
        from ..database import get_pickle_manager
        pickle_manager = get_pickle_manager()
        return pickle_manager.load_dataframe(name='organization_data')
    
    def get_priority_label(self, priority):
        """우선순위 라벨"""
        return {
            'urgent': '긴급',
            'high': '높음',
            'medium': '보통',
            'low': '낮음'
        }.get(priority, priority)
    
    def get_status_label(self, status):
        """상태 라벨"""
        return {
            'draft': '대기',
            'approved': '승인',
            'assigned': '할당',
            'in_progress': '진행중',
            'completed': '완료',
            'cancelled': '취소'
        }.get(status, status)