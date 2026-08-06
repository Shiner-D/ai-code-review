from __future__ import annotations

from .models import FileDiff, Issue
from .rules import ALL_RULES, Rule


def run_rules(files: list[FileDiff], rules: list[Rule] | None = None) -> list[Issue]:
    """Run all applicable rules against each file diff.

    Returns issues sorted by severity (critical first).
    """
    if rules is None:
        rules = ALL_RULES

    issues: list[Issue] = []
    for file_diff in files:
        for rule in rules:
            if rule.applies_to(file_diff.language):
                issues.extend(rule.check(file_diff))

    issues.sort()  # uses Issue.__lt__ (severity_rank)
    return issues
