import json
import os
import re
import uuid
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from common.llm.llm_client import LLMClient, MockLLMClient
from common.llm.prompt_manager import get_prompt_manager, get_api_case_prompt


def _default_prompt_template() -> str:
    """获取默认的prompt模板，优先从配置获取，失败时使用代码默认值"""
    # 优先从配置获取
    config_prompt = get_api_case_prompt()
    if config_prompt:
        return config_prompt
    
    # 回退到代码默认值
    return (
        "你是接口测试专家，基于接口信息生成测试用例JSON数组。\n"
        "输出格式：每个用例包含 id,title,priority,tags,request,expect,status_code,assertions\n"
        "request格式：{{method,path,headers,query,body}}\n\n"
        "覆盖要求：必填/选填、长度、格式、枚举、边界、空值、关联字段、业务场景。\n"
        "请务必输出合法JSON数组，使用标准双引号，字段之间用逗号分隔；不要输出多余文本、不要省略号；最好用```json ...```包裹。"
    )


def _extract_key_constraints(constraints: Optional[str], max_length: int = 500) -> str:
    """提取关键约束，只保留最重要的信息"""
    if not constraints or not isinstance(constraints, str):
        return ""

    # 如果约束较短，直接返回
    if len(constraints) <= max_length:
        return constraints

    # 提取关键信息：必填、枚举、格式、长度、范围等关键词
    key_patterns = [
        r"必填[：:].*?[。\n]",
        r"枚举[：:].*?[。\n]",
        r"格式[：:].*?[。\n]",
        r"长度[：:].*?[。\n]",
        r"范围[：:].*?[。\n]",
        r"类型[：:].*?[。\n]",
        r"约束[：:].*?[。\n]",
    ]

    key_parts = []
    for pattern in key_patterns:
        matches = re.findall(pattern, constraints, re.IGNORECASE)
        key_parts.extend(matches)

    if key_parts:
        result = " ".join(key_parts)
        if len(result) > max_length:
            result = result[:max_length] + "..."
        return result

    # 如果没有找到关键词，返回前max_length字符
    return constraints[:max_length] + "..."


def build_prompt(
    api_name: str,
    api_desc: str,
    http_method: str,
    path: str,
    params_example: Dict[str, Any],
    headers: Optional[Dict[str, Any]] = None,
    constraints: Optional[str] = None,
    max_cases: Optional[int] = None,
    extra_hint: Optional[str] = None,
    full_params_example: Optional[Dict[str, Any]] = None,
) -> str:
    prompt = _default_prompt_template()
    # 使用紧凑JSON，减少 token
    doc_block_focus = json.dumps(params_example, ensure_ascii=False, separators=(",", ":"), indent=None)
    doc_block_full = json.dumps(full_params_example or params_example, ensure_ascii=False, separators=(",", ":"), indent=None)
    header_block = json.dumps(headers or {}, ensure_ascii=False, separators=(",", ":"), indent=None)
    field_list = ", ".join(params_example.keys()) if isinstance(params_example, dict) else ""
    fields_hint = f"字段: {field_list}\n" if field_list else ""
    more_hint = extra_hint or ""

    # 只提取关键约束，限制长度
    constraints_trimmed = _extract_key_constraints(constraints, max_length=500)
    constraints_block = f"约束: {constraints_trimmed}\n" if constraints_trimmed else ""

    return (
        f"{prompt}\n\n"
        f"接口: {api_name}\n"
        f"描述: {api_desc}\n"
        f"方法: {http_method} {path}\n"
        f"{fields_hint}"
        f"Headers: {header_block}\n"
        f"全量请求基线（保持未被测字段一致）: {doc_block_full}\n"
        f"本批重点字段示例: {doc_block_focus}\n"
        f"{constraints_block}"
        f"{more_hint}"
        "除正在校验的字段外，其余字段保持与全量基线一致；不要删除或清空其他字段。"
    )


def _coerce_case_structure(raw_case: Dict[str, Any]) -> Dict[str, Any]:
    priority_value = raw_case.get("priority") or "P2"
    # 确保 priority 可 upper（可能是 int/None）
    try:
        priority_norm = str(priority_value).upper()
    except Exception:
        priority_norm = "P2"

    tags_value = raw_case.get("tags") or []
    # 确保 tags 为列表
    if isinstance(tags_value, (str, int, float, bool)):
        tags_value = [str(tags_value)]
    elif not isinstance(tags_value, list):
        tags_value = list(tags_value) if tags_value else []

    return {
        "id": str(raw_case.get("id") or uuid.uuid4())[:8],
        "title": raw_case.get("title") or "未命名用例",
        "priority": priority_norm,
        "tags": tags_value,
        "request": {
            "method": (raw_case.get("request") or {}).get("method"),
            "path": (raw_case.get("request") or {}).get("path"),
            "headers": (raw_case.get("request") or {}).get("headers") or {},
            "query": (raw_case.get("request") or {}).get("query") or {},
            "body": (raw_case.get("request") or {}).get("body") or {},
        },
        "expect": raw_case.get("expect") or "",
        "status_code": raw_case.get("status_code") or 200,
        "assertions": raw_case.get("assertions") or [],
    }


def _parse_model_output(model_output: str) -> List[Dict[str, Any]]:
    logger = logging.getLogger(__name__)

    def _trim_to_last_balanced(s: str) -> str:
        """截断到最后一个括号平衡的位置，减少截断导致的半包裹内容"""
        depth = 0
        in_string = False
        escape_next = False
        last_balanced = -1
        for i, ch in enumerate(s):
            if escape_next:
                escape_next = False
                continue
            if ch == "\\":
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
            if in_string:
                continue
            if ch == '[' or ch == '{':
                depth += 1
            elif ch == ']' or ch == '}':
                depth = max(depth - 1, 0)
                if depth == 0:
                    last_balanced = i
        if last_balanced != -1:
            trimmed = s[: last_balanced + 1]
            if len(trimmed) < len(s):
                logger.warning("【解析步骤】检测到可能截断，已截断到平衡位置: 原长=%d, 新长=%d", len(s), len(trimmed))
            return trimmed
        return s

    def _sanitize_long_strings(s: str, max_len: int = 2000) -> str:
        """
        将过长的字符串值截断，避免模型生成超长URL/文本导致截断或解析失败。
        同时补齐未闭合的字符串。
        """
        out = []
        in_string = False
        escape_next = False
        buf = []
        truncated = False
        for ch in s:
            if escape_next:
                if in_string:
                    buf.append(ch)
                else:
                    out.append(ch)
                escape_next = False
                continue
            if ch == "\\":
                if in_string:
                    buf.append(ch)
                else:
                    out.append(ch)
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                if in_string:
                    # closing quote
                    if len(buf) > max_len:
                        out.append('"')
                        out.append("".join(buf[:max_len]))
                        out.append("...(truncated)")
                        out.append('"')
                        truncated = True
                    else:
                        out.append('"')
                        out.append("".join(buf))
                        out.append('"')
                    buf = []
                    in_string = False
                else:
                    in_string = True
                    buf = []
                continue
            if in_string:
                buf.append(ch)
            else:
                out.append(ch)
        # 如果字符串未闭合，补一个引号
        if in_string:
            if len(buf) > max_len:
                out.append('"')
                out.append("".join(buf[:max_len]))
                out.append("...(truncated)")
                out.append('"')
                truncated = True
            else:
                out.append('"')
                out.append("".join(buf))
                out.append('"')
            out.append('"')  # 补齐结束引号
            truncated = True
        if truncated:
            logger.warning("【解析步骤】检测到超长或未闭合字符串，已截断/补齐后再解析")
        return "".join(out)

    def load_once(s: str) -> Any:
        return json.loads(s)

    def normalize_to_list(data: Any) -> List[Dict[str, Any]]:
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                return []
        if isinstance(data, dict):
            data = data.get("cases") or data.get("data") or []
        if not isinstance(data, list):
            return []
        return [c for c in data if isinstance(c, dict)]

    # 预处理：去除首尾空白
    stripped = model_output.strip()
    # 如果大概率截断，先尝试截到最后一个平衡位置
    stripped = _trim_to_last_balanced(stripped)
    # 截断超长字符串，减少因超长URL/文本导致的截断或未闭合
    stripped = _sanitize_long_strings(stripped)

    # 尝试去除可能的BOM或其他不可见字符
    if stripped.startswith('\ufeff'):
        stripped = stripped[1:]

    # 0) 如果输出是转义的JSON字符串（被双引号包裹），先解析一次
    if stripped.startswith('"') and stripped.endswith('"'):
        try:
            # 可能是被转义的JSON字符串，先解析一次
            unescaped = json.loads(stripped)
            if isinstance(unescaped, str):
                stripped = unescaped.strip()
                logger.info("【解析步骤】检测到转义的JSON字符串，已解转义，新长度=%d", len(stripped))
        except Exception as e:
            logger.debug("【解析步骤】尝试解转义失败: %s", str(e))

    # 1) 直接解析整个输出
    try:
        data = load_once(stripped)
        cases = normalize_to_list(data)
        if cases:
            logger.info("【解析成功】方法1-直接解析，用例数=%d", len(cases))
            return cases
    except json.JSONDecodeError as e:
        error_pos = getattr(e, 'pos', None)
        logger.warning("【解析失败】方法1-直接解析JSON错误: %s, 错误位置: %s", str(e), error_pos)
        # 尝试找到错误位置附近的文本
        if error_pos and error_pos < len(stripped):
            start = max(0, error_pos - 100)
            end = min(len(stripped), error_pos + 100)
            logger.warning("【解析失败】错误位置附近文本: %s", stripped[start:end])

        # 如果错误在末尾，可能是JSON被截断了
        if error_pos and error_pos > len(stripped) * 0.9:
            logger.warning("【解析失败】错误位置在末尾，可能是JSON被截断")
    except Exception as e:
        logger.warning("【解析失败】方法1-直接解析异常: %s", str(e), exc_info=True)

    # 2) 尝试从```json ...```中提取
    fenced = re.search(r"```(?:json)?\s*(\[[\s\S]*?\]|\{[\s\S]*?\})\s*```", model_output, re.IGNORECASE | re.DOTALL)
    if fenced:
        try:
            json_str = fenced.group(1).strip()
            data = load_once(json_str)
            cases = normalize_to_list(data)
            if cases:
                logger.info("【解析成功】方法2-代码块提取，用例数=%d", len(cases))
                return cases
        except Exception as e:
            logger.debug("【解析失败】方法2-代码块提取失败: %s", str(e))

    # 3) 尝试匹配首个完整的JSON数组（从第一个[到最后一个]）
    # 先找到第一个[的位置（在stripped中查找）
    first_bracket = stripped.find('[')
    if first_bracket >= 0:
        # 从后往前找最后一个]，但需要确保括号平衡
        # 计算括号平衡，找到最后一个匹配的]
        bracket_count = 0
        last_bracket = -1
        for i in range(len(stripped) - 1, first_bracket - 1, -1):
            if stripped[i] == ']':
                bracket_count += 1
                if bracket_count == 1:
                    last_bracket = i
                    break
            elif stripped[i] == '[':
                bracket_count -= 1
                if bracket_count < 0:
                    break

        if last_bracket > first_bracket:
            candidate = stripped[first_bracket:last_bracket + 1]
            # 尝试平衡括号，确保是完整的JSON
            for attempt in range(5):
                try:
                    data = load_once(candidate)
                    cases = normalize_to_list(data)
                    if cases:
                        logger.info("【解析成功】方法3-数组匹配，用例数=%d", len(cases))
                        return cases
                except json.JSONDecodeError as e:
                    # 如果JSON不完整，尝试去掉末尾的]再试
                    if candidate.endswith(']') and attempt < 4:
                        candidate = candidate[:-1]
                        continue
                    logger.debug("【解析失败】方法3-数组匹配失败(尝试%d): %s", attempt + 1, str(e))
                    break
                except Exception as e:
                    logger.debug("【解析失败】方法3-数组匹配异常: %s", str(e))
                    break

    # 4) 尝试逐行查找JSON数组
    lines = stripped.split('\n')
    json_lines = []
    in_json = False
    bracket_count = 0
    for line in lines:
        if '[' in line or in_json:
            json_lines.append(line)
            bracket_count += line.count('[') - line.count(']')
            in_json = True
            if bracket_count == 0 and json_lines:
                candidate = '\n'.join(json_lines)
                try:
                    data = load_once(candidate)
                    cases = normalize_to_list(data)
                    if cases:
                        logger.info("【解析成功】方法4-逐行匹配，用例数=%d", len(cases))
                        return cases
                except Exception:
                    pass
                json_lines = []
                in_json = False
                bracket_count = 0

    # 5) 如果JSON被截断，尝试修复（找到最后一个完整的用例对象）
    if stripped.startswith('['):
        # 使用状态机找到所有完整的用例对象
        # 用例对象是在数组中的，格式为 { ... }
        cases_positions = []  # 存储每个完整用例的 (start, end) 位置
        depth = 0  # 数组/对象深度
        in_string = False
        escape_next = False
        case_start = -1

        for i, char in enumerate(stripped):
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if not in_string:
                if char == '[':
                    depth += 1
                elif char == '{':
                    if depth == 1:  # 在数组中的对象，这是用例对象的开始
                        case_start = i
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 1 and case_start >= 0:  # 用例对象结束
                        cases_positions.append((case_start, i))
                        case_start = -1
                elif char == ']':
                    depth -= 1

        # 如果找到了完整的用例，尝试解析
        if cases_positions:
            logger.info("【解析步骤】找到 %d 个完整的用例对象", len(cases_positions))
            # 优先尝试解析所有找到的完整用例
            if len(cases_positions) > 0:
                first_start, _ = cases_positions[0]
                last_start, last_end = cases_positions[-1]
                # 尝试构建包含所有完整用例的JSON数组
                try:
                    # 从第一个用例开始到最后一个用例结束
                    candidate = '[' + stripped[first_start:last_end + 1] + ']'
                    data = load_once(candidate)
                    cases = normalize_to_list(data)
                    if cases:
                        logger.info("【解析成功】方法5-解析所有%d个完整用例，用例数=%d", len(cases_positions), len(cases))
                        return cases
                except Exception as e:
                    logger.debug("【解析失败】方法5-解析所有用例失败: %s", str(e))

            # 如果解析所有用例失败，尝试逐个解析并合并
            all_cases = []
            for idx, (start, end) in enumerate(cases_positions):
                try:
                    candidate = '[' + stripped[start:end + 1] + ']'
                    data = load_once(candidate)
                    cases = normalize_to_list(data)
                    if cases:
                        all_cases.extend(cases)
                        logger.debug("【解析步骤】成功解析用例 %d/%d", idx + 1, len(cases_positions))
                except Exception as e:
                    logger.debug("【解析失败】方法5-解析用例%d失败: %s", idx + 1, str(e))

            if all_cases:
                logger.info("【解析成功】方法5-逐个解析并合并，用例数=%d", len(all_cases))
                return all_cases

        # 最后尝试：简单补全括号
        bracket_open = stripped.count('[')
        bracket_close = stripped.count(']')
        missing_close = bracket_open - bracket_close
        if missing_close > 0:
            logger.warning("【解析步骤】检测到JSON可能被截断，缺失 %d 个 ]，尝试补全", missing_close)
            try:
                candidate = stripped + ']' * missing_close
                data = load_once(candidate)
                cases = normalize_to_list(data)
                if cases:
                    logger.info("【解析成功】方法5-简单补全括号，用例数=%d", len(cases))
                    return cases
            except Exception as e:
                logger.debug("【解析失败】方法5-简单补全括号失败: %s", str(e))

    # 5) 如果所有方法都失败，保存完整响应到文件以便调试
    logger.warning("【解析失败】所有方法都失败，原始输出长度=%d", len(model_output))
    logger.warning("【解析失败】前500字符: %s", model_output[:500])
    logger.warning("【解析失败】后500字符: %s", model_output[-500:] if len(model_output) > 500 else model_output)

    # 保存到调试文件
    try:
        debug_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "debug")
        os.makedirs(debug_dir, exist_ok=True)
        debug_file = os.path.join(debug_dir, f"parse_failed_{datetime.now().strftime('%Y%m%d%H%M%S')}.json")
        with open(debug_file, "w", encoding="utf-8") as f:
            json.dump({
                "raw_output": model_output,
                "length": len(model_output),
                "first_500": model_output[:500],
                "last_500": model_output[-500:] if len(model_output) > 500 else model_output,
            }, f, ensure_ascii=False, indent=2)
        logger.warning("【解析失败】完整响应已保存到: %s", debug_file)
    except Exception as e:
        logger.warning("【解析失败】保存调试文件失败: %s", e)

    return []


def generate_api_test_cases(
    api_name: str,
    api_desc: str,
    http_method: str,
    path: str,
    params_example: Dict[str, Any],
    headers: Optional[Dict[str, Any]] = None,
    constraints: Optional[str] = None,
    max_cases: Optional[int] = None,
    llm_client: Optional[LLMClient] = None,
    persist_dir: Optional[str] = None,
) -> Dict[str, Any]:
    logger = logging.getLogger(__name__)
    client = llm_client or MockLLMClient()
    def _run_once(params_subset: Dict[str, Any], extra_hint: Optional[str] = None) -> Tuple[str, List[Dict[str, Any]]]:
        prompt = build_prompt(
            api_name=api_name,
            api_desc=api_desc,
            http_method=http_method,
            path=path,
            params_example=params_subset,
            headers=headers,
            constraints=constraints,
            max_cases=max_cases,
            extra_hint=extra_hint,
            full_params_example=params_example,
        )

        logger.info("【生成用例】开始调用大模型")
        logger.info("【生成用例-完整prompt】\n%s", prompt)
        logger.info("【生成用例-constraints】\n%s", constraints or "无")
        logger.info("【生成用例-params_example】\n%s", json.dumps(params_subset, ensure_ascii=False, indent=2))

        # 记录prompt长度，便于排查截断问题
        prompt_length = len(prompt)
        prompt_tokens_estimate = prompt_length // 3  # 粗略估算：中文约3字符=1token
        logger.info("【生成用例】prompt长度=%d字符，估算token数≈%d", prompt_length, prompt_tokens_estimate)

        raw_output_local = client.complete(prompt, max_tokens=16384, timeout=600)
        logger.info("【生成用例】大模型返回原始输出长度=%d", len(raw_output_local))
        logger.info("【生成用例-完整响应】\n%s", raw_output_local)

        # 无论后续解析成功与否，先把“大模型原始输出”落到 debug 目录，便于排查
        try:
            debug_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "debug")
            os.makedirs(debug_dir, exist_ok=True)
            debug_file = os.path.join(debug_dir, f"llm_output_{datetime.now().strftime('%Y%m%d%H%M%S')}.json")
            with open(debug_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "raw_output": raw_output_local,
                        "length": len(raw_output_local),
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            logger.info("【调试】已将大模型输出保存到: %s", debug_file)
        except Exception as e:
            logger.warning("【调试】保存大模型输出失败: %s", e)

        parsed_cases_local = _parse_model_output(raw_output_local)
        # 过滤明显空的用例，减少“未命名/空内容”残留
        def _is_empty_case(c: Dict[str, Any]) -> bool:
            if not c:
                return True
            req = c.get("request") or {}
            return all(
                [
                    not c.get("title"),
                    not c.get("expect"),
                    not c.get("tags"),
                    not c.get("assertions"),
                    (req.get("method") is None or req.get("method") == ""),
                    (req.get("path") is None or req.get("path") == ""),
                    not (req.get("body") or {}),
                    not (req.get("query") or {}),
                    not (req.get("headers") or {}),
                ]
            )
        parsed_cases_local = [c for c in parsed_cases_local if not _is_empty_case(c)]
        logger.info("【生成用例】解析后用例数量=%d", len(parsed_cases_local))
        empty_cases_local = [c for c in parsed_cases_local if not c or all(v in (None, "", [], {}, ()) for v in c.values())]
        if parsed_cases_local:
            logger.info("【生成用例-解析后的用例示例】%s", json.dumps(parsed_cases_local[0] if parsed_cases_local else {}, ensure_ascii=False, indent=2))
        else:
            logger.warning("【生成用例】解析失败，原始输出前1000字符: %s", raw_output_local[:1000])
        if empty_cases_local:
            logger.warning("【生成用例】存在空用例数量=%d，可能解析不完整，原始输出前1000字符: %s", len(empty_cases_local), raw_output_local[:1000])

        return raw_output_local, parsed_cases_local

    def _extract_all_field_paths(obj: Any, prefix: str = "") -> List[str]:
        """递归提取所有字段路径（包括嵌套字段），用于日志记录"""
        paths = []
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{prefix}.{key}" if prefix else key
                paths.append(current_path)
                # 递归处理嵌套对象和数组
                if isinstance(value, (dict, list)):
                    paths.extend(_extract_all_field_paths(value, current_path))
        elif isinstance(obj, list) and obj:
            # 处理数组，取第一个元素作为示例
            paths.extend(_extract_all_field_paths(obj[0], prefix))
        return paths

    raw_outputs: List[str] = []
    all_cases: List[Dict[str, Any]] = []
    parse_fail_count = 0

    # 提取所有字段路径（包括嵌套字段），用于日志
    all_field_paths = _extract_all_field_paths(params_example)
    logger.info("【生成用例】提取到字段路径总数=%d", len(all_field_paths))
    if len(all_field_paths) <= 20:
        logger.info("【生成用例】字段路径列表: %s", all_field_paths)

    # 基于“字段路径”分批，优先覆盖更多路径；每批4个路径
    batch_size = 3  # 3字段/批，平衡截断风险与覆盖率
    batches: List[List[str]] = []
    if all_field_paths:
        for i in range(0, len(all_field_paths), batch_size):
            batches.append(all_field_paths[i : i + batch_size])
    else:
        # 没有结构化字段时，走单批
        batches = [[]]

    seen_titles: set = set()

    for paths in batches:
        if paths:
            # 计算本批涉及的顶层字段，并保留这些字段的完整结构
            top_keys = set(p.split(".")[0] for p in paths)
            params_subset = {k: params_example.get(k) for k in top_keys if isinstance(params_example, dict) and k in params_example}

            hint = (
                f"本批仅关注字段路径: {', '.join(paths)}。"
                " 只生成这些字段的用例，覆盖必填/长度/格式/枚举/边界/空值等，避免重复其他字段。"
            )
        else:
            params_subset = params_example
            hint = "生成高价值用例，覆盖所有字段场景。"

        raw_local, cases_local = _run_once(params_subset=params_subset, extra_hint=hint)
        raw_outputs.append(raw_local)
        if not cases_local:
            parse_fail_count += 1
        for c in cases_local:
            t = c.get("title")
            if t and t not in seen_titles:
                all_cases.append(c)
                seen_titles.add(t)


    # 去重与规范化
    normalized_cases = [_coerce_case_structure(c) for c in all_cases]
    logger.info("【生成用例】规范化后用例数量=%d", len(normalized_cases))

    review_id = str(uuid.uuid4())
    result = {
        "review_id": review_id,
        "cases": normalized_cases,
        "prompt": None,  # 多批次生成时不再返回单一prompt
        "raw_output": raw_outputs[0] if raw_outputs else "",
        "raw_outputs": raw_outputs,
        "parse_fail_count": parse_fail_count,
    }

    if persist_dir:
        os.makedirs(persist_dir, exist_ok=True)
        safe_name = re.sub(r"[^\w\-]+", "_", api_name).strip("_") or "api"
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        file_path = os.path.join(persist_dir, f"{safe_name}_{timestamp}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        result["persist_path"] = file_path

    return result

