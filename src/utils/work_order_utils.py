"""
작업지시 관리 유틸리티 클래스
데이터베이스 CRUD 작업 및 비즈니스 로직 처리
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import json

logger = logging.getLogger(__name__)


class WorkOrderManager:
    """작업지시 관리 클래스"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
    
    def create_work_order(self, 
                         title: str,
                         description: str,
                         order_type: str,
                         priority: str,
                         due_date: Optional[str],
                         requester_id: str,
                         requester_name: str,
                         target_type: str,
                         center_name: Optional[str] = None,
                         group_name: Optional[str] = None,
                         team_name: Optional[str] = None,
                         items: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """새 작업지시 생성"""
        try:
            # 작업지시 번호 생성
            order_number = self.generate_order_number()
            
            # 작업지시 마스터 생성
            insert_query = """
            INSERT INTO work_orders (
                order_number, title, description, order_type, priority,
                due_date, requester_id, requester_name, target_type,
                center_id, center_name, group_id, group_name, team_id, team_name
            ) VALUES (
                :order_number, :title, :description, :order_type, :priority,
                :due_date, :requester_id, :requester_name, :target_type,
                :center_id, :center_name, :group_id, :group_name, :team_id, :team_name
            )
            """
            
            params = {
                'order_number': order_number,
                'title': title,
                'description': description,
                'order_type': order_type,
                'priority': priority,
                'due_date': due_date.isoformat() if due_date else None,
                'requester_id': requester_id,
                'requester_name': requester_name,
                'target_type': target_type,
                'center_id': center_name,
                'center_name': center_name,
                'group_id': group_name,
                'group_name': group_name,
                'team_id': team_name,
                'team_name': team_name
            }
            
            # 트랜잭션 시작
            with self.db_manager.engine.begin() as conn:
                result = conn.execute(insert_query, params)
                order_id = result.lastrowid
                
                # 세부 항목 생성
                if items:
                    for i, item in enumerate(items):
                        item_query = """
                        INSERT INTO work_order_items (
                            order_id, item_number, item_type, description,
                            target_date_start, target_date_end
                        ) VALUES (
                            :order_id, :item_number, :item_type, :description,
                            :target_date_start, :target_date_end
                        )
                        """
                        
                        item_params = {
                            'order_id': order_id,
                            'item_number': i + 1,
                            'item_type': item.get('item_type', 'analysis'),
                            'description': item.get('description', ''),
                            'target_date_start': item.get('target_date_start'),
                            'target_date_end': item.get('target_date_end')
                        }
                        
                        conn.execute(item_query, item_params)
                
                # 이력 생성
                history_query = """
                INSERT INTO work_order_history (
                    order_id, action_type, action_by, new_status, comment
                ) VALUES (
                    :order_id, 'created', :action_by, 'draft', '작업지시 생성'
                )
                """
                
                conn.execute(history_query, {
                    'order_id': order_id,
                    'action_by': requester_name
                })
            
            logger.info(f"작업지시 생성 완료: {order_number}")
            
            return {
                'success': True,
                'order_id': order_id,
                'order_number': order_number
            }
            
        except Exception as e:
            logger.error(f"작업지시 생성 실패: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_order_number(self) -> str:
        """작업지시 번호 생성"""
        year = datetime.now().year
        
        # 올해 마지막 번호 조회
        query = """
        SELECT MAX(CAST(SUBSTR(order_number, -4) AS INTEGER)) as last_number
        FROM work_orders
        WHERE order_number LIKE :prefix
        """
        
        result = self.db_manager.execute_query(query, {'prefix': f'WO-{year}-%'})
        
        if result and result[0]['last_number']:
            next_number = result[0]['last_number'] + 1
        else:
            next_number = 1
        
        return f"WO-{year}-{next_number:04d}"
    
    def get_assigned_work_orders(self, assignee_id: str) -> List[Dict]:
        """담당 작업지시 목록 조회"""
        query = """
        SELECT 
            wo.*,
            woa.role,
            woa.status as assignment_status,
            woa.assigned_date,
            COUNT(woi.item_id) as item_count,
            AVG(woi.progress_rate) as completion_rate
        FROM work_order_assignments woa
        JOIN work_orders wo ON woa.order_id = wo.order_id
        LEFT JOIN work_order_items woi ON wo.order_id = woi.order_id
        WHERE woa.assignee_id = :assignee_id
        AND woa.status != 'completed'
        GROUP BY wo.order_id, woa.assignment_id
        ORDER BY wo.priority DESC, wo.due_date ASC
        """
        
        return self.db_manager.execute_query(query, {'assignee_id': assignee_id})
    
    def get_requested_work_orders(self, requester_id: str) -> List[Dict]:
        """요청한 작업지시 목록 조회"""
        query = """
        SELECT * FROM v_work_order_summary
        WHERE requester_id = :requester_id
        ORDER BY created_at DESC
        """
        
        return self.db_manager.execute_query(query, {'requester_id': requester_id})
    
    def get_work_order_items(self, order_id: int) -> List[Dict]:
        """작업지시 세부 항목 조회"""
        query = """
        SELECT * FROM work_order_items
        WHERE order_id = :order_id
        ORDER BY item_number
        """
        
        return self.db_manager.execute_query(query, {'order_id': order_id})
    
    def update_item_progress(self, item_id: int, progress_rate: int) -> bool:
        """항목 진행률 업데이트"""
        try:
            # 상태 자동 업데이트
            if progress_rate == 0:
                status = 'pending'
            elif progress_rate == 100:
                status = 'completed'
            else:
                status = 'in_progress'
            
            query = """
            UPDATE work_order_items
            SET progress_rate = :progress_rate,
                status = :status,
                updated_at = CURRENT_TIMESTAMP
            WHERE item_id = :item_id
            """
            
            self.db_manager.execute_query(query, {
                'item_id': item_id,
                'progress_rate': progress_rate,
                'status': status
            })
            
            return True
            
        except Exception as e:
            logger.error(f"진행률 업데이트 실패: {e}")
            return False
    
    def complete_assignment(self, order_id: int, assignee_id: str) -> bool:
        """작업 완료 처리"""
        try:
            with self.db_manager.engine.begin() as conn:
                # 담당자 완료 처리
                query = """
                UPDATE work_order_assignments
                SET status = 'completed',
                    completed_date = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE order_id = :order_id AND assignee_id = :assignee_id
                """
                
                conn.execute(query, {
                    'order_id': order_id,
                    'assignee_id': assignee_id
                })
                
                # 모든 담당자가 완료했는지 확인
                check_query = """
                SELECT COUNT(*) as pending_count
                FROM work_order_assignments
                WHERE order_id = :order_id AND status != 'completed'
                """
                
                result = conn.execute(check_query, {'order_id': order_id})
                pending_count = result.fetchone()[0]
                
                # 모두 완료했으면 작업지시도 완료 처리
                if pending_count == 0:
                    order_query = """
                    UPDATE work_orders
                    SET status = 'completed',
                        completed_date = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE order_id = :order_id
                    """
                    
                    conn.execute(order_query, {'order_id': order_id})
                    
                    # 이력 추가
                    history_query = """
                    INSERT INTO work_order_history (
                        order_id, action_type, action_by, 
                        old_status, new_status, comment
                    ) VALUES (
                        :order_id, 'completed', :action_by,
                        'in_progress', 'completed', '작업 완료'
                    )
                    """
                    
                    conn.execute(history_query, {
                        'order_id': order_id,
                        'action_by': assignee_id
                    })
            
            return True
            
        except Exception as e:
            logger.error(f"작업 완료 처리 실패: {e}")
            return False
    
    def get_overall_statistics(self) -> Dict[str, Any]:
        """전체 통계 조회"""
        query = """
        SELECT 
            COUNT(DISTINCT order_id) as total_orders,
            COUNT(DISTINCT CASE WHEN status = 'in_progress' THEN order_id END) as in_progress_orders,
            COUNT(DISTINCT CASE WHEN status = 'completed' THEN order_id END) as completed_orders,
            AVG(completion_rate) as avg_completion_rate
        FROM v_work_order_summary
        """
        
        result = self.db_manager.execute_query(query)
        return result[0] if result else None
    
    def get_organization_statistics(self) -> List[Dict]:
        """조직별 통계 조회"""
        query = """
        SELECT * FROM v_organization_work_orders
        ORDER BY center_name, group_name, team_name
        """
        
        return self.db_manager.execute_query(query)
    
    def get_assignee_statistics(self) -> List[Dict]:
        """담당자별 통계 조회"""
        query = """
        SELECT 
            assignee_name,
            COUNT(DISTINCT order_id) as total_orders,
            COUNT(DISTINCT CASE WHEN assignment_status = 'completed' THEN order_id END) as completed_orders,
            COUNT(total_items) as total_items,
            SUM(completed_items) as completed_items,
            ROUND(AVG(CAST(completed_items AS FLOAT) / NULLIF(total_items, 0) * 100), 1) as avg_completion_rate
        FROM v_assignee_work_orders
        GROUP BY assignee_id, assignee_name
        ORDER BY total_orders DESC
        """
        
        return self.db_manager.execute_query(query)
    
    def assign_work_order(self, order_id: int, assignee_id: str, assignee_name: str, 
                         assigned_by: str, role: str = 'executor') -> bool:
        """작업지시 할당"""
        try:
            # 할당 생성
            query = """
            INSERT INTO work_order_assignments (
                order_id, assignee_id, assignee_name, assigned_by, role
            ) VALUES (
                :order_id, :assignee_id, :assignee_name, :assigned_by, :role
            )
            """
            
            self.db_manager.execute_query(query, {
                'order_id': order_id,
                'assignee_id': assignee_id,
                'assignee_name': assignee_name,
                'assigned_by': assigned_by,
                'role': role
            })
            
            # 작업지시 상태 업데이트
            update_query = """
            UPDATE work_orders
            SET status = 'assigned',
                updated_at = CURRENT_TIMESTAMP
            WHERE order_id = :order_id AND status = 'draft'
            """
            
            self.db_manager.execute_query(update_query, {'order_id': order_id})
            
            # 이력 추가
            history_query = """
            INSERT INTO work_order_history (
                order_id, action_type, action_by, 
                old_status, new_status, comment
            ) VALUES (
                :order_id, 'assigned', :action_by,
                'draft', 'assigned', :comment
            )
            """
            
            self.db_manager.execute_query(history_query, {
                'order_id': order_id,
                'action_by': assigned_by,
                'comment': f'{assignee_name}에게 할당됨'
            })
            
            return True
            
        except Exception as e:
            logger.error(f"작업지시 할당 실패: {e}")
            return False