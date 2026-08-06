from __future__ import annotations

import re
from pathlib import Path

from .models import FileDiff, Hunk, Language

_LANG_MAP: dict[str, Language] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
}

_BINARY_RE = re.compile(r"^Binary files .+ differ$")
_DIFF_HEADER_RE = re.compile(r"^diff --git a/.+ b/(.+)$")
_NEW_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$")
_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def _detect_language(filename: str) -> Language:
    ext = Path(filename).suffix.lower()
    return _LANG_MAP.get(ext, "generic")


def parse_diff(diff_text: str) -> list[FileDiff]:
    """Parse unified git diff output into FileDiff objects.

    Only added lines are captured for review. Binary files and deleted files
    are skipped. Each FileDiff contains hunks with (line_number, content).
    """
    files: list[FileDiff] = []
    current_file: FileDiff | None = None
    current_hunk: Hunk | None = None
    is_binary = False
    new_line_counter = 0

    for raw_line in diff_text.splitlines():
        # New file in diff
        m = _DIFF_HEADER_RE.match(raw_line)
        if m:
            if current_file is not None and current_file.added_lines_total > 0:
                files.append(current_file)
            current_file = None
            current_hunk = None
            is_binary = False
            continue

        if _BINARY_RE.match(raw_line):
            is_binary = True
            continue

        if is_binary:
            continue

        # +++ b/filename sets the actual filename (handles renames)
        m = _NEW_FILE_RE.match(raw_line)
        if m:
            filename = m.group(1)
            current_file = FileDiff(filename=filename, language=_detect_language(filename))
            current_hunk = None
            continue

        if current_file is None:
            continue

        # Hunk header
        m = _HUNK_RE.match(raw_line)
        if m:
            current_hunk = Hunk(old_start=int(m.group(1)), new_start=int(m.group(2)))
            new_line_counter = current_hunk.new_start
            current_file.hunks.append(current_hunk)
            continue

        if current_hunk is None:
            continue

        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            content = raw_line[1:]  # strip the leading '+'
            current_hunk.added_lines.append((new_line_counter, content))
            new_line_counter += 1
        elif raw_line.startswith("-") and not raw_line.startswith("---"):
            content = raw_line[1:]
            current_hunk.removed_lines.append((new_line_counter, content))
            # removed lines don't advance new_line_counter
        elif not raw_line.startswith("\\"):
            # context line
            new_line_counter += 1

    if current_file is not None and current_file.added_lines_total > 0:
        files.append(current_file)

    return files
