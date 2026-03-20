-- 创建文档审核汇总表
-- 用于列表查询，避免扫描含大字段的 crosstest_review_record 表

CREATE TABLE IF NOT EXISTS `crosstest_review_summary` (
    `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `doc_id` VARCHAR(64) NOT NULL COMMENT '文档UUID（唯一）',
    `document_title` VARCHAR(200) NOT NULL COMMENT '文档标题',
    `business_module` VARCHAR(100) DEFAULT NULL COMMENT '业务模块',
    `interface_count` INT DEFAULT 0 COMMENT '识别到的接口数量',
    `image_count` INT DEFAULT 0 COMMENT '提取到的图片总数',
    `general_image_count` INT DEFAULT 0 COMMENT '知识类图片数量（未匹配到接口）',
    `test_case_count` INT DEFAULT 0 COMMENT '生成的测试用例数量',
    `status` ENUM('pending','approved','rejected') NOT NULL DEFAULT 'pending' COMMENT '审核状态: pending-待审核, approved-已通过, rejected-已拒绝',
    `xmind_file_path` VARCHAR(500) DEFAULT NULL COMMENT '生成的XMind文件路径',
    `creator` VARCHAR(50) NOT NULL DEFAULT 'system' COMMENT '创建人',
    `reviewer` VARCHAR(50) DEFAULT NULL COMMENT '审核人',
    `review_comment` TEXT DEFAULT NULL COMMENT '审核意见',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_doc_id` (`doc_id`),
    KEY `idx_status` (`status`),
    KEY `idx_business_module` (`business_module`),
    KEY `idx_created_time` (`created_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档审核汇总表';
