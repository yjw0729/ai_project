-- 任务执行记录表
-- 用于追踪所有异步任务（用例生成、测试执行、报告生成等）的完整生命周期
-- 配合 Redis 实现"双写"：Redis 快速查询 + MySQL 持久化

CREATE TABLE IF NOT EXISTS crosstest_task_execution (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键',

    -- 核心标识
    task_id VARCHAR(100) NOT NULL UNIQUE COMMENT '任务唯一ID(UUID)',
    user_id VARCHAR(50) NOT NULL COMMENT '用户ID（发起人）',

    -- 任务分类
    task_type VARCHAR(50) NOT NULL COMMENT '任务类型: llm.generate, test.execute, rag.index, report.generate',
    description VARCHAR(500) COMMENT '任务描述',
    priority INT DEFAULT 5 COMMENT '优先级 1-10，数字越小优先级越高',

    -- 任务参数（JSON，保存创建时的请求参数）
    payload JSON COMMENT '任务参数',

    -- 状态流转
    -- pending → queued → running → completed/failed/cancelled
    status ENUM('pending', 'queued', 'running', 'completed', 'failed', 'cancelled', 'retrying')
        NOT NULL DEFAULT 'pending' COMMENT '任务状态',

    -- 结果（JSON，保存执行结果）
    result JSON COMMENT '任务结果',

    -- 错误信息
    error_code VARCHAR(50) COMMENT '错误码',
    error_message TEXT COMMENT '错误详情',

    -- 重试信息
    retry_count INT DEFAULT 0 COMMENT '当前重试次数',
    max_retries INT DEFAULT 3 COMMENT '最大重试次数',

    -- 链路追踪
    trace_id VARCHAR(100) COMMENT '链路追踪ID',

    -- 时间戳
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    queued_time DATETIME COMMENT '入队时间',
    started_time DATETIME COMMENT '开始执行时间',
    finished_time DATETIME COMMENT '完成时间',

    -- 进度信息（字符串格式，如 "5/100"）
    progress VARCHAR(50) DEFAULT '0' COMMENT '进度描述',

    -- 审计字段
    created_by VARCHAR(50) COMMENT '创建人',
    updated_by VARCHAR(50) COMMENT '更新人',

    -- 索引
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    INDEX idx_task_type (task_type),
    INDEX idx_created_time (created_time),
    INDEX idx_user_status (user_id, status),
    INDEX idx_trace_id (trace_id)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='任务执行记录表（支持健壮性的异步任务追踪）';
