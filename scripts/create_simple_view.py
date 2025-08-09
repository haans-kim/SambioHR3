"""
작업지시 뷰 간단히 생성
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


def create_simple_view():
    """v_work_order_summary 뷰 생성 (간단한 버전)"""
    db_manager = get_database_manager()
    
    try:
        # 기존 뷰 삭제
        logger.info("Dropping existing v_work_order_summary view...")
        db_manager.execute_query("DROP VIEW IF EXISTS v_work_order_summary")
        
        # 새 뷰 생성 (실제 컬럼만 사용)
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
            COUNT(DISTINCT woi.item_id) as total_items,
            COUNT(DISTINCT CASE WHEN woi.completed = 1 THEN woi.item_id END) as completed_items,
            COUNT(DISTINCT woi.employee_id) as assigned_employees,
            COUNT(DISTINCT woa.employee_id) as assignee_count,
            COUNT(DISTINCT woi.item_id) as item_count,
            CASE 
                WHEN COUNT(woi.item_id) > 0 
                THEN (COUNT(DISTINCT CASE WHEN woi.completed = 1 THEN woi.item_id END) * 100.0 / COUNT(DISTINCT woi.item_id))
                ELSE 0 
            END as avg_progress_rate
        FROM work_orders wo
        LEFT JOIN work_order_items woi ON wo.order_id = woi.order_id
        LEFT JOIN work_order_assignments woa ON wo.order_id = woa.order_id
        GROUP BY wo.order_id
        """
        
        logger.info("Creating new v_work_order_summary view...")
        db_manager.execute_query(create_view_query)
        
        logger.info("View created successfully!")
        
        # 뷰 구조 확인
        result = db_manager.execute_query("SELECT * FROM v_work_order_summary LIMIT 1")
        logger.info(f"\nView test query successful. Row count: {len(result)}")
            
    except Exception as e:
        logger.error(f"Error creating view: {e}")
        raise


if __name__ == "__main__":
    create_simple_view()