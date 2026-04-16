# TRO稻草人 · 自动发文系统

本目录放置网站内容自动化的脚本。核心是 `auto_publish.py`，通过 **CourtListener 公开法院数据** + **LLM（Gemini 或 Claude）** 每 2-3 天自动生成一篇 TRO 案件速报或深度分析，发布到网站。

---

## 💰 两种方案对比

| 方案 | 月度成本 | 需要信用卡 | 质量 | 上手难度 |
|------|---------|----------|------|---------|
| **Gemini 免费额度**（默认） | **$0** | ❌ 不用 | 中文生成强，质量够用 | ⭐ 5 分钟 |
| Claude API（付费） | ~$2/月 | ✅ 要绑卡 | 法律长文更细腻 | ⭐ 5 分钟 |

Gemini 1.5 Flash 免费额度 **每天 1500 次、每分钟 15 次、每天 100 万 tokens**。我们每周只跑 3 次，用不到 1%。

> 建议：**先用 Gemini 免费方案跑起来**，运行稳定后如果对文章质量有更高要求，再切到 Claude。切换成本 = 改一个环境变量。

---

## 📐 系统架构

```
┌─────────────────────┐
│  GitHub Actions     │ 每周一/三/五 02:00 UTC 触发（北京时间 10:00）
│  (auto-publish.yml) │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐       ┌──────────────────────┐
│ auto_publish.py     │──────▶│ CourtListener API    │ 抓取最新 Schedule A 案件
│                     │       │ (公开联邦法院数据)   │
│ 1. 查案件           │◀──────│                      │
│ 2. 排序挑最值       │       └──────────────────────┘
│ 3. 调 LLM 生成      │
│ 4. 写 HTML 文件     │       ┌──────────────────────┐
│ 5. 更新 articles.json│──────▶│  Gemini (免费)       │ 二选一
│ 6. 重新渲染首页+归档 │◀──────│  或 Claude (付费)    │ LLM_PROVIDER 环境变量切换
└──────────┬──────────┘       └──────────────────────┘
           │
           ▼
┌─────────────────────┐
│ git commit + push   │ 自动推送，触发 GitHub Pages 部署
└─────────────────────┘
```

### 数据流向

- **单一数据源**：`news/articles.json` 存所有文章元数据，首页和归档页都从这里重新渲染
- **增量发布**：每次只生成一篇新文章，旧文章保留不动
- **去重机制**：靠 docket_number（案号）去重，同一案件不会发两篇
- **保底池**：抓不到新案件时，从 `EVERGREEN_TOPICS` 保底选题池挑一篇"深度分析"

---

## 🚀 方案 A（推荐）：Gemini 免费方案部署

### 1. 申请 Gemini API Key（完全免费，2 分钟）

- 用 Google 账号登录 https://aistudio.google.com/app/apikey
- 点 **Create API key** → 选一个 Google Cloud project（没有就自动创建一个）
- 复制 `AIza...` 开头的 Key

> ❗ **无需绑卡，无需付款信息**，Google AI Studio 直接给免费配额。

### 2. 申请 CourtListener Token（免费，推荐）

- 访问 https://www.courtlistener.com/sign-up/
- 注册账号 → Profile → Developer / API 页面 → 复制 40 位 hex Token
- 免费版每天 5000 次请求，够用

> 不填也能跑，只是速率限制紧一点，强烈建议填。

### 3. 把 Key 加到 GitHub Secrets

打开 https://github.com/globallawyer/dcr-tro/settings/secrets/actions

点 **New repository secret**，加两个：

| Name                  | Value                           |
|-----------------------|--------------------------------|
| `GEMINI_API_KEY`      | `AIza...`（上一步拿到的）     |
| `COURTLISTENER_TOKEN` | 40 位 hex                      |

> 不用加 `ANTHROPIC_API_KEY` —— 走免费路线不需要。

### 4. 首次手动触发

打开 https://github.com/globallawyer/dcr-tro/actions/workflows/auto-publish.yml

点 **Run workflow** → 保持 `dry_run = false` → 绿色 **Run workflow**。

- ✅ 约 1-2 分钟 Actions 绿灯
- ✅ 再 1-2 分钟 trolawyer.site 首页多一篇新文章
- ✅ 之后每周一/三/五 北京时间 10:00 自动跑

### 5. 启用定时任务

定时任务默认开启，无需操作。如果仓库 60 天无 commit，GitHub 会暂停定时任务，手动 Run 一次即可复活。

---

## 💎 方案 B：Claude 付费方案（质量更稳）

把默认的 Gemini 切换成 Claude：

### 1. 申请 Anthropic API Key

- 访问 https://console.anthropic.com/ → Settings → API Keys → Create Key
- 复制 `sk-ant-api03-...` Key
- 账户先充值 $10（每次生成 $0.05-0.10，能用 100+ 次）

### 2. 在 GitHub 加 Secret

打开 https://github.com/globallawyer/dcr-tro/settings/secrets/actions

加一个：

| Name | Value |
|------|-------|
| `ANTHROPIC_API_KEY` | `sk-ant-api03-xxx` |

### 3. 切换 provider

打开 https://github.com/globallawyer/dcr-tro/settings/variables/actions

点 **New repository variable**（注意是 Variables，不是 Secrets）：

| Name | Value |
|------|-------|
| `LLM_PROVIDER` | `claude` |

> 想再切回 Gemini，把 `LLM_PROVIDER` 改成 `gemini`（或直接删掉 variable）即可。

---

## 🧪 本地测试

```bash
cd "/Users/insignificant/my Claude zzx/dcr-tro"

# 安装依赖
pip install -r scripts/requirements.txt

# === 方案 A：Gemini 免费 ===
export GEMINI_API_KEY="AIzaSy..."
export COURTLISTENER_TOKEN="your_token"
export LLM_PROVIDER="gemini"          # 默认就是 gemini，可不写
export DRY_RUN=1                      # 只打印不写文件
python scripts/auto_publish.py

# === 方案 B：Claude 付费 ===
export ANTHROPIC_API_KEY="sk-ant-api03-..."
export LLM_PROVIDER="claude"
export DRY_RUN=1
python scripts/auto_publish.py

# 正式跑（会写文件但不会 commit）
unset DRY_RUN
python scripts/auto_publish.py
```

---

## 📝 如何调整

### 改更新频率

编辑 `.github/workflows/auto-publish.yml`：

```yaml
on:
  schedule:
    - cron: "0 2 * * 1,3,5"   # 周一/三/五 北京 10:00
    # - cron: "0 2 * * *"     # 每天
    # - cron: "0 2 * * 1"     # 仅每周一
```

cron 表达式语法：`分 时 日 月 星期`，用 UTC 时间。

### 改模型版本

在 GitHub Variables 设置中可以覆盖：

| Variable | 默认 | 可选值示例 |
|----------|------|----------|
| `LLM_PROVIDER` | `gemini` | `claude` |
| `GEMINI_MODEL` | `gemini-2.0-flash` | `gemini-1.5-pro`（更强但 RPM 更低） |
| `CLAUDE_MODEL` | `claude-sonnet-4-5-20250929` | 任何 Claude 模型 ID |

### 改文风

编辑 `scripts/auto_publish.py` → `ARTICLE_PROMPT_SYSTEM` 里的 editorial voice 段落。

### 加关注品牌

编辑 `KNOWN_BRANDS` 列表（脚本顶部）：

```python
KNOWN_BRANDS = [
    "nike", "adidas", "skechers",
    "your_brand_here",
]
```

品牌命中会让案件排序分数 +20，更容易被选中发文。

### 加保底选题

编辑 `EVERGREEN_TOPICS` 列表。每个选题需要 5 个字段：`category`, `category_label`, `category_icon`, `theme`, `brief`。

---

## 🛡️ 安全与合规

- ✅ **所有数据源都是公开合法的**：CourtListener 是联邦法院公开数据库，美国司法部门的公共记录
- ✅ **不抄袭**：文章由 LLM 基于公开案件事实 + 律所自有专业视角原创生成
- ✅ **可审计**：每次发布会产生一次 commit，历史可追溯
- ✅ **Key 不落仓库**：全部用 GitHub Secrets，`.gitignore` 已排除 `.env`

### 如何检查某次自动发文

打开仓库 Commits 页：https://github.com/globallawyer/dcr-tro/commits/main

搜索 `auto: 自动发布新文章` 前缀的 commit，点进去看当次生成的完整 HTML。

### 如何撤回一篇自动文章

```bash
cd "/Users/insignificant/my Claude zzx/dcr-tro"

# 删 HTML + 从 articles.json 手动去掉对应条目
rm news/2026-XX-XX-slug.html
# 编辑 news/articles.json 删掉对应对象

git add news/ index.html
git commit -m "撤回文章：YYYY-MM-DD-slug"
git push
```

或最简单：`git revert <commit-hash> && git push`。

---

## 🩺 故障排查

### "缺少 GEMINI_API_KEY 环境变量"
→ GitHub Secrets 没配置 `GEMINI_API_KEY`。按 [方案 A 步骤 3] 添加。

### "缺少 ANTHROPIC_API_KEY 环境变量"
→ 你把 `LLM_PROVIDER` 设成了 `claude` 但没配 Anthropic Key。要么加 Key，要么把 `LLM_PROVIDER` variable 删掉回到 gemini。

### Gemini 返回 `429 RESOURCE_EXHAUSTED`
→ 超出每分钟配额（免费版 15 RPM）。我们每周只跑 3 次，基本不会碰到。如果是手动短时间多次触发，等 1 分钟再试。

### Gemini 返回格式异常，extract_article_meta 抽不到内容
→ 偶发，重跑一次即可。如果连续失败，可能是 `GEMINI_MODEL` 换了新模型输出风格变了，检查 `ARTICLE_PROMPT_SYSTEM`。

### CourtListener 返回 429 (Rate Limit)
→ 没登录被限流。添加 `COURTLISTENER_TOKEN` 即可。

### 连续几次都没有新案件
→ 说明最近 7 天 CourtListener 里没有匹配的 Schedule A 案件。脚本会自动走"保底选题池"发一篇深度分析。

### 想完全停掉自动发文
→ 打开 GitHub → Actions → "自动发布 TRO 文章" → 右上 "..." → Disable workflow。

---

## 📊 预期成本

| 项目             | Gemini 方案     | Claude 方案        |
|------------------|----------------|-------------------|
| LLM              | **免费**        | $0.6 – $1.2/月    |
| CourtListener    | 免费            | 免费              |
| GitHub Actions   | 免费（公开仓库）| 免费              |
| GitHub Pages     | 免费            | 免费              |
| **合计**         | **$0**          | **< $2/月**       |

---

## 🔗 相关文档

- 文章发布手动指南：`/news/README.md`
- Gemini API 文档：https://ai.google.dev/gemini-api/docs
- CourtListener API 文档：https://www.courtlistener.com/help/api/rest/
- Anthropic API 文档：https://docs.anthropic.com/

---

**遇到问题？** 联系张兆新律师 · 微信 `mylearnedfriend`
