#!/usr/bin/env python3
"""
API 및 데이터베이스 변경사항 자동 추적 스크립트
Claude Code 작업 시 변경되는 API, DB 스키마 등을 감지하고 문서화합니다.
"""

import os
import sys
import json
import hashlib
import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple
import ast
import re

class ChangeTracker:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.cache_file = self.project_root / ".claude_cache" / "api_tracking.json"
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.changes = []
        self.previous_state = self.load_cache()
        
    def load_cache(self) -> Dict:
        """이전 상태 로드"""
        if self.cache_file.exists():
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_cache(self, current_state: Dict):
        """현재 상태 저장"""
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(current_state, f, indent=2, ensure_ascii=False)
    
    def get_file_hash(self, file_path: Path) -> str:
        """파일 해시 계산"""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def find_python_functions(self, file_path: Path) -> Dict[str, Dict]:
        """Python 파일에서 함수 정의 찾기"""
        functions = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # 함수 시그니처 추출
                    args = []
                    for arg in node.args.args:
                        args.append(arg.arg)
                    
                    functions[node.name] = {
                        'line': node.lineno,
                        'args': args,
                        'docstring': ast.get_docstring(node) or "",
                        'is_async': isinstance(node, ast.AsyncFunctionDef)
                    }
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
        
        return functions
    
    def find_streamlit_pages(self) -> Dict[str, Dict]:
        """Streamlit 페이지 찾기"""
        pages = {}
        
        # streamlit_app.py에서 페이지 정의 찾기
        app_file = self.project_root / "src" / "ui" / "streamlit_app.py"
        if app_file.exists():
            with open(app_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # st.Page 패턴 찾기
            page_pattern = r'st\.Page\s*\(\s*["\']([^"\']+)["\'].*?title\s*=\s*["\']([^"\']+)["\']'
            matches = re.findall(page_pattern, content, re.DOTALL)
            
            for path, title in matches:
                pages[title] = {
                    'path': path,
                    'file': str(app_file.relative_to(self.project_root))
                }
        
        return pages
    
    def find_database_models(self) -> Dict[str, List[str]]:
        """데이터베이스 모델 찾기"""
        models = {}
        
        # 데이터베이스 스키마 파일들
        schema_files = [
            self.project_root / "src" / "database" / "schema.py",
            self.project_root / "src" / "database" / "models.py",
            self.project_root / "src" / "database" / "tag_schema.py"
        ]
        
        for schema_file in schema_files:
            if schema_file.exists():
                with open(schema_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # SQLAlchemy 테이블 정의 찾기
                table_pattern = r'class\s+(\w+)\s*\([^)]*Base[^)]*\):'
                tables = re.findall(table_pattern, content)
                
                if tables:
                    models[str(schema_file.relative_to(self.project_root))] = tables
        
        return models
    
    def track_changes(self):
        """변경사항 추적"""
        current_state = {
            'timestamp': datetime.datetime.now().isoformat(),
            'apis': {},
            'pages': {},
            'models': {},
            'files': {}
        }
        
        # 1. Service Layer API 추적
        service_files = [
            self.project_root / "src" / "analysis" / "individual_analyzer.py",
            self.project_root / "src" / "analysis" / "organization_analyzer.py",
            self.project_root / "src" / "analysis" / "network_analyzer.py",
            self.project_root / "src" / "database" / "db_manager.py"
        ]
        
        for service_file in service_files:
            if service_file.exists():
                functions = self.find_python_functions(service_file)
                file_key = str(service_file.relative_to(self.project_root))
                current_state['apis'][file_key] = functions
                current_state['files'][file_key] = self.get_file_hash(service_file)
        
        # 2. Streamlit 페이지 추적
        current_state['pages'] = self.find_streamlit_pages()
        
        # 3. 데이터베이스 모델 추적
        current_state['models'] = self.find_database_models()
        
        # 4. 변경사항 비교
        if self.previous_state:
            self.compare_states(self.previous_state, current_state)
        
        # 5. 캐시 저장
        self.save_cache(current_state)
        
        return self.changes
    
    def compare_states(self, old_state: Dict, new_state: Dict):
        """상태 비교 및 변경사항 기록"""
        
        # API 변경사항
        for file, functions in new_state['apis'].items():
            if file not in old_state.get('apis', {}):
                self.changes.append({
                    'type': 'api',
                    'action': 'added',
                    'file': file,
                    'details': f"새 서비스 파일: {len(functions)}개 함수"
                })
            else:
                old_functions = old_state['apis'][file]
                # 추가된 함수
                for func_name, func_info in functions.items():
                    if func_name not in old_functions:
                        self.changes.append({
                            'type': 'api',
                            'action': 'added',
                            'file': file,
                            'function': func_name,
                            'details': f"새 함수: {func_name}({', '.join(func_info['args'])})"
                        })
                    elif func_info != old_functions[func_name]:
                        self.changes.append({
                            'type': 'api',
                            'action': 'modified',
                            'file': file,
                            'function': func_name,
                            'details': "함수 시그니처 또는 문서 변경"
                        })
                
                # 삭제된 함수
                for func_name in old_functions:
                    if func_name not in functions:
                        self.changes.append({
                            'type': 'api',
                            'action': 'deleted',
                            'file': file,
                            'function': func_name,
                            'details': f"함수 삭제: {func_name}"
                        })
        
        # 페이지 변경사항
        old_pages = old_state.get('pages', {})
        for title, info in new_state['pages'].items():
            if title not in old_pages:
                self.changes.append({
                    'type': 'page',
                    'action': 'added',
                    'title': title,
                    'details': f"새 페이지: {title} ({info['path']})"
                })
        
        for title in old_pages:
            if title not in new_state['pages']:
                self.changes.append({
                    'type': 'page',
                    'action': 'deleted',
                    'title': title,
                    'details': f"페이지 삭제: {title}"
                })
        
        # 데이터베이스 모델 변경사항
        for file, tables in new_state['models'].items():
            if file not in old_state.get('models', {}):
                self.changes.append({
                    'type': 'database',
                    'action': 'added',
                    'file': file,
                    'details': f"새 스키마 파일: {len(tables)}개 테이블"
                })
            else:
                old_tables = old_state['models'][file]
                added = set(tables) - set(old_tables)
                deleted = set(old_tables) - set(tables)
                
                for table in added:
                    self.changes.append({
                        'type': 'database',
                        'action': 'added',
                        'file': file,
                        'table': table,
                        'details': f"새 테이블: {table}"
                    })
                
                for table in deleted:
                    self.changes.append({
                        'type': 'database',
                        'action': 'deleted',
                        'file': file,
                        'table': table,
                        'details': f"테이블 삭제: {table}"
                    })
    
    def generate_changelog(self) -> str:
        """변경 로그 생성"""
        if not self.changes:
            return "변경사항이 없습니다."
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log = f"# API 변경 로그 - {timestamp}\n\n"
        
        # 타입별로 그룹화
        api_changes = [c for c in self.changes if c['type'] == 'api']
        page_changes = [c for c in self.changes if c['type'] == 'page']
        db_changes = [c for c in self.changes if c['type'] == 'database']
        
        if api_changes:
            log += "## API 변경사항\n"
            for change in api_changes:
                action_emoji = {'added': '➕', 'modified': '📝', 'deleted': '❌'}.get(change['action'], '•')
                log += f"- {action_emoji} {change['details']}\n"
                if 'file' in change:
                    log += f"  - 파일: `{change['file']}`\n"
            log += "\n"
        
        if page_changes:
            log += "## 페이지 변경사항\n"
            for change in page_changes:
                action_emoji = {'added': '➕', 'deleted': '❌'}.get(change['action'], '•')
                log += f"- {action_emoji} {change['details']}\n"
            log += "\n"
        
        if db_changes:
            log += "## 데이터베이스 변경사항\n"
            for change in db_changes:
                action_emoji = {'added': '➕', 'deleted': '❌'}.get(change['action'], '•')
                log += f"- {action_emoji} {change['details']}\n"
                if 'file' in change:
                    log += f"  - 파일: `{change['file']}`\n"
            log += "\n"
        
        return log


def main():
    """메인 함수"""
    if len(sys.argv) > 1:
        project_root = sys.argv[1]
    else:
        project_root = os.getcwd()
    
    tracker = ChangeTracker(project_root)
    changes = tracker.track_changes()
    
    if changes:
        # 변경 로그 생성
        changelog = tracker.generate_changelog()
        print(changelog)
        
        # 변경 로그 파일 저장
        log_dir = Path(project_root) / "doc" / "changes"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"api_changes_{timestamp}.md"
        
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(changelog)
        
        print(f"\n변경 로그 저장됨: {log_file}")
        
        # 최신 변경사항을 LATEST.md로도 저장
        latest_file = log_dir / "LATEST.md"
        with open(latest_file, 'w', encoding='utf-8') as f:
            f.write(changelog)
    else:
        print("변경사항이 없습니다.")


if __name__ == "__main__":
    main()