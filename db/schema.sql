-- ============================================================
-- 数据库Schema定义
-- 项目: pytest_sxp API测试框架
-- ============================================================

-- ============================================================
-- 1. tasks表 - 任务表
-- ============================================================

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id VARCHAR(36) UNIQUE NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    params TEXT,
    document_id INTEGER,
    interface_ids TEXT,
    result TEXT,
    error_message TEXT,
    progress INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);

-- ============================================================
-- 2. documents表 - 文档表
-- ============================================================

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id VARCHAR(36),
    doc_name VARCHAR(255) NOT NULL,
    doc_type VARCHAR(50) NOT NULL,
    doc_content TEXT,
    is_current BOOLEAN DEFAULT TRUE,
    is_history BOOLEAN DEFAULT FALSE,
    version VARCHAR(20),
    is_latest BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    approved_at DATETIME,
    approved_by VARCHAR(100)
);

-- ============================================================
-- 3. interfaces表 - 接口信息表
-- ============================================================

CREATE TABLE IF NOT EXISTS interfaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER,
    interface_name VARCHAR(255),
    method VARCHAR(10),
    path VARCHAR(500),
    request_params TEXT,
    response_params TEXT,
    business_rules TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

-- ============================================================
-- 4. assertion_configs表 - 断言配置表
-- ============================================================

CREATE TABLE IF NOT EXISTS assertion_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interface_id INTEGER,
    version VARCHAR(20) NOT NULL,
    assertion_template TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (interface_id) REFERENCES interfaces(id)
);

-- ============================================================
-- 5. test_data_configs表 - 测试数据配置表
-- ============================================================

CREATE TABLE IF NOT EXISTS test_data_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interface_id INTEGER,
    dataset_name VARCHAR(255) NOT NULL,
    param_configs TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (interface_id) REFERENCES interfaces(id)
);

-- ============================================================
-- 6. exception_codes表 - 异常码表（交易模块）
-- ============================================================

CREATE TABLE IF NOT EXISTS exception_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(50) UNIQUE NOT NULL,
    description VARCHAR(500),
    http_status INTEGER,
    response_code VARCHAR(50),
    suggestion TEXT,
    module VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 插入初始异常码数据（交易模块）
-- ============================================================

-- 订单模块
INSERT INTO exception_codes (code, description, http_status, response_code, suggestion, module) VALUES
('ORDER_001', '订单不存在', 200, '10001', '检查订单号是否正确', 'order'),
('ORDER_002', '订单已取消', 200, '10002', '该订单已取消，无法继续操作', 'order'),
('ORDER_003', '订单已完成', 200, '10003', '该订单已完成，无法重复操作', 'order'),
('ORDER_004', '订单状态不允许该操作', 200, '10004', '检查订单当前状态', 'order'),
('ORDER_005', '订单金额不匹配', 200, '10005', '核对订单金额是否一致', 'order');

-- 支付模块
INSERT INTO exception_codes (code, description, http_status, response_code, suggestion, module) VALUES
('PAY_001', '支付渠道不可用', 200, '20001', '切换其他支付方式', 'payment'),
('PAY_002', '支付金额超限', 200, '20002', '单笔或单日累计超限，请分笔支付', 'payment'),
('PAY_003', '余额不足', 200, '20003', '账户余额不足，请充值', 'payment'),
('PAY_004', '支付密码错误', 200, '20004', '输入正确的支付密码', 'payment'),
('PAY_005', '支付超时', 200, '20005', '请重新发起支付', 'payment'),
('PAY_006', '支付单已存在', 200, '20006', '订单已存在支付单，请勿重复提交', 'payment');

-- 退款模块
INSERT INTO exception_codes (code, description, http_status, response_code, suggestion, module) VALUES
('REFUND_001', '退款订单不存在', 200, '30001', '检查退款单号是否正确', 'refund'),
('REFUND_002', '订单已退款', 200, '30002', '该订单已全部退款', 'refund'),
('REFUND_003', '退款金额超限', 200, '30003', '退款金额不能超过支付金额', 'refund'),
('REFUND_004', '退款超过允许时间', 200, '30004', '订单支付超过可退款期限', 'refund'),
('REFUND_005', '退款处理中', 200, '30005', '退款正在处理中，请稍后查询', 'refund');

-- 通用异常
INSERT INTO exception_codes (code, description, http_status, response_code, suggestion, module) VALUES
('COMMON_001', '系统繁忙', 500, '50001', '稍后重试或联系客服', 'common'),
('COMMON_002', '参数错误', 400, '40001', '检查请求参数是否正确', 'common'),
('COMMON_003', '签名验证失败', 401, '40101', '检查签名是否正确', 'common'),
('COMMON_004', '权限不足', 403, '40301', '联系管理员开通权限', 'common');
