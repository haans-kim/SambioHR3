"""
독립적인 데이터 업로드 컴포넌트
기존 UI 스타일을 그대로 유지하며 독립 실행 가능
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import logging
import time
import os
import json
from pathlib import Path
from typing import Dict, List, Optional
import tempfile

# 상대 경로로 core 모듈 import
import sys
sys.path.append(str(Path(__file__).parent.parent))

from core.data_loader import TagDataLoader, DatabaseManager, PickleManager, ExcelLoader

class DataUploadComponent:
    """독립적인 데이터 업로드 컴포넌트"""
    
    def __init__(self, db_path: str = "sambio_human.db", pickle_path: str = "data"):
        self.db_path = db_path
        self.pickle_path = pickle_path
        self.logger = logging.getLogger(__name__)
        
        # 핵심 컴포넌트 초기화
        self.tag_data_loader = TagDataLoader(db_path, pickle_path)
        self.db_manager = self.tag_data_loader.db_manager
        self.pickle_manager = self.tag_data_loader.pickle_manager
        self.excel_loader = self.tag_data_loader.excel_loader
        
        # 설정 파일 경로
        self.config_dir = Path("config")
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / "upload_config.json"
        
        # 데이터 유형 정의 (TagData만 지원)
        self.data_types = {
            "TagData": {
                "table_name": "tag_data",
                "display_name": "태깅 데이터",
                "description": "입출문 태깅 데이터 (2~6월)"
            }
        }
        
        # 세션 상태 초기화
        if 'upload_config' not in st.session_state:
            st.session_state.upload_config = self._load_upload_config()
        
        # 자동으로 pickle 파일 확인 및 로드 - 최초 1회만 실행
        if 'pickles_auto_loaded' not in st.session_state:
            self._auto_load_pickles()
            st.session_state.pickles_auto_loaded = True
    
    def _load_upload_config(self) -> Dict:
        """업로드 설정 로드"""
        config = {}
        for data_type, info in self.data_types.items():
            config[data_type] = {
                "files": [],
                "file_names": [],
                "pickle_exists": False,
                "dataframe_name": None,
                "last_modified": None,
                "row_count": 0
            }
        
        # 저장된 설정이 있으면 병합
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                    if 'upload_config' in saved_config:
                        for data_type, saved_info in saved_config['upload_config'].items():
                            if data_type in config:
                                # files는 로드하지 않음 (UploadedFile 객체는 저장 불가)
                                saved_info['files'] = []
                                config[data_type].update(saved_info)
            except Exception as e:
                self.logger.warning(f"업로드 설정 로드 실패: {e}")
        
        return config
    
    def _save_upload_config(self):
        """업로드 설정 저장"""
        save_config = {'upload_config': {}}
        for data_type, info in st.session_state.upload_config.items():
            save_info = info.copy()
            # 파일 이름 저장
            if 'file_names' in info and info['file_names']:
                save_info['file_names'] = info['file_names']
            else:
                save_info['file_names'] = [file_info['name'] for file_info in info.get('files', [])]
            save_info['files'] = []  # UploadedFile 객체는 제외
            save_config['upload_config'][data_type] = save_info
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(save_config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"업로드 설정 저장 실패: {e}")
    
    def render(self):
        """업로드 인터페이스 렌더링"""
        st.markdown("## 📊 SAMBIO 데이터 업로드 관리")
        st.markdown("### 태깅 데이터 업로드 및 관리")
        
        # 초기 로드 시 pickle 파일 정보로 상태 업데이트
        if 'data_status_refreshed' not in st.session_state:
            self._refresh_data_status()
            st.session_state.data_status_refreshed = True
        
        # 데이터 상태 테이블 표시
        self._render_data_status_table()
        
        # 구분선
        st.markdown("---")
        
        # 파일 추가 섹션
        self._render_file_upload_section()
        
        # 구분선
        st.markdown("---")
        
        # 로드 옵션 섹션
        with st.expander("⚙️ 로드 옵션", expanded=False):
            save_pickle = st.checkbox("Pickle 파일 저장", value=True, 
                                   help="체크하면 Excel 로딩 후 Pickle 파일로도 저장합니다.")
            st.session_state.save_pickle = save_pickle
            
            replace_existing = st.checkbox("기존 데이터 교체", value=False,
                                     help="체크하면 기존 데이터를 삭제하고 새 데이터로 교체합니다.")
            st.session_state.replace_existing = replace_existing
        
        # 액션 버튼들
        col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
        with col1:
            if st.button("📤 데이터 로드", type="primary", use_container_width=True):
                self._load_all_data()
        
        with col2:
            if st.button("🔄 새로고침", use_container_width=True):
                self._refresh_data_status()
                st.rerun()
                
        with col3:
            if st.button("📋 DB 상태 조회", use_container_width=True):
                self._show_db_status()
                
        with col4:
            if st.button("💾 설정 저장", use_container_width=True):
                self._save_upload_config()
                st.success("설정이 저장되었습니다.")
        
        # 큰 구분선으로 섹션 분리
        st.markdown("---")
        st.markdown("---")
        
        # 데이터 조회 섹션
        st.markdown("### 🔍 데이터 조회")
        self._render_data_viewer_section()
    
    def _render_data_status_table(self):
        """데이터 상태 테이블 렌더링"""
        
        # 상태 정보 수집
        status_data = []
        for data_type, info in self.data_types.items():
            # 세션 상태에서 설정 정보 가져오기
            config = st.session_state.upload_config.get(data_type, {
                "files": [], 
                "file_names": [],
                "pickle_exists": False,
                "dataframe_name": None,
                "last_modified": None,
                "row_count": 0
            })
            
            # Pickle 파일 존재 확인 (실시간 체크)
            pickle_files = self.pickle_manager.list_pickle_files(info['table_name'])
            pickle_exists = len(pickle_files) > 0
            
            # 현재 등록된 파일 수와 저장된 파일 이름 목록
            current_files = len(config.get('files', []))
            saved_file_names = config.get('file_names', [])
            
            # 파일 정보 표시
            if current_files > 0:
                # 현재 등록된 파일명 표시
                current_file_names = [f['name'] for f in config.get('files', [])]
                file_info = f"{current_files}개 등록 ({', '.join(current_file_names[:2])}{'...' if len(current_file_names) > 2 else ''})"
            elif saved_file_names:
                # 저장된 파일명 표시
                file_info = f"{len(saved_file_names)}개 ({', '.join(saved_file_names[:2])}{'...' if len(saved_file_names) > 2 else ''})"
            else:
                file_info = "0개"
            
            # 설정 파일의 정보를 우선적으로 사용
            row_count = config.get('row_count', 0)
            last_modified = config.get('last_modified', '-')
            dataframe_name = config.get('dataframe_name', '-')
            
            # 설정 파일에 정보가 없으면 pickle 파일 정보 사용
            if pickle_exists and pickle_files and row_count == 0:
                latest_pickle = pickle_files[0]
                row_count = latest_pickle.get('rows', 0)
                last_modified = latest_pickle.get('created_at', '-')
                dataframe_name = latest_pickle.get('name', '-')
            
            status_data.append({
                "데이터 유형": info['display_name'],
                "등록 파일": file_info,
                "Pickle 상태": "있음" if (pickle_exists or config.get('pickle_exists', False)) else "없음",
                "데이터프레임": dataframe_name,
                "행 수": f"{row_count:,}" if row_count > 0 else "-",
                "최종 수정": last_modified[:10] if last_modified != '-' else "-"
            })
        
        # DataFrame으로 변환하여 표시
        df_status = pd.DataFrame(status_data)
        
        # 전체 행이 보이도록 height를 데이터 행 수에 맞춰 설정
        row_height = 35
        header_height = 40
        total_height = len(df_status) * row_height + header_height + 20
        
        st.dataframe(
            df_status, 
            use_container_width=True,
            hide_index=True,
            height=total_height
        )
    
    def _render_file_upload_section(self):
        """파일 업로드 섹션 렌더링"""
        st.markdown("#### 📁 파일 등록")
        
        # TagData 고정 선택
        selected_type = "TagData"
        st.info(f"📊 데이터 유형: {self.data_types[selected_type]['display_name']}")
        
        # 파일 업로드
        uploaded_files = st.file_uploader(
            "엑셀 파일 선택 (복수 선택 가능)",
            type=['xlsx', 'xls'],
            accept_multiple_files=True,
            key="tag_data_uploader"
        )
        
        # 파일 추가 버튼
        if uploaded_files:
            if st.button("➕ 파일 추가", key="add_files"):
                for file in uploaded_files:
                    file_info = {
                        "name": file.name,
                        "size": file.size,
                        "file": file
                    }
                    # 중복 확인
                    existing_names = [f['name'] for f in st.session_state.upload_config[selected_type]["files"]]
                    if file_info['name'] not in existing_names:
                        st.session_state.upload_config[selected_type]["files"].append(file_info)
                st.success(f"{len(uploaded_files)}개 파일이 추가되었습니다.")
                st.rerun()
        
        # 등록된 파일 목록 표시
        if st.session_state.upload_config[selected_type]["files"]:
            st.markdown(f"##### 📋 {self.data_types[selected_type]['display_name']} 등록 파일")
            
            for idx, file_info in enumerate(st.session_state.upload_config[selected_type]["files"]):
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.text(file_info["name"])
                with col2:
                    st.text(f"{file_info['size'] / (1024*1024):.2f} MB")
                with col3:
                    if st.button("🗑️ 삭제", key=f"remove_{selected_type}_{idx}"):
                        st.session_state.upload_config[selected_type]["files"].pop(idx)
                        st.rerun()
    
    def _load_all_data(self):
        """모든 데이터 로드"""
        progress_bar = st.progress(0)
        status_text = st.empty()
        detail_text = st.empty()
        
        data_type = "TagData"
        info = self.data_types[data_type]
        config = st.session_state.upload_config[data_type]
        
        try:
            if len(config['files']) > 0:
                # 엑셀 파일에서 로드
                status_text.text(f"📊 {info['display_name']} 로딩 중...")
                progress_bar.progress(0.3)
                
                self._load_from_excel(data_type, info, config, detail_text, progress_bar)
                
            else:
                st.warning("등록된 파일이 없습니다. 먼저 Excel 파일을 추가해주세요.")
                return
            
            progress_bar.progress(1.0)
            status_text.text("✅ 로드 완료!")
            
            # 설정 저장
            self._save_upload_config()
            self.logger.info("데이터 로드 완료 - 설정 저장됨")
            
            time.sleep(1)
            progress_bar.empty()
            status_text.empty()
            detail_text.empty()
            
            st.success("🎉 모든 데이터 로드가 완료되었습니다!")
            st.info("새로고침 버튼을 눌러 테이블을 업데이트하세요.")
            
        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            detail_text.empty()
            st.error(f"❌ 로드 실패: {e}")
            self.logger.error(f"데이터 로드 오류: {e}")
    
    def _load_from_excel(self, data_type: str, info: Dict, config: Dict, detail_text, progress_bar):
        """엑셀 파일에서 데이터 로드"""
        temp_files_to_delete = []
        
        try:
            all_dfs = []
            file_names = []
            
            # 모든 파일 읽기
            total_files = len(config['files'])
            for idx, file_info in enumerate(config['files']):
                detail_text.text(f"📖 파일 로딩 중: {file_info['name']} ({idx+1}/{total_files})")
                progress = 0.1 + (idx / total_files) * 0.5
                progress_bar.progress(progress)
                
                # 파일을 임시로 저장 (UploadedFile 객체는 직접 경로로 접근 불가)
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                    tmp_file.write(file_info['file'].getbuffer())
                    tmp_path = tmp_file.name
                
                try:
                    # ExcelLoader 사용하여 로드
                    df = self.excel_loader.load_excel_file(Path(tmp_path), auto_merge_sheets=True)
                    all_dfs.append(df)
                    file_names.append(file_info['name'])
                    self.logger.info(f"{file_info['name']} 로드 완료: {len(df):,}행")
                    
                    temp_files_to_delete.append(tmp_path)
                    
                except Exception as e:
                    # 오류 발생 시 임시 파일 삭제
                    try:
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)
                    except:
                        pass
                    raise e
            
            # 데이터프레임 병합
            if all_dfs:
                detail_text.text("🔄 데이터 병합 중...")
                progress_bar.progress(0.7)
                
                combined_df = pd.concat(all_dfs, ignore_index=True)
                self.logger.info(f"데이터 병합 완료: {len(combined_df):,}행")
                
                # 데이터베이스에 저장
                detail_text.text("💾 데이터베이스 저장 중...")
                progress_bar.progress(0.9)
                
                save_pickle = st.session_state.get('save_pickle', True)
                replace_existing = st.session_state.get('replace_existing', False)
                
                # TagDataLoader 사용하여 저장
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_excel:
                    # 병합된 데이터를 임시 Excel 파일로 저장
                    combined_df.to_excel(tmp_excel.name, index=False)
                    temp_files_to_delete.append(tmp_excel.name)
                    
                    # TagDataLoader로 DB에 저장
                    success = self.tag_data_loader.load_excel_to_db(
                        Path(tmp_excel.name),
                        save_pickle=save_pickle,
                        replace_existing=replace_existing
                    )
                
                if success:
                    # 설정 업데이트
                    config['file_names'] = file_names
                    config['files'] = []  # 로드 완료 후 파일 목록 초기화
                    config['pickle_exists'] = save_pickle
                    config['dataframe_name'] = info['table_name']
                    config['row_count'] = len(combined_df)
                    config['last_modified'] = datetime.now().isoformat()
                    
                    # 세션 상태 업데이트
                    st.session_state.upload_config[data_type] = config
                    
                    self.logger.info(f"{data_type} 로드 완료: {len(combined_df):,}행")
                else:
                    raise Exception("데이터베이스 저장 실패")
                
        except Exception as e:
            self.logger.error(f"{data_type} 로드 오류: {e}")
            raise
        finally:
            # 임시 파일 삭제
            for tmp_path in temp_files_to_delete:
                try:
                    time.sleep(0.5)  # Windows 호환성
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                        self.logger.debug(f"임시 파일 삭제: {tmp_path}")
                except Exception as del_error:
                    self.logger.warning(f"임시 파일 삭제 실패: {tmp_path} - {del_error}")
    
    def _refresh_data_status(self):
        """데이터 상태 정보를 pickle 파일에서 다시 읽어서 업데이트"""
        self.logger.info("데이터 상태 새로고침 시작...")
        
        for data_type, info in self.data_types.items():
            # 최신 pickle 파일 정보 가져오기
            pickle_files = self.pickle_manager.list_pickle_files(info['table_name'])
            
            if pickle_files:
                latest_pickle = pickle_files[0]
                
                # 설정 업데이트
                config = st.session_state.upload_config.get(data_type, {})
                config['pickle_exists'] = True
                config['dataframe_name'] = info['table_name']
                config['row_count'] = latest_pickle.get('rows', 0)
                config['last_modified'] = latest_pickle.get('created_at', datetime.now().isoformat())
                
                # 파일명 정보가 없으면 description에서 추출
                if not config.get('file_names'):
                    config['file_names'] = [f"Pickle 파일 ({latest_pickle.get('rows', 0):,}행)"]
                
                st.session_state.upload_config[data_type] = config
                self.logger.info(f"{data_type} 상태 업데이트: {latest_pickle.get('rows', 0):,}행")
            else:
                # pickle 파일이 없는 경우 초기화
                config = st.session_state.upload_config.get(data_type, {})
                config['pickle_exists'] = False
                config['row_count'] = 0
                config['last_modified'] = '-'
                st.session_state.upload_config[data_type] = config
        
        # 업데이트된 설정 저장
        self._save_upload_config()
        self.logger.info("데이터 상태 새로고침 완료")
    
    def _show_db_status(self):
        """데이터베이스 상태 조회"""
        with st.expander("📊 데이터베이스 상태", expanded=True):
            try:
                # TagDataLoader의 show_status 메서드 활용
                import io
                import contextlib
                
                # 출력을 캡처
                f = io.StringIO()
                with contextlib.redirect_stdout(f):
                    self.tag_data_loader.show_status()
                
                status_output = f.getvalue()
                st.code(status_output, language=None)
                
            except Exception as e:
                st.error(f"데이터베이스 상태 조회 실패: {e}")
    
    def _render_data_viewer_section(self):
        """데이터 조회 섹션 렌더링"""
        # Pickle 파일이 있는지 확인
        pickle_files = self.pickle_manager.list_pickle_files("tag_data")
        
        if not pickle_files:
            st.info("조회 가능한 데이터가 없습니다.")
            return
        
        # 데이터 보기 버튼
        if st.button("📊 TagData 보기", type="primary", use_container_width=True):
            st.session_state.show_data_preview = True
        
        # 데이터 미리보기
        if st.session_state.get('show_data_preview', False):
            self._show_data_preview()
    
    def _show_data_preview(self):
        """TagData 미리보기 표시"""
        try:
            # 최신 pickle 파일 로드
            pickle_files = self.pickle_manager.list_pickle_files("tag_data")
            if not pickle_files:
                st.warning("데이터를 찾을 수 없습니다.")
                return
            
            latest_file = pickle_files[0]
            
            with st.spinner("📊 TagData 로딩 중..."):
                df = self.pickle_manager.load_dataframe("tag_data", latest_file['version'])
            
            if df is None:
                st.error("데이터 로드 실패")
                return
            
            # 새로운 전체 너비 컨테이너
            st.markdown("---")
            
            # 제목과 닫기 버튼
            col_title, col_close = st.columns([5, 1])
            with col_title:
                st.markdown("### 📊 TagData 조회 결과")
            with col_close:
                if st.button("❌ 닫기", use_container_width=True):
                    st.session_state.show_data_preview = False
                    st.rerun()
            
            # 데이터 정보 표시
            st.success("TagData 로드 완료")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("총 행 수", f"{len(df):,}")
            with col2:
                st.metric("총 열 수", f"{len(df.columns):,}")
            with col3:
                st.metric("메모리 사용량", f"{df.memory_usage(deep=True).sum() / 1024**2:.1f} MB")
            with col4:
                st.metric("마지막 업데이트", latest_file.get('created_at', '-')[:10])
            
            # 데이터 미리보기 탭
            tab1, tab2, tab3 = st.tabs(["📋 데이터 미리보기", "📈 열 정보", "🔍 데이터 검색"])
            
            with tab1:
                # 샘플 수 선택
                sample_size = st.slider("표시할 행 수", min_value=10, max_value=min(1000, len(df)), value=100, step=10)
                
                # 데이터 표시
                st.dataframe(df.head(sample_size), use_container_width=True, height=400)
                
                # CSV 다운로드 버튼
                csv = df.head(sample_size).to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 샘플 데이터 다운로드 (CSV)",
                    data=csv,
                    file_name=f"tag_data_sample_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime='text/csv'
                )
            
            with tab2:
                # 열 정보 표시
                col_info = pd.DataFrame({
                    '열 이름': df.columns,
                    '데이터 타입': df.dtypes.astype(str),
                    'Null 값 개수': df.isnull().sum(),
                    'Null 비율(%)': (df.isnull().sum() / len(df) * 100).round(2),
                    '고유값 개수': df.nunique()
                })
                st.dataframe(col_info, use_container_width=True, height=400)
            
            with tab3:
                # 검색 기능
                search_col1, search_col2 = st.columns([1, 2])
                
                with search_col1:
                    search_col = st.selectbox("검색할 컬럼", df.columns.tolist())
                
                with search_col2:
                    search_value = st.text_input("검색어 입력")
                
                if search_value:
                    # 문자열 컬럼인 경우 포함 검색, 숫자형인 경우 정확히 일치
                    if df[search_col].dtype == 'object':
                        mask = df[search_col].astype(str).str.contains(search_value, case=False, na=False)
                    else:
                        try:
                            search_num = float(search_value)
                            mask = df[search_col] == search_num
                        except:
                            mask = pd.Series([False] * len(df))
                    
                    filtered_df = df[mask]
                    
                    if len(filtered_df) > 0:
                        st.success(f"검색 결과: {len(filtered_df)}개 행 발견")
                        st.dataframe(filtered_df.head(100), use_container_width=True, height=300)
                    else:
                        st.warning("검색 결과가 없습니다.")
            
        except Exception as e:
            st.error(f"데이터 조회 중 오류 발생: {e}")
            self.logger.error(f"데이터 조회 오류: {e}", exc_info=True)
    
    def _auto_load_pickles(self):
        """자동으로 pickle 파일을 확인하고 메타데이터 로드"""
        self.logger.info("Pickle 파일 자동 확인 시작...")
        
        try:
            # TagData pickle 파일 확인
            pickle_files = self.pickle_manager.list_pickle_files("tag_data")
            
            if pickle_files:
                # 가장 최신 pickle 파일 정보 가져오기
                latest_pickle = pickle_files[0]
                
                # 세션 상태 업데이트
                config = st.session_state.upload_config.get("TagData", {})
                config['pickle_exists'] = True
                config['dataframe_name'] = "tag_data"
                config['row_count'] = latest_pickle.get('rows', 0)
                config['last_modified'] = latest_pickle.get('created_at', datetime.now().isoformat())
                
                # 파일명 정보 업데이트
                if not config.get('file_names'):
                    config['file_names'] = [f"Pickle 파일 ({latest_pickle.get('rows', 0):,}행)"]
                
                st.session_state.upload_config["TagData"] = config
                
                self.logger.info(f"TagData 메타데이터 로드 완료: {latest_pickle.get('rows', 0):,}행")
            else:
                self.logger.info("TagData pickle 파일 없음")
            
            # 설정 저장
            self._save_upload_config()
            
        except Exception as e:
            self.logger.error(f"Pickle 파일 자동 확인 중 오류: {e}")