-- 작업지시 관리 시스템 테이블 생성 스크립트
-- 2025-08-06 Phase 4 구현

-- 1. 작업지시 마스터 테이블
CREATE TABLE IF NOT EXISTS work_orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_number TEXT UNIQUE NOT NULL,  -- WO-2025-0001 형식
    title TEXT NOT NULL,
    description TEXT,
    order_type TEXT NOT NULL,  -- 'analysis', 'report', 'improvement', 'etc'
    priority TEXT NOT NULL DEFAULT 'medium',  -- 'urgent', 'high', 'medium', 'low'
    status TEXT NOT NULL DEFAULT 'draft',  -- 'draft', 'approved', 'assigned', 'in_progress', 'completed', 'cancelled'
    
    -- 요청 정보
    requester_id TEXT NOT NULL,
    requester_name TEXT NOT NULL,
    request_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    due_date DATE,
    
    -- 대상 조직
    target_type TEXT NOT NULL,  -- 'center', 'group', 'team', 'individual'
    center_id TEXT,
    center_name TEXT,
    group_id TEXT,
    group_name TEXT,
    team_id TEXT,
    team_name TEXT,
    
    -- 승인 정보
    approver_id TEXT,
    approver_name TEXT,
    approved_date DATETIME,
    
    -- 완료 정보
    completed_date DATETIME,
    completion_note TEXT,
    
    -- 메타데이터
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. 작업지시 할당 테이블 (담당자 할당)
CREATE TABLE IF NOT EXISTS work_order_assignments (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    assignee_id TEXT NOT NULL,
    assignee_name TEXT NOT NULL,
    assigned_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    assigned_by TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'executor',  -- 'executor', 'reviewer', 'observer'
    status TEXT NOT NULL DEFAULT 'assigned',  -- 'assigned', 'accepted', 'in_progress', 'completed'
    
    -- 진행 정보
    accepted_date DATETIME,
    started_date DATETIME,
    completed_date DATETIME,
    
    -- 메타데이터
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (order_id) REFERENCES work_orders(order_id)
);

-- 3. 작업지시 상세 항목 테이블
CREATE TABLE IF NOT EXISTS work_order_items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    item_number INTEGER NOT NULL,  -- 순번
    item_type TEXT NOT NULL,  -- 'analysis', 'action', 'report'
    description TEXT NOT NULL,
    
    -- 분석 대상 (analysis 타입인 경우)
    target_date_start DATE,
    target_date_end DATE,
    target_employees TEXT,  -- JSON 배열 형태로 저장
    
    -- 상태 관리
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'in_progress', 'completed'
    progress_rate INTEGER DEFAULT 0,  -- 0-100
    
    -- 결과
    result_summary TEXT,
    result_data TEXT,  -- JSON 형태로 저장
    
    -- 메타데이터
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (order_id) REFERENCES work_orders(order_id)
);

-- 4. 작업지시 진행 이력 테이블
CREATE TABLE IF NOT EXISTS work_order_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,  -- 'created', 'updated', 'assigned', 'started', 'completed', 'cancelled'
    action_by TEXT NOT NULL,
    action_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    old_status TEXT,
    new_status TEXT,
    comment TEXT,
    
    FOREIGN KEY (order_id) REFERENCES work_orders(order_id)
);

-- 5. 작업지시 파일 첨부 테이블
CREATE TABLE IF NOT EXISTS work_order_attachments (
    attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT,
    file_size INTEGER,
    uploaded_by TEXT NOT NULL,
    uploaded_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (order_id) REFERENCES work_orders(order_id)
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_work_orders_status ON work_orders(status);
CREATE INDEX IF NOT EXISTS idx_work_orders_requester ON work_orders(requester_id);
CREATE INDEX IF NOT EXISTS idx_work_orders_due_date ON work_orders(due_date);
CREATE INDEX IF NOT EXISTS idx_work_orders_target ON work_orders(target_type, center_id, group_id, team_id);

CREATE INDEX IF NOT EXISTS idx_assignments_order ON work_order_assignments(order_id);
CREATE INDEX IF NOT EXISTS idx_assignments_assignee ON work_order_assignments(assignee_id);
CREATE INDEX IF NOT EXISTS idx_assignments_status ON work_order_assignments(status);

CREATE INDEX IF NOT EXISTS idx_items_order ON work_order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_items_status ON work_order_items(status);

CREATE INDEX IF NOT EXISTS idx_history_order ON work_order_history(order_id);
CREATE INDEX IF NOT EXISTS idx_history_date ON work_order_history(action_date);

-- 뷰 생성

-- 작업지시 현황 뷰
CREATE VIEW IF NOT EXISTS v_work_order_summary AS
SELECT 
    wo.order_id,
    wo.order_number,
    wo.title,
    wo.order_type,
    wo.priority,
    wo.status,
    wo.requester_name,
    wo.request_date,
    wo.due_date,
    wo.target_type,
    wo.center_name,
    wo.group_name,
    wo.team_name,
    COUNT(DISTINCT woa.assignee_id) as assignee_count,
    COUNT(DISTINCT woi.item_id) as item_count,
    AVG(woi.progress_rate) as avg_progress_rate,
    CASE 
        WHEN wo.status = 'completed' THEN 100
        WHEN COUNT(woi.item_id) = 0 THEN 0
        ELSE CAST(COUNT(CASE WHEN woi.status = 'completed' THEN 1 END) AS FLOAT) / COUNT(woi.item_id) * 100
    END as completion_rate
FROM work_orders wo
LEFT JOIN work_order_assignments woa ON wo.order_id = woa.order_id
LEFT JOIN work_order_items woi ON wo.order_id = woi.order_id
GROUP BY wo.order_id;

-- 담당자별 작업지시 현황 뷰
CREATE VIEW IF NOT EXISTS v_assignee_work_orders AS
SELECT 
    woa.assignee_id,
    woa.assignee_name,
    wo.order_id,
    wo.order_number,
    wo.title,
    wo.priority,
    wo.due_date,
    woa.role,
    woa.status as assignment_status,
    wo.status as order_status,
    COUNT(woi.item_id) as total_items,
    COUNT(CASE WHEN woi.status = 'completed' THEN 1 END) as completed_items
FROM work_order_assignments woa
JOIN work_orders wo ON woa.order_id = wo.order_id
LEFT JOIN work_order_items woi ON wo.order_id = woi.order_id
GROUP BY woa.assignment_id;

-- 조직별 작업지시 현황 뷰
CREATE VIEW IF NOT EXISTS v_organization_work_orders AS
SELECT 
    target_type,
    center_name,
    group_name,
    team_name,
    COUNT(DISTINCT order_id) as total_orders,
    COUNT(DISTINCT CASE WHEN status = 'draft' THEN order_id END) as draft_orders,
    COUNT(DISTINCT CASE WHEN status = 'assigned' THEN order_id END) as assigned_orders,
    COUNT(DISTINCT CASE WHEN status = 'in_progress' THEN order_id END) as in_progress_orders,
    COUNT(DISTINCT CASE WHEN status = 'completed' THEN order_id END) as completed_orders
FROM work_orders
GROUP BY target_type, center_name, group_name, team_name;