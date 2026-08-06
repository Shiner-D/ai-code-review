from __future__ import annotations

import json
import os
import re
from typing import Any

from .models import FileDiff, Issue, ReviewReport, ReviewStats, SEVERITY_ORDER

_DEFAULT_MODEL = "claude-sonnet-4-6"
_MAX_DIFF_CHARS = 30_000

_SYSTEM_PROMPT = """You are a senior software engineer specializing in reviewing AI-generated code.
Your role is to find issues that static linters miss: logic errors, security vulnerabilities, missing edge cases, incorrect API usage, and faulty assumptions that AI models commonly make.

Focus on:
1. Logic errors — wrong conditions, off-by-one errors, incorrect algorithm
2. Missing error handling — network failures, empty results, race conditions
3. Security vulnerabilities — not caught by regex rules (auth bypass, SSRF, broken access control)
4. Hallucinated or incorrect API usage — calling methods with wrong signatures or non-existent APIs
5. Missing edge cases — null inputs, empty collections, concurrent modification, integer overflow
6. Subtle bugs — code that "looks right" but has a hidden flaw

Do NOT report:
- Style issues (handled by linters)
- Formatting problems
- Missing docstrings
- Issues already reported by the rule engine (listed in the prompt)

Output ONLY valid JSON with this exact structure:
{
  "issues": [
    {
      "file": "path/to/file.py",
      "line": 42,
      "severity": "critical|high|medium|low|info",
      "message": "Clear description of the problem",
      "suggestion": "Concrete fix suggestion"
    }
  ],
  "summary": "2-3 sentence overall assessment",
  "risk_score": 0
}

risk_score is 0-100: 0 = no issues, 100 = do not merge. Use 0-20 for minor, 21-50 for moderate, 51-80 for significant, 81-100 for critical issues."""


def _is_claude_model(model: str) -> bool:
    return model.startswith("claude-")


def _resolve_api_key(model: str) -> str | None:
    """查找合适的 API Key，优先级：AI_REVIEW_API_KEY > 厂商专用 Key。"""
    generic = os.environ.get("AI_REVIEW_API_KEY")
    if generic:
        return generic
    if _is_claude_model(model):
        return os.environ.get("ANTHROPIC_API_KEY")
    return os.environ.get("OPENAI_API_KEY")


def _resolve_base_url(model: str, cli_base_url: str | None) -> str | None:
    """返回 API base URL，CLI 参数 > 环境变量 > 默认值。"""
    if cli_base_url:
        return cli_base_url
    return os.environ.get("AI_REVIEW_BASE_URL")


def _build_user_prompt(files: list[FileDiff], existing_issues: list[Issue]) -> str:
    parts: list[str] = []

    if existing_issues:
        parts.append("## Issues already found by the rule engine (do not repeat these):\n")
        for issue in existing_issues[:20]:
            parts.append(f"- [{issue.rule_id}] {issue.file}:{issue.line} — {issue.message}")
        parts.append("")

    parts.append("## Code changes to review:\n")
    total_chars = 0
    for fd in files:
        diff_text = fd.diff_text()
        if total_chars + len(diff_text) > _MAX_DIFF_CHARS:
            parts.append(f"\n[Truncated: {len(files)} files total, showing first {total_chars} chars]")
            break
        parts.append(f"### {fd.filename} ({fd.language}, +{fd.added_lines_total} lines)\n")
        parts.append("```")
        parts.append(diff_text)
        parts.append("```\n")
        total_chars += len(diff_text)

    return "\n".join(parts)


def _parse_response(raw: str, files: list[FileDiff]) -> tuple[list[Issue], str, int]:
    valid_files = {fd.filename for fd in files}
    try:
        data: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if m:
            data = json.loads(m.group(1))
        else:
            return [], "AI response could not be parsed as JSON.", 50

    issues: list[Issue] = []
    for item in data.get("issues", []):
        severity = item.get("severity", "medium")
        if severity not in SEVERITY_ORDER:
            severity = "medium"
        file_path = item.get("file", "unknown")
        if file_path not in valid_files:
            matches = [f for f in valid_files if f.endswith(file_path) or file_path.endswith(f)]
            file_path = matches[0] if matches else file_path
        issues.append(Issue(
            file=file_path,
            line=item.get("line"),
            severity=severity,
            rule_id="AI",
            message=item.get("message", ""),
            source="claude",
            suggestion=item.get("suggestion"),
        ))

    summary = data.get("summary", "")
    risk_score = max(0, min(100, int(data.get("risk_score", 0))))
    return issues, summary, risk_score


def _call_anthropic(model: str, api_key: str, user_content: str) -> str:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic 包未安装，请执行：pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},  # prompt caching，节省约 80% token
            }
        ],
        messages=[{"role": "user", "content": user_content}],
    )
    return response.content[0].text


def _call_openai_compat(model: str, api_key: str, base_url: str | None, user_content: str) -> str:
    """调用任何 OpenAI 兼容接口（DeepSeek、OpenAI、Ollama 等）。"""
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai 包未安装，请执行：pip install openai")

    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url

    client = OpenAI(**kwargs)
    response = client.chat.completions.create(
        model=model,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    return response.choices[0].message.content or ""


def analyze_with_claude(
    files: list[FileDiff],
    existing_issues: list[Issue],
    model: str = _DEFAULT_MODEL,
    base_url: str | None = None,
) -> tuple[list[Issue], str, int]:
    """发送 diff 和规则结果给 AI 模型做语义审查。

    自动根据模型名称选择 provider：
    - claude-* → Anthropic SDK（支持 prompt caching）
    - 其他      → OpenAI 兼容接口（DeepSeek / OpenAI / Ollama 等）

    环境变量优先级：AI_REVIEW_API_KEY > ANTHROPIC_API_KEY / OPENAI_API_KEY
    """
    api_key = _resolve_api_key(model)
    resolved_base_url = _resolve_base_url(model, base_url)

    if not api_key and not (resolved_base_url and "localhost" in resolved_base_url):
        provider_hint = "ANTHROPIC_API_KEY" if _is_claude_model(model) else "AI_REVIEW_API_KEY 或 OPENAI_API_KEY"
        return [], f"AI 分析已跳过 — 未设置 {provider_hint}。", 0

    user_content = _build_user_prompt(files, existing_issues)

    try:
        if _is_claude_model(model):
            raw = _call_anthropic(model, api_key or "", user_content)
        else:
            raw = _call_openai_compat(model, api_key or "ollama", resolved_base_url, user_content)
    except Exception as e:
        return [], f"AI 分析出错：{e}", 0

    return _parse_response(raw, files)


def build_report(
    files: list[FileDiff],
    rule_issues: list[Issue],
    claude_issues: list[Issue],
    summary: str,
    risk_score: int,
    fail_on: str,
    model_used: str | None,
) -> ReviewReport:
    from .models import ReviewReport, ReviewStats, SEVERITY_ORDER

    all_issues = sorted(rule_issues + claude_issues)
    threshold_rank = SEVERITY_ORDER.get(fail_on, 1)
    passed = not any(i.severity_rank <= threshold_rank for i in all_issues)

    by_severity: dict[str, int] = {s: 0 for s in SEVERITY_ORDER}
    for issue in all_issues:
        by_severity[issue.severity] += 1

    triggered = sorted({i.rule_id for i in all_issues})

    stats = ReviewStats(
        files_reviewed=len(files),
        lines_added=sum(f.added_lines_total for f in files),
        issues_by_severity=by_severity,
        rules_triggered=triggered,
    )

    if not summary:
        if not all_issues:
            summary = "No issues found. The code looks good."
        else:
            top = all_issues[0]
            summary = f"Found {len(all_issues)} issue(s). Most severe: [{top.rule_id}] {top.message[:80]}."

    return ReviewReport(
        issues=all_issues,
        summary=summary,
        risk_score=risk_score,
        passed=passed,
        stats=stats,
        model_used=model_used,
    )
