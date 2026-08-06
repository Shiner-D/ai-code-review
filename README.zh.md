# AI 代码审查工具

一个平台无关的命令行工具，用于在 PR 合并前验证 AI 生成代码的可靠性。

结合快速静态规则引擎与 AI 语义分析，捕捉 ESLint/pylint 等 lint 工具无法发现的问题：逻辑错误、安全漏洞、缺失边界处理、AI 幻觉调用。

支持多种 AI 审查模型：Claude、DeepSeek、OpenAI，以及本地 Ollama。

## 工作原理

```
git diff → 规则引擎 → AI 语义分析 → JSON + Markdown 报告 → 退出码
```

1. **规则引擎** — 基于正则/模式的静态检查，无需 API 调用，速度快
2. **AI 语义分析** — 深层语义审查，支持 Claude / DeepSeek / OpenAI / Ollama
3. **报告输出** — JSON（供脚本处理）+ Markdown（可直接贴到 PR 评论）
4. **退出码** — `0` 通过，`1` 失败，用于控制 CI/CD 合并门禁

## 快速开始

### 第一步：安装

```bash
# 基础安装（含 Claude 支持）
pip install git+https://github.com/Shiner-D/ai-code-review.git

# 如需使用 DeepSeek / OpenAI / Ollama，额外安装 openai 包
pip install "ai-code-review[openai]"
```

### 第二步：配置 API Key

根据你选用的模型，设置对应的环境变量：

```bash
# ── Claude（默认）──────────────────────────────────────────
export ANTHROPIC_API_KEY=sk-ant-...

# ── DeepSeek ────────────────────────────────────────────────
export AI_REVIEW_API_KEY=sk-...
export AI_REVIEW_BASE_URL=https://api.deepseek.com

# ── OpenAI ──────────────────────────────────────────────────
export AI_REVIEW_API_KEY=sk-...

# ── Ollama（本地运行，无需 API Key）─────────────────────────
export AI_REVIEW_BASE_URL=http://localhost:11434/v1
```

> Windows PowerShell 使用 `$env:变量名 = "值"` 语法，或用
> `[Environment]::SetEnvironmentVariable("变量名", "值", "User")` 永久生效。

### 第三步：在你的项目里执行审查

```bash
# 切换到被审查的项目目录（不是本工具的目录）
cd /path/to/your-project

# 审查当前分支相对于主分支的所有变更（使用默认 Claude 模型）
git diff origin/main...HEAD | ai-code-review --output-dir ./ai-review

# 使用 DeepSeek 审查
git diff origin/main...HEAD | ai-code-review --model deepseek-chat --output-dir ./ai-review

# 使用本地 Ollama 审查
git diff origin/main...HEAD | ai-code-review --model llama3.2 --output-dir ./ai-review
```

执行后在 `./ai-review/` 目录生成 `review.json` 和 `review.md` 两份报告。

## 推荐使用时机

功能开发完成、准备创建 PR 合并到主分支之前执行：

```
写代码（可以多次 commit）
        ↓
git push origin feature/xxx
        ↓
执行 ai-code-review 审查   ← 这里
        ↓
查看报告，修复问题
        ↓
创建 PR / 合并
```

## 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--diff-file FILE` | 标准输入 | 从文件读取 diff，替代管道输入 |
| `--output-dir DIR` | 不输出文件 | 报告文件写入目录，生成 `review.json` 和 `review.md` |
| `--format` | `json,markdown` | 输出格式，逗号分隔 |
| `--fail-on SEVERITY` | `high` | 达到该严重级别时退出码返回 1，阻止合并 |
| `--model MODEL` | `claude-sonnet-4-6` | AI 模型名称，自动识别 provider |
| `--base-url URL` | 环境变量 | 自定义 API 地址，也可用 `AI_REVIEW_BASE_URL` 设置 |
| `--rules-only` | false | 跳过 AI 分析，仅运行静态规则（无需 API Key） |
| `--max-issues N` | 100 | 报告中最多显示的问题数量 |

**严重级别**（从高到低）：`critical` → `high` → `medium` → `low` → `info`

## 支持的 AI Provider

工具根据 `--model` 参数自动判断使用哪个 provider，无需额外配置：

| Provider | 模型示例 | API Key 变量 | Base URL |
| --- | --- | --- | --- |
| Claude（默认） | `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` | 无需设置 |
| DeepSeek | `deepseek-chat` | `AI_REVIEW_API_KEY` | `https://api.deepseek.com` |
| OpenAI | `gpt-4o` | `AI_REVIEW_API_KEY` | 无需设置 |
| Ollama（本地） | `llama3.2` | 不需要 | `http://localhost:11434/v1` |

> `AI_REVIEW_API_KEY` 优先级最高，会覆盖 `ANTHROPIC_API_KEY` 和 `OPENAI_API_KEY`。
> 模型名以 `claude-` 开头走 Anthropic SDK（支持 prompt caching），其他走 OpenAI 兼容接口。

## CI/CD 集成

参考 [`examples/`](examples/) 目录中的配置文件：

- [`github-actions.yml`](examples/github-actions.yml) — GitHub Actions，自动在 PR 中发表评论
- [`gitlab-ci.yml`](examples/gitlab-ci.yml) — GitLab CI，Merge Request 时触发
- [`azure-pipelines.yml`](examples/azure-pipelines.yml) — Azure DevOps Pipelines

在 CI 环境中将对应的 API Key 设置为加密的 Secret 变量即可。

## 检查内容

### 静态规则（无需 API Key）

| 规则 ID | 严重级别 | 描述 |
|---------|----------|------|
| SEC001 | critical | 硬编码的密码、Token、密钥等凭据 |
| SEC002 | high | SQL 字符串拼接（SQL 注入风险） |
| SEC003 | high | `eval()` / `exec()` 的使用 |
| SEC004 | high | `subprocess` 使用 `shell=True` |
| SEC005 | medium | 使用 MD5/SHA-1 做安全性哈希 |
| QUA001 | low | 生产代码中遗留的 `print` / `console.log` |
| QUA002 | low | PR 中遗留的 TODO / FIXME / HACK 注释 |
| QUA003 | medium | Python 裸 `except:` 子句 |
| QUA004 | info | 魔法数字（未命名的数字字面量） |
| AIP001 | high | 函数体仅为 `pass`，未实现的存根函数 |
| AIP002 | medium | return/raise 之后的不可达代码 |
| AIP003 | medium | 可能返回 null 的函数调用结果未做空值检查 |
| AIP004 | info | 函数过长（AI 生成代码的常见反模式） |

### AI 语义分析（需要 API Key）

- 逻辑错误与算法缺陷
- 静态规则未覆盖的安全漏洞
- 缺失的错误处理路径
- 幻觉 API 调用或方法签名错误
- 缺失的边界处理（null 输入、空集合、整数溢出等）

AI 分析**不重复** ESLint / pylint / spotbugs 已有的检查项，专注于语义层面的问题。

## 报告示例

### `review.json`（机器可读）

```json
{
  "passed": false,
  "risk_score": 72,
  "summary": "发现 5 个问题，最高严重级别：[SEC001] 检测到硬编码凭据。",
  "stats": { "files_reviewed": 2, "lines_added": 47 },
  "issues": [
    {
      "file": "src/auth/login.py",
      "line": 4,
      "severity": "critical",
      "rule_id": "SEC001",
      "source": "rule",
      "message": "检测到硬编码凭据，请使用环境变量或密钥管理服务。",
      "suggestion": "替换为 os.environ['SECRET_NAME']"
    }
  ]
}
```

### `review.md`（人类可读）

生成带颜色标记的 Markdown，可直接作为 PR 评论发布，每个问题包含具体位置、描述和修复建议。

## 仅运行静态规则（无需 API Key）

适合快速检查或暂无 API Key 的场景：

```bash
git diff origin/main...HEAD | ai-code-review --rules-only
```

## 支持的编程语言

Python、TypeScript、JavaScript、Java、Kotlin，以及所有文本文件（通用分析）。语言根据文件扩展名自动识别。

## 本地开发

```bash
git clone https://github.com/Shiner-D/ai-code-review.git
cd ai-code-review
pip install -e .
pytest tests/
```
