#!/usr/bin/env python3
"""
SAMBIO Data Uploader
독립적인 데이터 업로드 및 관리 애플리케이션

실행 방법:
cd Data_Uploader
streamlit run app.py
"""

import streamlit as st
import logging
from pathlib import Path
import sys

# 현재 디렉토리를 Python 경로에 추가
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# UI 컴포넌트 import
from ui.data_upload_component import DataUploadComponent

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """메인 애플리케이션"""
    
    # Streamlit 페이지 설정
    st.set_page_config(
        page_title="SAMBIO Data Uploader",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # 사이드바 설정
    with st.sidebar:
        st.markdown("## 📊 SAMBIO Data Uploader")
        st.markdown("---")
        st.markdown("### 🎯 주요 기능")
        st.markdown("""
        - **Excel 파일 업로드**: 대용량 태깅 데이터 처리
        - **자동 병합**: 여러 시트 자동 통합
        - **Pickle 캐시**: 빠른 재로딩
        - **DB 저장**: SQLite 데이터베이스 관리
        - **데이터 조회**: 실시간 데이터 미리보기
        """)
        
        st.markdown("---")
        st.markdown("### ℹ️ 사용법")
        st.markdown("""
        1. **파일 등록**: Excel 파일 선택 및 추가
        2. **로드 옵션**: Pickle 저장, 데이터 교체 설정
        3. **데이터 로드**: 버튼 클릭으로 처리 시작
        4. **상태 확인**: 실시간 진행률 모니터링
        5. **데이터 조회**: 로드된 데이터 미리보기
        """)
        
        st.markdown("---")
        st.markdown("### 🔧 설정")
        
        # DB 파일 위치 표시
        db_path = current_dir.parent / "sambio_human.db"
        if db_path.exists():
            st.success(f"✅ DB 연결됨")
            st.caption(f"📁 {db_path.name}")
        else:
            st.warning("⚠️ DB 파일 없음")
            st.caption("첫 실행 시 자동 생성됩니다")
        
        # 데이터 폴더 상태
        data_path = current_dir / "data"
        if data_path.exists():
            pickle_files = list(data_path.glob("*.pkl.gz"))
            if pickle_files:
                st.info(f"📦 Pickle 파일: {len(pickle_files)}개")
            else:
                st.info("📦 Pickle 파일: 없음")
        else:
            st.info("📦 데이터 폴더: 자동 생성 예정")
    
    # 메인 컨텐츠
    try:
        # 경로 설정 (현재 디렉토리 기준)
        db_path = str(current_dir.parent / "sambio_human.db")  # 루트에 DB
        pickle_path = str(current_dir / "data")  # Data_Uploader/data에 pickle
        
        # 데이터 업로드 컴포넌트 초기화 및 렌더링
        upload_component = DataUploadComponent(db_path, pickle_path)
        upload_component.render()
        
    except Exception as e:
        st.error(f"❌ 애플리케이션 오류: {e}")
        logger.error(f"애플리케이션 오류: {e}", exc_info=True)
        
        # 디버깅 정보 표시
        with st.expander("🔍 디버깅 정보"):
            st.code(f"""
오류 세부사항:
- 오류 유형: {type(e).__name__}
- 오류 메시지: {str(e)}
- 현재 디렉토리: {current_dir}
- DB 경로: {current_dir.parent / 'sambio_human.db'}
- Pickle 경로: {current_dir / 'data'}
            """)

if __name__ == "__main__":
    main()