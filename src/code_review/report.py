from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .models import ReviewReport, SEVERITY_ORDER

_SEVERITY_EMOJI = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🔵",
    "info": "⚪",
}

_PASS_BADGE = "✅ PASSED"
_FAIL_BADGE = "❌ FAILED"


def to_json(report: ReviewReport, indent: int = 2) -> str:
    data = {
        "passed": report.passed,
        "risk_score": report.risk_score,
        "summary": report.summary,
        "model_used": report.model_used,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "files_reviewed": report.stats.files_reviewed,
            "lines_added": report.stats.lines_added,
            "issues_by_severity": report.stats.issues_by_severity,
            "rules_triggered": report.stats.rules_triggered,
        },
        "issues": [
            {
                "file": i.file,
                "line": i.line,
                "severity": i.severity,
                "rule_id": i.rule_id,
                "source": i.source,
                "message": i.message,
                "suggestion": i.suggestion,
            }
            for i in report.issues
        ],
    }
    return json.dumps(data, indent=indent, ensure_ascii=False)


def to_markdown(report: ReviewReport) -> str:
    badge = _PASS_BADGE if report.passed else _FAIL_BADGE
    lines: list[str] = [
        f"# AI Code Review {badge}",
        "",
        f"**Risk Score:** {report.risk_score}/100 &nbsp; "
        f"**Files:** {report.stats.files_reviewed} &nbsp; "
        f"**Lines added:** {report.stats.lines_added}",
        "",
        f"> {report.summary}",
        "",
    ]

    # Summary table
    lines += [
        "## Issues by Severity",
        "",
        "| Severity | Count |",
        "|----------|-------|",
    ]
    for sev in SEVERITY_ORDER:
        count = report.stats.issues_by_severity.get(sev, 0)
        if count:
            emoji = _SEVERITY_EMOJI[sev]
            lines.append(f"| {emoji} {sev.capitalize()} | {count} |")
    lines.append("")

    if not report.issues:
        lines.append("_No issues found._")
        return "\n".join(lines)

    lines.append("## Details")
    lines.append("")

    current_file = None
    for issue in report.issues:
        if issue.file != current_file:
            current_file = issue.file
            lines.append(f"### `{issue.file}`")
            lines.append("")

        loc = f"line {issue.line}" if issue.line else "file level"
        emoji = _SEVERITY_EMOJI[issue.severity]
        lines.append(f"**{emoji} [{issue.rule_id}]** `{loc}` — {issue.message}")
        if issue.suggestion:
            lines.append(f"> 💡 {issue.suggestion}")
        lines.append("")

    if report.model_used:
        lines += ["---", f"_Claude model: `{report.model_used}`_"]

    return "\n".join(lines)


def write_reports(report: ReviewReport, output_dir: Path, formats: list[str]) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if "json" in formats:
        p = output_dir / "review.json"
        p.write_text(to_json(report), encoding="utf-8")
        written.append(p)

    if "markdown" in formats:
        p = output_dir / "review.md"
        p.write_text(to_markdown(report), encoding="utf-8")
        written.append(p)

    return written
