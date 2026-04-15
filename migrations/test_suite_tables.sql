-- ===============================================
-- 测试套件表 SQL 脚本
-- 文件: migrations/test_suite_tables.sql
-- 说明: 重建 test_suite 和 test_suite_case 表
-- ===============================================

-- ===============================================
-- 1. 删除旧表（如果存在）
-- ===============================================
DROP TABLE IF EXISTS crosstest_test_suite_case;
DROP TABLE IF EXISTS crosstest_test_suite;

-- ===============================================
-- 2. 创建 test_suite 表
-- ===============================================
CREATE TABLE crosstest_test_suite (
    -- 基础字段
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    name VARCHAR(200) NOT NULL COMMENT '套件名称',
    description VARCHAR(1000) COMMENT '套件描述',

    -- 分类信息
    suite_type ENUM('smoke', 'regression', 'function', 'performance', 'custom')
        NOT NULL DEFAULT 'custom' COMMENT '套件类型: smoke-冒烟, regression-回归, function-功能, performance-性能, custom-自定义',
    module VARCHAR(100) COMMENT '所属模块',

    -- 配置信息
    tags JSON COMMENT '标签数组',
    config JSON COMMENT '套件配置',

    -- 新增: 执行状态字段
    last_execution_status ENUM('not_run', 'running', 'passed', 'failed', 'stopped')
        DEFAULT 'not_run' COMMENT '最近一次执行状态: not_run-未执行, running-执行中, passed-通过, failed-失败, stopped-停止',
    last_execution_time DATETIME COMMENT '最近一次执行时间',
    last_execution_id VARCHAR(50) COMMENT '最近一次执行的执行ID',
    total_executions INT DEFAULT 0 COMMENT '累计执行次数',
    success_rate DECIMAL(5, 2) DEFAULT 0.00 COMMENT '累计成功率(%)',

    -- 新增: 套件级默认请求配置
    -- 说明: 这些配置会被套件下所有用例继承（如果没有单独配置）
    case_default_config JSON COMMENT '套件下所有用例的默认请求配置(headers/params/body等)',

    -- 状态管理
    status ENUM('active', 'inactive')
        NOT NULL DEFAULT 'active' COMMENT '状态: active-激活, inactive-未激活',

    -- 审计字段
    creator VARCHAR(50) NOT NULL COMMENT '创建人',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    -- 索引
    UNIQUE KEY uk_suite_name (name),
    INDEX idx_suite_type (suite_type),
    INDEX idx_module (module),
    INDEX idx_status (status),
    INDEX idx_last_execution_time (last_execution_time),
    INDEX idx_suite_type_status (suite_type, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试套件表';


-- ===============================================
-- 3. 创建 test_suite_case 表
-- ===============================================
CREATE TABLE crosstest_test_suite_case (
    -- 主键
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',

    -- 外键关联
    suite_id INT NOT NULL COMMENT '套件ID',
    case_id INT NOT NULL COMMENT '用例ID',

    -- 用例基本信息（从 test_case 复制冗余存储，避免每次查询都 JOIN）
    name VARCHAR(200) COMMENT '用例名称(冗余存储)',
    case_id_str VARCHAR(50) COMMENT '业务用例编号(冗余存储)',

    -- 关联配置
    execution_order INT DEFAULT 0 COMMENT '执行顺序',
    enabled BOOLEAN DEFAULT TRUE COMMENT '是否启用',

    -- 独立请求配置字段
    -- 说明: 如果这些字段有值，则使用这些值；否则回退到 test_case 表的配置
    url VARCHAR(500) COMMENT '请求URL(独立配置，为空则继承用例)',
    request_headers JSON COMMENT '请求头(独立配置)',
    request_params JSON COMMENT '请求参数(独立配置)',
    request_body JSON COMMENT '请求体(独立配置)',
    timeout INT DEFAULT 30 COMMENT '超时秒数',
    assertions JSON COMMENT '断言配置(独立配置)',

    -- 扩展配置字段
    config JSON COMMENT '其他配置(JSON)',

    -- 用例内容字段（优先级: suite_case 自己的 > 从 test_case 复制过来的）
    preconditions TEXT COMMENT '前置条件(可独立覆盖)',
    test_steps JSON COMMENT '测试步骤(可独立覆盖)',
    test_data JSON COMMENT '测试数据(可独立覆盖)',

    -- 审计字段
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    -- 索引
    INDEX idx_suite_id (suite_id),
    INDEX idx_case_id (case_id),
    INDEX idx_suite_case (suite_id, case_id),
    INDEX idx_execution_order (suite_id, execution_order),
    INDEX idx_enabled (enabled),

    -- 外键约束
    CONSTRAINT fk_suite_case_suite FOREIGN KEY (suite_id)
        REFERENCES crosstest_test_suite(id) ON DELETE CASCADE,
    CONSTRAINT fk_suite_case_case FOREIGN KEY (case_id)
        REFERENCES crosstest_test_case(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试套件-用例关联表';


-- ===============================================
-- 4. case_default_config 字段结构说明
-- =============================================
/*
case_default_config 结构示例:
{
    "default_headers": {
        "X-Suite-ID": "suite_001",
        "X-Environment": "test"
    },
    "default_params": {
        "platform": "web"
    },
    "default_timeout": 60,
    "default_retry_count": 1
}
*/

-- ===============================================
-- 5. 初始化数据示例（可选）
-- =============================================
/*
INSERT INTO crosstest_test_suite (name, description, suite_type, module, creator)
VALUES
    ('用户模块冒烟测试', '用户相关核心接口冒烟测试', 'smoke', '用户中心', 'admin'),
    ('支付模块回归测试', '支付全流程回归测试套件', 'regression', '支付中心', 'admin');
*/
