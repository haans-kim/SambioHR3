"""
작업지시 뷰 최소 버전 생성
"""

import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.database import get_database_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_minimal_view():
    """v_work_order_summary 뷰 생성 (최소 버전)"""
    db_manager = get_database_manager()
    
    try:
        # 기존 뷰 삭제
        logger.info("Dropping existing v_work_order_summary view...")
        db_manager.execute_query("DROP VIEW IF EXISTS v_work_order_summary")
        
        # 새 뷰 생성 (최소 컬럼만)
        create_view_query = """
        CREATE VIEW v_work_order_summary AS
        SELECT 
            wo.order_id,
            wo.order_number,
            wo.title,
            wo.description,
            wo.order_type,
            wo.priority,
            wo.status,
            wo.due_date,
            wo.requester_id,
            wo.requester_name,
            wo.request_date,
            wo.target_type,
            wo.center_id,
            wo.center_name,
            wo.group_id,
            wo.group_name,
            wo.team_id,
            wo.team_name,
            wo.created_at,
            wo.updated_at,
            wo.completed_date as completed_at,
            CASE 
                WHEN wo.status = 'completed' THEN 100
                WHEN wo.status = 'in_progress' THEN 50
                ELSE 0
            END as completion_rate,
            0 as total_items,
            0 as completed_items,
            0 as assigned_employees,
            0 as assignee_count,
            0 as item_count,
            0 as avg_progress_rate
        FROM work_orders wo
        """
        
        logger.info("Creating new v_work_order_summary view...")
        db_manager.execute_query(create_view_query)
        
        logger.info("View created successfully!")
        
        # 뷰 테스트
        result = db_manager.execute_query("SELECT count(*) as cnt FROM v_work_order_summary")
        logger.info(f"View test successful. Row count: {result[0]['cnt'] if result else 0}")
        
        # 컬럼 확인
        columns = db_manager.execute_query("PRAGMA table_info(v_work_order_summary)")
        logger.info("\nView columns:")
        for col in columns:
            if col['name'] == 'requester_id':
                logger.info(f"  ✅ {col['name']} ({col['type']})")
            else:
                logger.info(f"  - {col['name']} ({col['type']})")
            
    except Exception as e:
        logger.error(f"Error creating view: {e}")
        raise


if __name__ == "__main__":
    create_minimal_view()