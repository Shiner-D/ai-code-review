from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import FileDiff, Issue, Language, Severity


class Rule(ABC):
    id: str
    description: str
    severity: Severity
    languages: set[Language] | None = None  # None = all languages

    def applies_to(self, language: Language) -> bool:
        return self.languages is None or language in self.languages

    @abstractmethod
    def check(self, file_diff: FileDiff) -> list[Issue]:
        """Return list of issues found in the file diff."""
        ...

    def _make_issue(self, file: str, line: int | None, message: str, suggestion: str | None = None) -> Issue:
        return Issue(
            file=file,
            line=line,
            severity=self.severity,
            rule_id=self.id,
            message=message,
            source="rule",
            suggestion=suggestion,
        )
