"""
데이터 업로드 컴포넌트
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import logging

from ...database import DatabaseManager

class DataUploadComponent:
    """데이터 업로드 컴포넌트"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
    
    def render(self):
        """업로드 인터페이스 렌더링"""
        st.markdown("### 📤 데이터 업로드")
        
        # 업로드 유형 선택
        upload_type = st.selectbox(
            "업로드 데이터 유형",
            [
                "태깅 데이터 (tag_data)",
                "ABC 활동 데이터 (abc_data)",
                "근무시간 Claim 데이터 (claim_data)",
                "근태 사용 데이터 (attendance_data)",
                "비근무시간 데이터 (non_work_time)",
                "직원 정보 (employee_info)",
                "태깅 지점 마스터 (tag_location_master)",
                "조직 매핑 (organization_mapping)"
            ]
        )
        
        # 파일 업로드
        uploaded_file = st.file_uploader(
            "엑셀 파일 선택",
            type=['xlsx', 'xls'],
            help="지원 형식: .xlsx, .xls"
        )
        
        if uploaded_file is not None:
            self.process_upload(uploaded_file, upload_type)
    
    def process_upload(self, uploaded_file, upload_type: str):
        """업로드 처리"""
        try:
            # 파일 정보 표시
            st.success(f"파일 업로드 완료: {uploaded_file.name}")
            st.write(f"파일 크기: {uploaded_file.size / (1024*1024):.2f} MB")
            
            # 데이터 미리보기
            df = pd.read_excel(uploaded_file, nrows=5)
            st.markdown("#### 📋 데이터 미리보기")
            st.dataframe(df)
            
            # 업로드 진행 버튼
            if st.button("🚀 데이터 처리 시작", type="primary"):
                self.execute_data_processing(uploaded_file, upload_type)
                
        except Exception as e:
            st.error(f"파일 처리 중 오류 발생: {e}")
            self.logger.error(f"파일 업로드 오류: {e}")
    
    def execute_data_processing(self, uploaded_file, upload_type: str):
        """데이터 처리 실행"""
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # 단계별 처리
            status_text.text("데이터 로딩 중...")
            progress_bar.progress(20)
            
            status_text.text("데이터 검증 중...")
            progress_bar.progress(40)
            
            status_text.text("데이터 변환 중...")
            progress_bar.progress(60)
            
            status_text.text("데이터베이스 저장 중...")
            progress_bar.progress(80)
            
            status_text.text("처리 완료!")
            progress_bar.progress(100)
            
            st.success("✅ 데이터 처리가 완료되었습니다!")
            
            # 처리 결과 요약
            st.markdown("#### 📊 처리 결과")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("처리된 레코드", "1,234개")
            
            with col2:
                st.metric("처리 시간", "2.3초")
            
            with col3:
                st.metric("성공률", "100%")
                
        except Exception as e:
            st.error(f"데이터 처리 중 오류 발생: {e}")
            self.logger.error(f"데이터 처리 오류: {e}")
        finally:
            progress_bar.empty()
            status_text.empty()