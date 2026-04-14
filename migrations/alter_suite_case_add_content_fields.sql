-- =====================================================
-- 为 crosstest_test_suite_case 表新增用例内容字段
-- 说明：
--   - inherit_from_case=true 时，自动从 test_case 复制 preconditions/test_steps/test_data 入库
--   - inherit_from_case=false 时，用户传入什么就存什么
--   - 执行时 fallback 规则：
--       suite_case 自己的字段 > test_case 表的字段
-- =====================================================

ALTER TABLE `crosstest_test_suite_case`
    ADD COLUMN `preconditions` TEXT COMMENT '前置条件(可独立覆盖)' AFTER `assertions`,
    ADD COLUMN `test_steps` JSON COMMENT '测试步骤(可独立覆盖)' AFTER `preconditions`,
    ADD COLUMN `test_data` JSON COMMENT '测试数据(可独立覆盖)' AFTER `test_steps`;
