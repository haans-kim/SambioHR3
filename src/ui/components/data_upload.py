"""
데이터 업로드 컴포넌트 - 테이블 형태로 재구성
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

from ...database import DatabaseManager
from ...data_processing import PickleManager, DataTransformer, ExcelLoader

class DataUploadComponent:
    """데이터 업로드 컴포넌트"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        self.pickle_manager = PickleManager()
        self.data_transformer = DataTransformer()
        self.excel_loader = ExcelLoader()
        
        # 설정 파일 경로
        self.config_dir = Path("config")
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / "upload_config.json"
        
        # 데이터 유형 정의 로드 (저장된 설정이 있으면 사용)
        self.data_types = self._load_data_types()
        
        # 세션 상태 초기화
        if 'upload_config' not in st.session_state:
            st.session_state.upload_config = self._load_upload_config()
        
        # 자동으로 pickle 파일 확인 및 로드 - 최초 1회만 실행
        if 'pickles_auto_loaded' not in st.session_state:
            self._auto_load_pickles()
            st.session_state.pickles_auto_loaded = True
    
    def _load_data_types(self) -> Dict:
        """데이터 유형 정의 로드"""
        default_types = {
            "Tagging Data": {
                "table_name": "tag_data",
                "display_name": "태깅 데이터",
                "process_func_name": "process_tagging_data"
            },
            "태깅지점": {
                "table_name": "tag_location_master",
                "display_name": "태깅 지점 마스터",
                "process_func_name": None
            },
            "근무시간_Claim": {
                "table_name": "claim_data",
                "display_name": "근무시간 Claim 데이터",
                "process_func_name": "process_claim_data"
            },
            "근태사용": {
                "table_name": "attendance_data",
                "display_name": "근태 사용 데이터",
                "process_func_name": None
            },
            "비근무시간": {
                "table_name": "non_work_time",
                "display_name": "비근무시간 데이터",
                "process_func_name": None
            },
            "ABC데이터": {
                "table_name": "abc_data",
                "display_name": "ABC 활동 데이터",
                "process_func_name": "process_abc_data"
            },
            "식사 데이터": {
                "table_name": "meal_data",
                "display_name": "식사 태그 데이터",
                "process_func_name": "process_meal_data"
            }
        }
        
        # 저장된 설정 파일이 있으면 로드
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                    if 'data_types' in saved_config:
                        default_types.update(saved_config['data_types'])
            except Exception as e:
                self.logger.warning(f"설정 파일 로드 실패: {e}")
        
        # process_func 설정
        for data_type, info in default_types.items():
            if info.get('process_func_name'):
                info['process_func'] = getattr(self.data_transformer, info['process_func_name'], None)
            else:
                info['process_func'] = None
        
        return default_types
    
    def _save_data_types(self):
        """데이터 유형 정의 저장"""
        # process_func는 저장할 수 없으므로 함수 이름만 저장
        save_data = {'data_types': {}}
        for data_type, info in self.data_types.items():
            save_info = info.copy()
            # process_func 제거하고 함수 이름만 저장
            if 'process_func' in save_info:
                if save_info['process_func']:
                    save_info['process_func_name'] = save_info['process_func'].__name__
                del save_info['process_func']
            save_data['data_types'][data_type] = save_info
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"설정 파일 저장 실패: {e}")
    
    def _load_upload_config(self) -> Dict:
        """업로드 설정 로드"""
        # 기본 설정 초기화
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
                                # file_names 정보는 유지
                                config[data_type].update(saved_info)
            except Exception as e:
                self.logger.warning(f"업로드 설정 로드 실패: {e}")
        
        return config
    
    def _save_upload_config(self):
        """업로드 설정 저장"""
        # UploadedFile 객체는 JSON 직렬화 불가하므로 파일 이름만 저장
        save_config = {'upload_config': {}}
        for data_type, info in st.session_state.upload_config.items():
            save_info = info.copy()
            # 파일 이름 저장 - 이미 file_names가 있으면 그것을 사용
            if 'file_names' in info and info['file_names']:
                save_info['file_names'] = info['file_names']
            else:
                # files가 있으면 그것에서 파일명 추출
                save_info['file_names'] = [file_info['name'] for file_info in info.get('files', [])]
            save_info['files'] = []  # UploadedFile 객체는 제외
            save_config['upload_config'][data_type] = save_info
        
        # 데이터 유형 정의도 함께 저장
        save_data = {'data_types': {}}
        for data_type, info in self.data_types.items():
            save_info = info.copy()
            if 'process_func' in save_info:
                if save_info['process_func']:
                    save_info['process_func_name'] = save_info['process_func'].__name__
                del save_info['process_func']
            save_data['data_types'][data_type] = save_info
        
        save_data.update(save_config)
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"업로드 설정 저장 실패: {e}")
    
    def render(self):
        """업로드 인터페이스 렌더링"""
        st.markdown("### 📤 데이터 업로드 관리")
        
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
        
        # 옵션 설정
        with st.expander("⚙️ 로드 옵션", expanded=False):
            save_to_db = st.checkbox("데이터베이스에도 저장", value=False, 
                                   help="체크하면 Pickle 파일과 함께 SQLite 데이터베이스에도 저장됩니다.")
            st.session_state.save_to_db = save_to_db
            
            process_data = st.checkbox("데이터 전처리 실행", value=False,
                                     help="체크하면 데이터 로딩 후 전처리(분석)를 실행합니다. 대용량 데이터는 시간이 오래 걸릴 수 있습니다.")
            st.session_state.process_data = process_data
        
        # 데이터 로드 버튼
        col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
        with col1:
            if st.button("🚀 데이터 로드", type="primary", use_container_width=True):
                self._load_all_data()
        
        with col2:
            if st.button("🗑️ 캐시 초기화", use_container_width=True):
                self._clear_cache()
                
        with col3:
            if st.button("🔄 새로고침", use_container_width=True):
                self._refresh_data_status()
                st.rerun()
                
        with col4:
            if st.button("💾 설정 저장", use_container_width=True):
                self._save_upload_config()
                st.success("설정이 저장되었습니다.")
    
    def _render_data_status_table(self):
        """데이터 상태 테이블 렌더링"""
        st.markdown("#### 📊 데이터 로딩 상태")
        
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
                # 로깅 추가
                self.logger.info(f"{data_type} saved_file_names: {saved_file_names}")
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
                "Pickle 상태": "✅ 있음" if (pickle_exists or config.get('pickle_exists', False)) else "❌ 없음",
                "데이터프레임": dataframe_name,
                "행 수": f"{row_count:,}" if row_count > 0 else "-",
                "최종 수정": last_modified if last_modified != '-' else "-"
            })
        
        # DataFrame으로 변환하여 표시
        df_status = pd.DataFrame(status_data)
        st.dataframe(df_status, use_container_width=True, height=250)
    
    def _render_file_upload_section(self):
        """파일 업로드 섹션 렌더링"""
        st.markdown("#### 📁 파일 등록")
        
        # 데이터 유형 선택
        col1, col2 = st.columns([1, 2])
        
        with col1:
            selected_type = st.selectbox(
                "데이터 유형",
                list(self.data_types.keys()),
                key="upload_data_type"
            )
        
        with col2:
            uploaded_files = st.file_uploader(
                "엑셀 파일 선택 (복수 선택 가능)",
                type=['xlsx', 'xls'],
                accept_multiple_files=True,
                key=f"file_uploader_{selected_type}"
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
                    if file_info not in st.session_state.upload_config[selected_type]["files"]:
                        st.session_state.upload_config[selected_type]["files"].append(file_info)
                st.success(f"{len(uploaded_files)}개 파일이 추가되었습니다.")
        
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
                    if st.button("❌", key=f"remove_{selected_type}_{idx}"):
                        st.session_state.upload_config[selected_type]["files"].pop(idx)
        
        # 신규 데이터 유형 추가
        with st.expander("➕ 신규 데이터 유형 추가"):
            new_type_name = st.text_input("데이터 유형 이름")
            new_table_name = st.text_input("테이블 이름")
            new_display_name = st.text_input("표시 이름")
            
            if st.button("추가") and all([new_type_name, new_table_name, new_display_name]):
                self.data_types[new_type_name] = {
                    "table_name": new_table_name,
                    "display_name": new_display_name,
                    "process_func": None
                }
                st.session_state.upload_config[new_type_name] = {
                    "files": [],
                    "pickle_exists": False,
                    "dataframe_name": None,
                    "last_modified": None,
                    "row_count": 0
                }
                # 설정 저장
                self._save_data_types()
                self._save_upload_config()
                st.success(f"'{new_type_name}' 데이터 유형이 추가되었습니다.")
    
    def _load_all_data(self):
        """모든 데이터 로드"""
        progress_bar = st.progress(0)
        status_text = st.empty()
        detail_text = st.empty()  # 상세 진행상황 표시용
        
        total_types = len(self.data_types)
        
        for idx, (data_type, info) in enumerate(self.data_types.items()):
            config = st.session_state.upload_config[data_type]
            
            # 진행률 업데이트
            progress = (idx) / total_types
            progress_bar.progress(progress)
            status_text.text(f"처리 중: {info['display_name']} ({idx + 1}/{total_types})")
            
            # 파일이 변경되었는지 확인
            pickle_files = self.pickle_manager.list_pickle_files(info['table_name'])
            needs_reload = (
                len(config['files']) > 0 or  # 새 파일이 추가됨
                (len(pickle_files) == 0 and len(config['files']) == 0)  # pickle도 없고 파일도 없음
            )
            
            if needs_reload and len(config['files']) > 0:
                # 엑셀 파일에서 로드
                detail_text.text(f"📂 {info['display_name']} 파일 로딩 중...")
                self._load_from_excel(data_type, info, config, detail_text)
            elif len(pickle_files) > 0 and len(config['files']) == 0:
                # Pickle 파일에서 로드
                detail_text.text(f"💾 {info['display_name']} 캐시에서 로딩 중...")
                self._load_from_pickle(data_type, info)
            
            time.sleep(0.1)  # UI 업데이트를 위한 짧은 대기
        
        progress_bar.empty()
        status_text.empty()
        detail_text.empty()
        
        # 설정 저장 - 세션 상태가 이미 업데이트되어 있으므로 바로 저장
        self._save_upload_config()
        self.logger.info("데이터 로드 완료 - 설정 저장됨")
        
        st.success("✅ 모든 데이터 로드가 완료되었습니다!")
        st.info("🔄 새로고침 버튼을 눌러 테이블을 업데이트하세요.")
        
        # 버튼 클릭 후에만 rerun
        time.sleep(2)  # 성공 메시지를 보여주기 위한 대기
    
    def _load_from_excel(self, data_type: str, info: Dict, config: Dict, detail_text=None):
        """엑셀 파일에서 데이터 로드"""
        try:
            all_dfs = []
            
            # 파일 이름 목록 수집
            file_names = []
            
            # 모든 파일 읽기
            for idx, file_info in enumerate(config['files']):
                self.logger.info(f"[{idx+1}/{len(config['files'])}] {file_info['name']} 로딩 시작...")
                
                # 파일을 임시로 저장 (UploadedFile 객체는 직접 경로로 접근 불가)
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                    tmp_file.write(file_info['file'].getbuffer())
                    tmp_path = tmp_file.name
                
                try:
                    # ExcelLoader 사용하여 로드 (여러 시트 자동 병합)
                    if detail_text:
                        detail_text.text(f"📂 {file_info['name']} 파일 분석 중...")
                    df = self.excel_loader.load_excel_file(tmp_path, auto_merge_sheets=True)
                    all_dfs.append(df)
                    file_names.append(file_info['name'])
                    self.logger.info(f"{file_info['name']} 로드 완료: {len(df):,}행")
                    if detail_text:
                        detail_text.text(f"✅ {file_info['name']} 로드 완료: {len(df):,}행")
                finally:
                    # 임시 파일 삭제
                    import os
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
            
            # 데이터프레임 병합
            if all_dfs:
                combined_df = pd.concat(all_dfs, ignore_index=True)
                
                # 데이터 변환 (옵션이 켜져있을 때만)
                if info['process_func'] and st.session_state.get('process_data', False):
                    self.logger.info(f"{data_type} 전처리 시작...")
                    processed_df = info['process_func'](combined_df)
                else:
                    processed_df = combined_df
                    if info['process_func']:
                        self.logger.info(f"{data_type} 로딩만 수행 (전처리 건너뜀)")
                
                # Pickle로 저장
                version = datetime.now().strftime('%Y%m%d_%H%M%S')
                self.pickle_manager.save_dataframe(
                    processed_df,
                    name=info['table_name'],
                    version=version,
                    description=f"Combined from {len(config['files'])} files"
                )
                
                # 데이터베이스에 저장 (옵션이 켜져있을 때만)
                if self.db_manager and st.session_state.get('save_to_db', False):
                    try:
                        # 기존 데이터 삭제
                        table_class = self.db_manager.get_table_class(info['table_name'])
                        if table_class:
                            with self.db_manager.get_session() as session:
                                session.query(table_class).delete()
                                session.commit()
                        
                        # 새 데이터 삽입
                        self.db_manager.dataframe_to_table(
                            processed_df, 
                            info['table_name'], 
                            if_exists='append'
                        )
                        self.logger.info(f"{info['display_name']} 데이터베이스 저장 완료")
                    except Exception as db_error:
                        self.logger.warning(f"데이터베이스 저장 실패 (Pickle은 성공): {db_error}")
                
                # 설정 업데이트
                config['file_names'] = file_names  # 위에서 수집한 파일 이름 목록 사용
                config['files'] = []  # 로드 완료 후 파일 목록 초기화
                config['pickle_exists'] = True
                config['dataframe_name'] = info['table_name']
                config['row_count'] = len(processed_df)
                config['last_modified'] = datetime.now().isoformat()
                
                # 디버깅용 로그
                self.logger.info(f"{data_type} 파일명 수집 결과: {file_names}")
                
                # 세션 상태 업데이트
                st.session_state.upload_config[data_type] = config
                self.logger.info(f"{data_type} 설정 업데이트: {config}")
                
                st.success(f"✅ {info['display_name']} 로드 완료: {len(processed_df):,}행")
                
        except Exception as e:
            st.error(f"❌ {info['display_name']} 로드 실패: {e}")
            self.logger.error(f"{data_type} 로드 오류: {e}")
    
    def _load_from_pickle(self, data_type: str, info: Dict):
        """Pickle 파일에서 데이터 로드"""
        try:
            # 가장 최신 pickle 파일 로드
            pickle_files = self.pickle_manager.list_pickle_files(info['table_name'])
            if pickle_files:
                latest_file = pickle_files[0]
                df = self.pickle_manager.load_dataframe(
                    name=info['table_name'],
                    version=latest_file['version']
                )
                
                if df is not None:
                    # 설정 업데이트
                    config = st.session_state.upload_config[data_type]
                    config['pickle_exists'] = True
                    config['dataframe_name'] = info['table_name']
                    config['row_count'] = len(df)
                    config['last_modified'] = latest_file.get('created_at', datetime.now().isoformat())
                    
                    # 세션 상태 업데이트
                    st.session_state.upload_config[data_type] = config
                    
                    st.info(f"ℹ️ {info['display_name']} Pickle 캐시에서 로드: {len(df):,}행")
                else:
                    st.warning(f"⚠️ {info['display_name']} Pickle 파일 로드 실패")
                    
        except Exception as e:
            st.error(f"❌ {info['display_name']} Pickle 로드 오류: {e}")
            self.logger.error(f"{data_type} pickle 로드 오류: {e}")
    
    def _refresh_data_status(self):
        """데이터 상태 정보를 pickle 파일에서 다시 읽어서 업데이트"""
        self.logger.info("데이터 상태 새로고침 시작...")
        
        for data_type, info in self.data_types.items():
            # 최신 pickle 파일 정보 가져오기
            pickle_files = self.pickle_manager.list_pickle_files(info['table_name'])
            
            if pickle_files:
                latest_pickle = pickle_files[0]  # 가장 최신 파일
                
                # 설정 업데이트
                config = st.session_state.upload_config.get(data_type, {})
                config['pickle_exists'] = True
                config['dataframe_name'] = info['table_name']
                config['row_count'] = latest_pickle.get('rows', 0)
                config['last_modified'] = latest_pickle.get('created_at', datetime.now().isoformat())
                
                # 파일명 정보가 없으면 description에서 추출 시도
                if not config.get('file_names'):
                    description = latest_pickle.get('description', '')
                    if 'Combined from' in description:
                        # "Combined from X files" 형태에서 파일 수만 표시
                        config['file_names'] = [f"Pickle 파일 ({latest_pickle.get('rows', 0):,}행)"]
                
                # 세션 상태 업데이트
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
    
    def _clear_cache(self):
        """캐시 초기화"""
        # 확인 다이얼로그 표시
        with st.expander("⚠️ 캐시 초기화 확인", expanded=True):
            st.warning("모든 Pickle 캐시가 삭제됩니다. 이 작업은 되돌릴 수 없습니다.")
            
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("확인", type="primary", key="confirm_clear_cache"):
                    try:
                        # 모든 pickle 파일 삭제
                        pickle_dir = Path("data/pickles")
                        if pickle_dir.exists():
                            for file in pickle_dir.glob("*.pkl.gz"):
                                file.unlink()
                        
                        st.success("✅ 캐시가 초기화되었습니다.")
                        time.sleep(1)
                        
                    except Exception as e:
                        st.error(f"캐시 초기화 실패: {e}")
            
            with col2:
                st.info("확인 버튼을 누르면 모든 캐시가 삭제됩니다.")
    
    def _auto_load_pickles(self):
        """자동으로 pickle 파일을 확인하고 로드"""
        self.logger.info("Pickle 파일 자동 로드 시작...")
        
        try:
            # 각 데이터 타입별로 pickle 파일 확인
            for data_type, info in self.data_types.items():
                pickle_files = self.pickle_manager.list_pickle_files(info['table_name'])
                
                if pickle_files:
                    # 가장 최신 pickle 파일 정보 가져오기
                    latest_pickle = pickle_files[0]
                    
                    # 세션 상태 업데이트만 수행 (실제 데이터 로드는 하지 않음)
                    config = st.session_state.upload_config.get(data_type, {})
                    config['pickle_exists'] = True
                    config['dataframe_name'] = info['table_name']
                    config['row_count'] = latest_pickle.get('rows', 0)
                    config['last_modified'] = latest_pickle.get('created_at', datetime.now().isoformat())
                    
                    # 파일명 정보 업데이트
                    if not config.get('file_names'):
                        config['file_names'] = [f"Pickle 파일 ({latest_pickle.get('rows', 0):,}행)"]
                    
                    st.session_state.upload_config[data_type] = config
                    
                    self.logger.info(f"{data_type} 메타데이터 로드 완료: {latest_pickle.get('rows', 0):,}행")
                else:
                    self.logger.info(f"{data_type}에 대한 pickle 파일 없음")
            
            # 설정 저장
            self._save_upload_config()
            
        except Exception as e:
            self.logger.error(f"Pickle 파일 자동 로드 중 오류: {e}")