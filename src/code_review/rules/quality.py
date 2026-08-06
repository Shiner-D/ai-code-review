from __future__ import annotations

import re

from .base import Rule
from ..models import FileDiff, Issue


_PRINT_PY_RE = re.compile(r'^\s*print\s*\(')
_CONSOLE_LOG_RE = re.compile(r'\bconsole\.(log|debug|warn|error)\s*\(')
_SYSTEM_OUT_RE = re.compile(r'System\.out\.print')

_TODO_RE = re.compile(r'(?i)\b(TODO|FIXME|HACK|XXX)\b')

_BARE_EXCEPT_RE = re.compile(r'^\s*except\s*:\s*$')

# Magic number: standalone integer ≥ 100 not in an obvious constant definition
_MAGIC_NUM_RE = re.compile(r'(?<![A-Z_=\[\(,])\b([1-9]\d{2,})\b(?!\s*[=:])')


class DebugPrintRule(Rule):
    id = "QUA001"
    description = "Debug print/log statement left in production code"
    severity = "low"

    def check(self, file_diff: FileDiff) -> list[Issue]:
        # Skip test files
        fname = file_diff.filename.lower()
        if "test" in fname or "spec" in fname or "__debug" in fname:
            return []

        issues = []
        for lineno, content in file_diff.added_lines_flat():
            if (
                _PRINT_PY_RE.search(content)
                or _CONSOLE_LOG_RE.search(content)
                or _SYSTEM_OUT_RE.search(content)
            ):
                issues.append(self._make_issue(
                    file_diff.filename, lineno,
                    "Debug print/log statement in production code.",
                    "Remove or replace with proper logging framework.",
                ))
        return issues


class TodoInCodeRule(Rule):
    id = "QUA002"
    description = "TODO/FIXME/HACK comment left in PR"
    severity = "low"

    def check(self, file_diff: FileDiff) -> list[Issue]:
        issues = []
        for lineno, content in file_diff.added_lines_flat():
            m = _TODO_RE.search(content)
            if m:
                issues.append(self._make_issue(
                    file_diff.filename, lineno,
                    f"{m.group(0)} comment indicates unfinished work in this PR.",
                    "Resolve the issue before merging, or create a tracked ticket and remove the comment.",
                ))
        return issues


class BareExceptRule(Rule):
    id = "QUA003"
    description = "Bare except clause catches all exceptions including SystemExit"
    severity = "medium"
    languages = {"python"}

    def check(self, file_diff: FileDiff) -> list[Issue]:
        issues = []
        for lineno, content in file_diff.added_lines_flat():
            if _BARE_EXCEPT_RE.match(content):
                issues.append(self._make_issue(
                    file_diff.filename, lineno,
                    "Bare `except:` catches SystemExit and KeyboardInterrupt — almost always a bug.",
                    "Catch specific exceptions: `except (ValueError, TypeError):`.",
                ))
        return issues


class MagicNumberRule(Rule):
    id = "QUA004"
    description = "Magic number — unexplained numeric literal"
    severity = "info"

    def check(self, file_diff: FileDiff) -> list[Issue]:
        issues = []
        for lineno, content in file_diff.added_lines_flat():
            stripped = content.strip()
            # Skip comments and constant definitions
            if stripped.startswith(("#", "//", "*", "/*")) or re.match(r'^[A-Z_]+ =', stripped):
                continue
            for m in _MAGIC_NUM_RE.finditer(content):
                issues.append(self._make_issue(
                    file_diff.filename, lineno,
                    f"Magic number {m.group(1)} — consider extracting to a named constant.",
                ))
                break  # one issue per line is enough
        return issues


QUALITY_RULES: list[Rule] = [
    DebugPrintRule(),
    TodoInCodeRule(),
    BareExceptRule(),
    MagicNumberRule(),
]
