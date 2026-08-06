from __future__ import annotations

import re

from .base import Rule
from ..models import FileDiff, Issue


# Stub function body — only 'pass' or 'return None' with no real implementation
_STUB_BODY_RE = re.compile(r'^\s*(pass|return\s+None)\s*$')
_DEF_RE = re.compile(r'^\s*def\s+\w+')

# Unreachable code after return/throw/raise
_RETURN_RE = re.compile(r'^\s*(return|raise|throw)\b')
_CODE_AFTER_RETURN_RE = re.compile(r'^\s+\S')

# Functions that genuinely can return null/None (single-record lookups)
# Deliberately excludes: findMany/findAll/findFirst (return array/throw), fetch() (throws)
_NULLABLE_CALL_RE = re.compile(
    r'(?i)\b(findOne|findById|findUnique|getOne|getById|getUserById'
    r'|findUser|getUser|findItem|getItem|findRecord|getRecord'
    r'|querySelector|getElementById|getElementBy\w+'
    r'|lookupUser|lookupById)\s*\('
)

# Null guard patterns — checked in a wider window (before and after the call)
_NULL_CHECK_RE = re.compile(
    r'(?i)(is\s+None|is\s+not\s+None|!= null|== null|\?\.'
    r'|if\s*\(?\s*\!?\s*\w|\.length\s*===?\s*0|throw\s+new\s+\w+Error'
    r'|notFound\(\)|return\s+null|return\s+response)'
)

# Lines that are definitions or infrastructure — never flag these
_DEFINITION_RE = re.compile(
    r'(?i)(^\s*(async\s+)?function\s+\w|^\s*(export\s+)?(const|let|var)\s+\w+\s*='
    r'|\=>\s*\{|useEffect\s*\(|\.then\s*\(|\.catch\s*\(|await\s+fetch\()'
)


class StubFunctionRule(Rule):
    id = "AIP001"
    description = "Function body appears to be an unimplemented stub"
    severity = "high"
    languages = {"python"}

    def check(self, file_diff: FileDiff) -> list[Issue]:
        issues = []
        lines = file_diff.added_lines_flat()
        i = 0
        while i < len(lines):
            lineno, content = lines[i]
            if _DEF_RE.match(content):
                # Look at the next non-empty added line
                j = i + 1
                while j < len(lines) and lines[j][1].strip() == "":
                    j += 1
                if j < len(lines) and _STUB_BODY_RE.match(lines[j][1]):
                    issues.append(self._make_issue(
                        file_diff.filename, lineno,
                        "Function appears to be an unimplemented stub (body is only `pass` or `return None`).",
                        "Implement the function body or mark it with NotImplementedError if intentionally abstract.",
                    ))
            i += 1
        return issues


class UnreachableCodeRule(Rule):
    id = "AIP002"
    description = "Unreachable code detected after return/raise/throw"
    severity = "medium"

    def check(self, file_diff: FileDiff) -> list[Issue]:
        issues = []
        lines = file_diff.added_lines_flat()
        for idx, (lineno, content) in enumerate(lines):
            if _RETURN_RE.match(content):
                # Check if the next line has code at the same or deeper indent
                if idx + 1 < len(lines):
                    next_lineno, next_content = lines[idx + 1]
                    if next_content.strip() and not next_content.strip().startswith(("#", "//")):
                        curr_indent = len(content) - len(content.lstrip())
                        next_indent = len(next_content) - len(next_content.lstrip())
                        if next_indent == curr_indent:
                            issues.append(self._make_issue(
                                file_diff.filename, next_lineno,
                                "Code after return/raise/throw is unreachable.",
                                "Remove the unreachable code or fix the control flow logic.",
                            ))
        return issues


class MissingNullCheckRule(Rule):
    id = "AIP003"
    description = "Single-record lookup result used without null check"
    severity = "medium"

    # Look 4 lines before and 4 lines after the call for a null guard
    _WINDOW = 4

    def check(self, file_diff: FileDiff) -> list[Issue]:
        issues = []
        lines = file_diff.added_lines_flat()
        for idx, (lineno, content) in enumerate(lines):
            if not _NULLABLE_CALL_RE.search(content):
                continue
            # Skip function definitions and infrastructure lines
            if _DEFINITION_RE.search(content):
                continue
            # Look in a window before and after for any null guard
            start = max(0, idx - self._WINDOW)
            end = min(len(lines), idx + self._WINDOW + 1)
            window_text = " ".join(c for _, c in lines[start:end])
            if not _NULL_CHECK_RE.search(window_text):
                issues.append(self._make_issue(
                    file_diff.filename, lineno,
                    "Single-record lookup result used without a visible null check nearby.",
                    "Add a null/None guard before accessing properties of the result.",
                ))
        return issues


class LargeFunctionRule(Rule):
    id = "AIP004"
    description = "Function is very large — AI often generates oversized single functions"
    severity = "info"
    languages = {"python", "typescript", "javascript", "java", "kotlin"}

    # Heuristic: count consecutive added lines in same hunk belonging to one function
    _THRESHOLD = 80

    def check(self, file_diff: FileDiff) -> list[Issue]:
        issues = []
        for hunk in file_diff.hunks:
            if len(hunk.added_lines) >= self._THRESHOLD:
                first_lineno = hunk.added_lines[0][0]
                issues.append(self._make_issue(
                    file_diff.filename, first_lineno,
                    f"Hunk adds {len(hunk.added_lines)} lines — AI-generated code tends to pack too much logic into one function.",
                    "Break this into smaller, focused functions with clear responsibilities.",
                ))
        return issues


AI_PATTERN_RULES: list[Rule] = [
    StubFunctionRule(),
    UnreachableCodeRule(),
    MissingNullCheckRule(),
    LargeFunctionRule(),
]
