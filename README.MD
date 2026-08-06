# AI Code Review

A platform-agnostic CLI tool for validating AI-generated code in pull requests.

Combines a fast static rule engine with AI semantic analysis to catch what linters miss: logic errors, security vulnerabilities, missing edge cases, and AI hallucinations.

Supports multiple AI review models: Claude, DeepSeek, OpenAI, and local Ollama.

## How It Works

```
git diff  →  Rule Engine  →  AI Analysis  →  JSON + Markdown report  →  exit code
```

1. **Rule Engine** — fast regex/pattern checks, no API calls required
2. **AI Analysis** — deep semantic review; supports Claude / DeepSeek / OpenAI / Ollama
3. **Report** — JSON (machine-readable) + Markdown (paste as PR comment)
4. **Exit code** — `0` pass, `1` fail — controls CI/CD merge gates

## Quick Start

### Install

```bash
# Base install (includes Claude support)
pip install git+https://github.com/Shiner-D/ai-code-review.git

# Add DeepSeek / OpenAI / Ollama support
pip install "ai-code-review[openai]"
```

### Configure your API key

Set the environment variable for your chosen provider:

```bash
# Claude (default)
export ANTHROPIC_API_KEY=sk-ant-...

# DeepSeek
export AI_REVIEW_API_KEY=sk-...
export AI_REVIEW_BASE_URL=https://api.deepseek.com

# OpenAI
export AI_REVIEW_API_KEY=sk-...

# Ollama (local, no API key needed)
export AI_REVIEW_BASE_URL=http://localhost:11434/v1
```

### Run on a PR diff

```bash
# Switch to the project you want to review (not this tool's directory)
cd /path/to/your-project

# Review changes on the current branch vs main (default Claude model)
git diff origin/main...HEAD | ai-code-review --output-dir ./ai-review

# Use DeepSeek instead
git diff origin/main...HEAD | ai-code-review --model deepseek-chat --output-dir ./ai-review

# Use local Ollama
git diff origin/main...HEAD | ai-code-review --model llama3.2 --output-dir ./ai-review
```

## CLI Options

| Option | Default | Description |
| --- | --- | --- |
| `--diff-file FILE` | stdin | Read diff from file instead of stdin |
| `--output-dir DIR` | (none) | Directory to write `review.json` and `review.md` |
| `--format` | `json,markdown` | Output formats, comma-separated |
| `--fail-on SEVERITY` | `high` | Exit code 1 when issues at this level or above are found |
| `--model MODEL` | `claude-sonnet-4-6` | AI model name; provider is auto-detected |
| `--base-url URL` | env var | Custom API base URL; also readable from `AI_REVIEW_BASE_URL` |
| `--rules-only` | false | Skip AI analysis, run static rules only (no API key needed) |
| `--max-issues N` | 100 | Cap issues in report |

**Severity levels** (most to least severe): `critical` → `high` → `medium` → `low` → `info`

## Supported AI Providers

The provider is auto-detected from the model name — no extra configuration needed:

| Provider | Model example | API key variable | Base URL |
| --- | --- | --- | --- |
| Claude (default) | `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` | not required |
| DeepSeek | `deepseek-chat` | `AI_REVIEW_API_KEY` | `https://api.deepseek.com` |
| OpenAI | `gpt-4o` | `AI_REVIEW_API_KEY` | not required |
| Ollama (local) | `llama3.2` | not required | `http://localhost:11434/v1` |

> `AI_REVIEW_API_KEY` takes highest priority and overrides both `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`.
> Models starting with `claude-` use the Anthropic SDK (with prompt caching); all others use the OpenAI-compatible API.

## CI/CD Integration

See the [`examples/`](examples/) directory:

- [`github-actions.yml`](examples/github-actions.yml) — GitHub Actions with PR comment posting
- [`gitlab-ci.yml`](examples/gitlab-ci.yml) — GitLab CI with merge request trigger
- [`azure-pipelines.yml`](examples/azure-pipelines.yml) — Azure DevOps Pipelines

Set the relevant API key as an encrypted secret in your CI environment.

## What It Checks

### Static Rules (no API key needed)

| Rule | Severity | Description |
| --- | --- | --- |
| SEC001 | critical | Hardcoded credentials/secrets |
| SEC002 | high | SQL string concatenation (injection risk) |
| SEC003 | high | `eval()` / `exec()` usage |
| SEC004 | high | `subprocess` with `shell=True` |
| SEC005 | medium | MD5/SHA-1 for security hashing |
| QUA001 | low | Debug `print`/`console.log` in production |
| QUA002 | low | TODO/FIXME/HACK comment left in PR |
| QUA003 | medium | Bare `except:` clause (Python) |
| QUA004 | info | Magic numbers |
| AIP001 | high | Unimplemented stub function body |
| AIP002 | medium | Unreachable code after return/raise |
| AIP003 | medium | Nullable function result used without null check |
| AIP004 | info | Oversized function (AI anti-pattern) |

### AI Semantic Analysis (requires API key)

- Logic errors and incorrect algorithms
- Security vulnerabilities not caught by regex rules
- Missing error handling for failure paths
- Hallucinated or incorrect API usage
- Missing edge cases (null inputs, empty collections, overflow)

AI analysis intentionally does **not** duplicate what ESLint/pylint/spotbugs already report.

## Report Output

### `review.json`

Machine-readable, suitable for dashboards or custom CI scripts.

```json
{
  "passed": false,
  "risk_score": 72,
  "summary": "Found 5 issues. Most severe: [SEC001] Hardcoded credential detected.",
  "stats": { "files_reviewed": 2, "lines_added": 47 },
  "issues": [
    {
      "file": "src/auth/login.py",
      "line": 4,
      "severity": "critical",
      "rule_id": "SEC001",
      "source": "rule",
      "message": "Hardcoded credential detected — use environment variables.",
      "suggestion": "Replace with os.environ['SECRET_NAME']"
    }
  ]
}
```

### `review.md`

Human-readable Markdown with color-coded severity badges, can be posted directly as a PR comment.

## Rules Only (no API key)

```bash
git diff origin/main...HEAD | ai-code-review --rules-only
```

## Supported Languages

Python, TypeScript, JavaScript, Java, Kotlin, and any text file (generic analysis).
Language is auto-detected from file extension.

## Development

```bash
git clone https://github.com/Shiner-D/ai-code-review.git
cd ai-code-review
pip install -e .
pytest tests/
```
