-- 为 crosstest_review_record 表增加请求/响应 JSON 示例字段（在 request_params 后新增）
-- 执行前请确认表已存在；若字段已存在可忽略报错

ALTER TABLE `crosstest_review_record`
    ADD COLUMN `request_json_sample` TEXT NULL COMMENT '请求参数JSON示例' AFTER `request_params`;

ALTER TABLE `crosstest_review_record`
    ADD COLUMN `response_json_sample` TEXT NULL COMMENT '响应参数JSON示例' AFTER `request_json_sample`;
