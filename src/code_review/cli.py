from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich import box

from .git_parser import parse_diff
from .rule_engine import run_rules
from .claude_analyzer import analyze_with_claude, build_report
from .report import write_reports, to_markdown
from .models import SEVERITY_ORDER

console = Console()
err_console = Console(stderr=True)

_DEFAULT_MODEL = "claude-sonnet-4-6"
_VALID_SEVERITIES = list(SEVERITY_ORDER.keys())
_VALID_FORMATS = ["json", "markdown"]


def _print_summary(report) -> None:
    status = "[bold green]PASSED[/]" if report.passed else "[bold red]FAILED[/]"
    console.print(f"\n[bold]AI Code Review[/] — {status}")
    console.print(f"Risk score: [bold]{report.risk_score}[/]/100  |  Files: {report.stats.files_reviewed}  |  Lines added: {report.stats.lines_added}")
    console.print(f"\n{report.summary}\n")

    if not report.issues:
        console.print("[green]No issues found.[/]")
        return

    table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold")
    table.add_column("Severity", width=10)
    table.add_column("Rule", width=10)
    table.add_column("File", width=40)
    table.add_column("Line", width=6)
    table.add_column("Message")

    sev_color = {"critical": "red", "high": "orange3", "medium": "yellow", "low": "cyan", "info": "dim"}

    for issue in report.issues:
        color = sev_color.get(issue.severity, "white")
        table.add_row(
            f"[{color}]{issue.severity}[/{color}]",
            issue.rule_id,
            issue.file[-38:] if len(issue.file) > 38 else issue.file,
            str(issue.line) if issue.line else "-",
            issue.message[:80],
        )

    console.print(table)


@click.command()
@click.option("--diff-file", "-f", type=click.Path(exists=True, path_type=Path), default=None,
              help="Read diff from file instead of stdin.")
@click.option("--output-dir", "-o", type=click.Path(path_type=Path), default=None,
              help="Directory to write report files. Skipped if not set.")
@click.option("--format", "formats", default="json,markdown",
              help="Comma-separated output formats: json,markdown. Default: json,markdown")
@click.option("--fail-on", default="high", show_default=True,
              type=click.Choice(_VALID_SEVERITIES),
              help="Exit with code 1 when issues at this severity or above are found.")
@click.option("--model", default=_DEFAULT_MODEL, show_default=True,
              help="AI model for analysis. claude-* uses Anthropic; others use OpenAI-compatible API.")
@click.option("--base-url", default=None,
              help="Custom API base URL for OpenAI-compatible providers (e.g. https://api.deepseek.com). "
                   "Also readable from AI_REVIEW_BASE_URL env var.")
@click.option("--rules-only", is_flag=True, default=False,
              help="Skip AI analysis — run static rules only.")
@click.option("--max-issues", default=100, show_default=True,
              help="Maximum number of issues to include in the report.")
def main(
    diff_file: Path | None,
    output_dir: Path | None,
    formats: str,
    fail_on: str,
    model: str,
    base_url: str | None,
    rules_only: bool,
    max_issues: int,
) -> None:
    """Review AI-generated code changes from a git diff.

    Reads a unified diff from stdin or --diff-file, runs static rules and
    optional AI analysis, writes reports, and exits with code 1 if issues
    at or above --fail-on severity are found.

    \b
    Supported providers (auto-detected from model name):
      Claude:   --model claude-sonnet-4-6   ANTHROPIC_API_KEY=sk-ant-...
      DeepSeek: --model deepseek-chat       AI_REVIEW_API_KEY=sk-...
                                            AI_REVIEW_BASE_URL=https://api.deepseek.com
      OpenAI:   --model gpt-4o              AI_REVIEW_API_KEY=sk-...
      Ollama:   --model llama3.2            AI_REVIEW_BASE_URL=http://localhost:11434/v1

    \b
    Examples:
      git diff origin/main...HEAD | ai-code-review
      git diff origin/main...HEAD | ai-code-review --model deepseek-chat
      ai-code-review --diff-file pr.diff --output-dir ./reports --fail-on medium
      git diff main...feature | ai-code-review --rules-only
    """
    # Read diff input
    if diff_file:
        diff_text = diff_file.read_text(encoding="utf-8", errors="replace")
    elif not sys.stdin.isatty():
        diff_text = sys.stdin.read()
    else:
        err_console.print("[yellow]No diff input. Pipe git diff output or use --diff-file.[/]")
        err_console.print("Example: git diff origin/main...HEAD | ai-code-review")
        sys.exit(2)

    if not diff_text.strip():
        console.print("[green]Empty diff — nothing to review.[/]")
        sys.exit(0)

    # Parse
    with console.status("Parsing diff..."):
        files = parse_diff(diff_text)

    if not files:
        console.print("[green]No reviewable changes found in diff.[/]")
        sys.exit(0)

    console.print(f"Reviewing [bold]{len(files)}[/] file(s), "
                  f"[bold]{sum(f.added_lines_total for f in files)}[/] added lines...")

    # Rule engine
    with console.status("Running static rules..."):
        rule_issues = run_rules(files)

    console.print(f"  Rules: [bold]{len(rule_issues)}[/] issue(s) found")

    # Claude analysis
    claude_issues: list = []
    summary = ""
    risk_score = 0
    model_used: str | None = None

    if not rules_only:
        import os
        from .claude_analyzer import _resolve_api_key, _resolve_base_url, _is_claude_model
        resolved_key = _resolve_api_key(model)
        resolved_url = _resolve_base_url(model, base_url)
        is_local = resolved_url and "localhost" in resolved_url

        if not resolved_key and not is_local:
            if _is_claude_model(model):
                err_console.print("[yellow]Warning: ANTHROPIC_API_KEY 未设置 — 仅运行静态规则。[/]")
            else:
                err_console.print("[yellow]Warning: AI_REVIEW_API_KEY 未设置 — 仅运行静态规则。[/]")
                err_console.print(f"[dim]提示：export AI_REVIEW_API_KEY=your-key  AI_REVIEW_BASE_URL=https://api.deepseek.com[/]")
        else:
            with console.status(f"Analyzing with {model}..."):
                claude_issues, summary, risk_score = analyze_with_claude(
                    files, rule_issues, model=model, base_url=base_url
                )
            model_used = model
            console.print(f"  AI ({model}): [bold]{len(claude_issues)}[/] additional issue(s) found")

    # Build report
    report = build_report(
        files=files,
        rule_issues=rule_issues[:max_issues],
        claude_issues=claude_issues[:max(0, max_issues - len(rule_issues))],
        summary=summary,
        risk_score=risk_score,
        fail_on=fail_on,
        model_used=model_used,
    )

    _print_summary(report)

    # Write files
    if output_dir:
        fmt_list = [f.strip() for f in formats.split(",") if f.strip() in _VALID_FORMATS]
        written = write_reports(report, output_dir, fmt_list)
        for path in written:
            console.print(f"  Wrote [bold]{path}[/]")

    sys.exit(0 if report.passed else 1)
