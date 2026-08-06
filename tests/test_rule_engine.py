from pathlib import Path

from code_review.git_parser import parse_diff
from code_review.rule_engine import run_rules
from code_review.rules.security import SECURITY_RULES
from code_review.rules.quality import QUALITY_RULES
from code_review.rules.ai_patterns import AI_PATTERN_RULES


FIXTURE = (Path(__file__).parent / "fixtures" / "sample.diff").read_text()


def _rules_of_id(issues, rule_id):
    return [i for i in issues if i.rule_id == rule_id]


def test_sec001_hardcoded_secret():
    files = parse_diff(FIXTURE)
    issues = run_rules(files, SECURITY_RULES)
    assert _rules_of_id(issues, "SEC001"), "Should flag DB_PASSWORD hardcoded"


def test_sec002_sql_injection():
    files = parse_diff(FIXTURE)
    issues = run_rules(files, SECURITY_RULES)
    assert _rules_of_id(issues, "SEC002"), "Should flag SQL string concatenation"


def test_sec004_shell_true():
    files = parse_diff(FIXTURE)
    issues = run_rules(files, SECURITY_RULES)
    assert _rules_of_id(issues, "SEC004"), "Should flag subprocess shell=True"


def test_sec005_weak_hash():
    files = parse_diff(FIXTURE)
    issues = run_rules(files, SECURITY_RULES)
    assert _rules_of_id(issues, "SEC005"), "Should flag md5 hash"


def test_qua001_console_log():
    files = parse_diff(FIXTURE)
    issues = run_rules(files, QUALITY_RULES)
    assert _rules_of_id(issues, "QUA001"), "Should flag console.log in TS file"


def test_qua002_todo_comment():
    files = parse_diff(FIXTURE)
    issues = run_rules(files, QUALITY_RULES)
    assert _rules_of_id(issues, "QUA002"), "Should flag TODO comment"


def test_aip001_stub_function():
    files = parse_diff(FIXTURE)
    issues = run_rules(files, AI_PATTERN_RULES)
    assert _rules_of_id(issues, "AIP001"), "Should flag pass-body stub"


def test_severity_ordering():
    files = parse_diff(FIXTURE)
    issues = run_rules(files)
    severities = [i.severity_rank for i in issues]
    assert severities == sorted(severities), "Issues should be sorted by severity"


def test_all_issues_have_file():
    files = parse_diff(FIXTURE)
    issues = run_rules(files)
    for issue in issues:
        assert issue.file, "Every issue must have a file path"


def test_source_is_rule():
    files = parse_diff(FIXTURE)
    issues = run_rules(files)
    assert all(i.source == "rule" for i in issues)
