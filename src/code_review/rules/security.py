from __future__ import annotations

import re

from .base import Rule
from ..models import FileDiff, Issue


# Patterns for hardcoded secrets — avoids false positives on variable names
_SECRET_RE = re.compile(
    r'(?i)(password|passwd|secret|api[_-]?key|token|auth[_-]?key|private[_-]?key)\s*=\s*["\'][^"\']{4,}["\']'
)

_SQL_CONCAT_RE = re.compile(
    r'(?i)(select|insert|update|delete|drop|create)\b.+(\+\s*\w|\w\s*\+)',
)

_EVAL_RE = re.compile(r'\beval\s*\(')
_EXEC_RE = re.compile(r'\bexec\s*\(')

_SHELL_TRUE_RE = re.compile(r'shell\s*=\s*True')

_WEAK_HASH_RE = re.compile(r'(?i)\b(md5|sha1)\s*\(')
_WEAK_HASH_IMPORT_RE = re.compile(r'(?i)(hashlib\.md5|hashlib\.sha1|MessageDigest\.getInstance\s*\(\s*["\']MD5|["\']SHA-1)')


class HardcodedSecretRule(Rule):
    id = "SEC001"
    description = "Hardcoded credential or secret detected"
    severity = "critical"

    def check(self, file_diff: FileDiff) -> list[Issue]:
        issues = []
        for lineno, content in file_diff.added_lines_flat():
            if _SECRET_RE.search(content):
                issues.append(self._make_issue(
                    file_diff.filename, lineno,
                    "Hardcoded credential detected — use environment variables or a secrets manager.",
                    "Replace with os.environ['SECRET_NAME'] or a secrets vault reference.",
                ))
        return issues


class SqlInjectionRule(Rule):
    id = "SEC002"
    description = "SQL string concatenation — potential injection"
    severity = "high"

    def check(self, file_diff: FileDiff) -> list[Issue]:
        issues = []
        for lineno, content in file_diff.added_lines_flat():
            if _SQL_CONCAT_RE.search(content):
                issues.append(self._make_issue(
                    file_diff.filename, lineno,
                    "SQL query built by string concatenation — vulnerable to SQL injection.",
                    "Use parameterized queries or an ORM.",
                ))
        return issues


class EvalExecRule(Rule):
    id = "SEC003"
    description = "Use of eval() or exec()"
    severity = "high"

    def check(self, file_diff: FileDiff) -> list[Issue]:
        issues = []
        for lineno, content in file_diff.added_lines_flat():
            if _EVAL_RE.search(content) or _EXEC_RE.search(content):
                issues.append(self._make_issue(
                    file_diff.filename, lineno,
                    "eval()/exec() executes arbitrary code — dangerous with any user-controlled input.",
                    "Replace with a safe alternative (ast.literal_eval, explicit logic, etc.).",
                ))
        return issues


class SubprocessShellRule(Rule):
    id = "SEC004"
    description = "subprocess called with shell=True"
    severity = "high"

    def check(self, file_diff: FileDiff) -> list[Issue]:
        issues = []
        for lineno, content in file_diff.added_lines_flat():
            if _SHELL_TRUE_RE.search(content):
                issues.append(self._make_issue(
                    file_diff.filename, lineno,
                    "subprocess with shell=True enables shell injection if any argument is user-controlled.",
                    "Pass a list of arguments and set shell=False.",
                ))
        return issues


class WeakHashRule(Rule):
    id = "SEC005"
    description = "MD5 or SHA-1 used for security-sensitive hashing"
    severity = "medium"

    def check(self, file_diff: FileDiff) -> list[Issue]:
        issues = []
        for lineno, content in file_diff.added_lines_flat():
            if _WEAK_HASH_RE.search(content) or _WEAK_HASH_IMPORT_RE.search(content):
                issues.append(self._make_issue(
                    file_diff.filename, lineno,
                    "MD5/SHA-1 are cryptographically broken — do not use for passwords or integrity checks.",
                    "Use SHA-256 or bcrypt/argon2 for passwords.",
                ))
        return issues


SECURITY_RULES: list[Rule] = [
    HardcodedSecretRule(),
    SqlInjectionRule(),
    EvalExecRule(),
    SubprocessShellRule(),
    WeakHashRule(),
]
