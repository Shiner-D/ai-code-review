from pathlib import Path

from code_review.git_parser import parse_diff


FIXTURE = (Path(__file__).parent / "fixtures" / "sample.diff").read_text()


def test_parse_returns_two_files():
    files = parse_diff(FIXTURE)
    assert len(files) == 2


def test_python_file_detected():
    files = parse_diff(FIXTURE)
    py_file = next(f for f in files if f.filename.endswith(".py"))
    assert py_file.language == "python"


def test_typescript_file_detected():
    files = parse_diff(FIXTURE)
    ts_file = next(f for f in files if f.filename.endswith(".ts"))
    assert ts_file.language == "typescript"


def test_added_lines_captured():
    files = parse_diff(FIXTURE)
    py_file = next(f for f in files if f.filename.endswith(".py"))
    assert py_file.added_lines_total > 0


def test_line_numbers_non_zero():
    files = parse_diff(FIXTURE)
    for fd in files:
        for lineno, _ in fd.added_lines_flat():
            assert lineno > 0, "Line numbers should be 1-indexed"


def test_empty_diff():
    assert parse_diff("") == []


def test_binary_file_skipped():
    diff = (
        "diff --git a/image.png b/image.png\n"
        "Binary files a/image.png and b/image.png differ\n"
    )
    assert parse_diff(diff) == []


def test_diff_text_roundtrip():
    files = parse_diff(FIXTURE)
    for fd in files:
        text = fd.diff_text()
        assert fd.filename in text
