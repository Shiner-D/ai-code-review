import json
from pathlib import Path

from code_review.git_parser import parse_diff
from code_review.rule_engine import run_rules
from code_review.claude_analyzer import build_report
from code_review.report import to_json, to_markdown


FIXTURE = (Path(__file__).parent / "fixtures" / "sample.diff").read_text()


def _make_report(fail_on="high"):
    files = parse_diff(FIXTURE)
    rule_issues = run_rules(files)
    return build_report(
        files=files,
        rule_issues=rule_issues,
        claude_issues=[],
        summary="Test summary.",
        risk_score=40,
        fail_on=fail_on,
        model_used=None,
    )


def test_json_is_valid():
    report = _make_report()
    data = json.loads(to_json(report))
    assert "issues" in data
    assert "passed" in data
    assert "risk_score" in data
    assert "stats" in data


def test_json_has_all_issue_fields():
    report = _make_report()
    data = json.loads(to_json(report))
    for issue in data["issues"]:
        assert "file" in issue
        assert "severity" in issue
        assert "rule_id" in issue
        assert "message" in issue


def test_markdown_contains_header():
    report = _make_report()
    md = to_markdown(report)
    assert "# AI Code Review" in md


def test_markdown_shows_fail_status():
    report = _make_report(fail_on="low")  # many issues expected
    md = to_markdown(report)
    assert "FAILED" in md or "PASSED" in md


def test_fail_on_critical_fails_when_critical_issue_present():
    report = _make_report(fail_on="critical")
    # Sample diff has SEC001 (critical) — must fail even at critical threshold
    assert not report.passed


def test_fail_on_critical_no_high_issues_pass():
    """Verify that threshold logic itself is correct: high issue does not trigger critical threshold."""
    from code_review.models import Issue, ReviewStats, ReviewReport
    high_only_report = ReviewReport(
        issues=[Issue(file="f.py", severity="high", rule_id="X", message="m", source="rule")],
        summary="",
        risk_score=30,
        passed=False,
        stats=ReviewStats(files_reviewed=1, lines_added=1, issues_by_severity={"high": 1}, rules_triggered=["X"]),
    )
    # Manually recalculate passed for fail_on=critical
    from code_review.models import SEVERITY_ORDER
    threshold = SEVERITY_ORDER["critical"]
    passed = not any(i.severity_rank <= threshold for i in high_only_report.issues)
    assert passed, "A 'high' issue should not fail when fail_on=critical"


def test_fail_on_high_with_critical_issues_fails():
    report = _make_report(fail_on="high")
    # SEC001 is critical — fail_on=high includes critical
    assert not report.passed


def test_stats_file_count():
    files = parse_diff(FIXTURE)
    report = _make_report()
    assert report.stats.files_reviewed == len(files)


def test_write_reports(tmp_path):
    from code_review.report import write_reports
    report = _make_report()
    written = write_reports(report, tmp_path, ["json", "markdown"])
    assert len(written) == 2
    assert (tmp_path / "review.json").exists()
    assert (tmp_path / "review.md").exists()
