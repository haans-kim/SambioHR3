"""
작업지시 관련 테이블 및 뷰 생성 스크립트
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


def create_work_order_tables():
    """작업지시 관련 테이블 생성"""
    db_manager = get_database_manager()
    
    # work_orders 테이블 생성
    create_work_orders_table = """
    CREATE TABLE IF NOT EXISTS work_orders (
        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number VARCHAR(20) UNIQUE NOT NULL,
        title VARCHAR(200) NOT NULL,
        description TEXT,
        order_type VARCHAR(50) NOT NULL,
        priority VARCHAR(20) NOT NULL,
        status VARCHAR(20) DEFAULT 'created',
        due_date DATE,
        requester_id VARCHAR(50) NOT NULL,
        requester_name VARCHAR(100) NOT NULL,
        target_type VARCHAR(20) NOT NULL,
        center_id VARCHAR(10),
        center_name VARCHAR(100),
        group_id VARCHAR(10),
        group_name VARCHAR(100),
        team_id VARCHAR(10),
        team_name VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        completion_rate REAL DEFAULT 0
    );
    """
    
    # work_order_items 테이블 생성
    create_work_order_items_table = """
    CREATE TABLE IF NOT EXISTS work_order_items (
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        employee_id VARCHAR(20),
        employee_name VARCHAR(100),
        center_id VARCHAR(10),
        center_name VARCHAR(100),
        group_id VARCHAR(10),
        group_name VARCHAR(100),
        team_id VARCHAR(10),
        team_name VARCHAR(100),
        target_date DATE,
        completed BOOLEAN DEFAULT 0,
        completed_at TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES work_orders (order_id)
    );
    """
    
    # work_order_progress 테이블 생성
    create_work_order_progress_table = """
    CREATE TABLE IF NOT EXISTS work_order_progress (
        progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        item_id INTEGER,
        action_type VARCHAR(50) NOT NULL,
        action_by VARCHAR(50) NOT NULL,
        action_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        comment TEXT,
        FOREIGN KEY (order_id) REFERENCES work_orders (order_id),
        FOREIGN KEY (item_id) REFERENCES work_order_items (item_id)
    );
    """
    
    # v_work_order_summary 뷰 생성
    create_work_order_summary_view = """
    CREATE VIEW IF NOT EXISTS v_work_order_summary AS
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
        wo.target_type,
        wo.center_id,
        wo.center_name,
        wo.group_id,
        wo.group_name,
        wo.team_id,
        wo.team_name,
        wo.created_at,
        wo.updated_at,
        wo.completed_at,
        wo.completion_rate,
        COUNT(DISTINCT woi.item_id) as total_items,
        COUNT(DISTINCT CASE WHEN woi.completed = 1 THEN woi.item_id END) as completed_items,
        COUNT(DISTINCT woi.employee_id) as assigned_employees
    FROM work_orders wo
    LEFT JOIN work_order_items woi ON wo.order_id = woi.order_id
    GROUP BY wo.order_id;
    """
    
    try:
        # 테이블 생성
        logger.info("Creating work_orders table...")
        db_manager.execute_query(create_work_orders_table)
        
        logger.info("Creating work_order_items table...")
        db_manager.execute_query(create_work_order_items_table)
        
        logger.info("Creating work_order_progress table...")
        db_manager.execute_query(create_work_order_progress_table)
        
        logger.info("Creating v_work_order_summary view...")
        db_manager.execute_query(create_work_order_summary_view)
        
        logger.info("All work order tables and views created successfully!")
        
        # 인덱스 생성
        create_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_work_orders_requester ON work_orders(requester_id);",
            "CREATE INDEX IF NOT EXISTS idx_work_orders_status ON work_orders(status);",
            "CREATE INDEX IF NOT EXISTS idx_work_orders_due_date ON work_orders(due_date);",
            "CREATE INDEX IF NOT EXISTS idx_work_order_items_order ON work_order_items(order_id);",
            "CREATE INDEX IF NOT EXISTS idx_work_order_items_employee ON work_order_items(employee_id);",
            "CREATE INDEX IF NOT EXISTS idx_work_order_progress_order ON work_order_progress(order_id);"
        ]
        
        for index_query in create_indexes:
            db_manager.execute_query(index_query)
        
        logger.info("Indexes created successfully!")
        
    except Exception as e:
        logger.error(f"Error creating work order tables: {e}")
        raise


if __name__ == "__main__":
    create_work_order_tables()