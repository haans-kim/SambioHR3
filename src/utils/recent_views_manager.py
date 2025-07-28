"""
최근 조회 기록 관리 모듈
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import streamlit as st

class RecentViewsManager:
    """최근 조회 기록을 관리하는 클래스"""
    
    def __init__(self, max_items: int = 5):
        self.max_items = max_items
        self.file_path = Path.home() / ".sambio_hr" / "recent_views.json"
        self._ensure_directory()
        self._load_recent_views()
    
    def _ensure_directory(self):
        """설정 디렉토리 생성"""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _load_recent_views(self):
        """저장된 최근 조회 기록 로드"""
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self.recent_views = json.load(f)
            except:
                self.recent_views = []
        else:
            self.recent_views = []
    
    def _save_recent_views(self):
        """최근 조회 기록 저장"""
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.recent_views, f, ensure_ascii=False, indent=2)
    
    def add_view(self, employee_id: str, employee_name: str, 
                 analysis_date: str, department: Optional[str] = None):
        """새로운 조회 기록 추가"""
        view_data = {
            "employee_id": employee_id,
            "employee_name": employee_name,
            "analysis_date": analysis_date,
            "department": department,
            "viewed_at": datetime.now().isoformat(),
            "view_key": f"{employee_id}_{analysis_date}"  # 중복 체크용
        }
        
        # 중복 제거
        self.recent_views = [v for v in self.recent_views 
                           if v.get('view_key') != view_data['view_key']]
        
        # 맨 앞에 추가
        self.recent_views.insert(0, view_data)
        
        # 최대 개수 유지
        self.recent_views = self.recent_views[:self.max_items]
        
        # 저장
        self._save_recent_views()
    
    def get_recent_views(self) -> List[Dict]:
        """최근 조회 기록 반환"""
        return self.recent_views
    
    def clear_all(self):
        """모든 기록 삭제"""
        self.recent_views = []
        self._save_recent_views()
    
    def remove_view(self, view_key: str):
        """특정 조회 기록 삭제"""
        self.recent_views = [v for v in self.recent_views 
                           if v.get('view_key') != view_key]
        self._save_recent_views()


def render_recent_views_section(recent_views_manager: RecentViewsManager):
    """Streamlit UI에서 최근 조회 섹션 렌더링 - 이제는 사용하지 않음"""
    # 이 함수는 더 이상 사용되지 않지만 호환성을 위해 유지
    return None