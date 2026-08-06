from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

Severity = Literal["critical", "high", "medium", "low", "info"]
Source = Literal["rule", "claude"]
Language = Literal["python", "typescript", "javascript", "java", "kotlin", "generic"]


@dataclass
class Hunk:
    old_start: int
    new_start: int
    added_lines: list[tuple[int, str]] = field(default_factory=list)
    removed_lines: list[tuple[int, str]] = field(default_factory=list)


@dataclass
class FileDiff:
    filename: str
    language: Language
    hunks: list[Hunk] = field(default_factory=list)

    @property
    def added_lines_total(self) -> int:
        return sum(len(h.added_lines) for h in self.hunks)

    def added_lines_flat(self) -> list[tuple[int, str]]:
        """All added lines as (line_number, content) across all hunks."""
        result = []
        for hunk in self.hunks:
            result.extend(hunk.added_lines)
        return result

    def diff_text(self) -> str:
        """Reconstructed diff text for Claude consumption."""
        lines = [f"--- {self.filename}", f"+++ {self.filename}"]
        for hunk in self.hunks:
            lines.append(f"@@ -{hunk.old_start} +{hunk.new_start} @@")
            for lineno, content in hunk.removed_lines:
                lines.append(f"-{content}")
            for lineno, content in hunk.added_lines:
                lines.append(f"+{content}")
        return "\n".join(lines)


@dataclass
class Issue:
    file: str
    severity: Severity
    rule_id: str
    message: str
    source: Source
    line: int | None = None
    suggestion: str | None = None

    @property
    def severity_rank(self) -> int:
        return SEVERITY_ORDER[self.severity]

    def __lt__(self, other: Issue) -> bool:
        return self.severity_rank < other.severity_rank


@dataclass
class ReviewStats:
    files_reviewed: int
    lines_added: int
    issues_by_severity: dict[str, int]
    rules_triggered: list[str]


@dataclass
class ReviewReport:
    issues: list[Issue]
    summary: str
    risk_score: int
    passed: bool
    stats: ReviewStats
    model_used: str | None = None

    def issues_at_or_above(self, severity: Severity) -> list[Issue]:
        threshold = SEVERITY_ORDER[severity]
        return [i for i in self.issues if i.severity_rank <= threshold]
