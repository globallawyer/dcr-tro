# TRO稻草人 · 自动发文系统

本目录放置网站内容自动化的脚本。核心是 `auto_publish.py`，通过 **CourtListener 公开法院数据** + **Claude API** 每 2-3 天自动生成一篇 TRO 案件速报或深度分析，发布到网站。

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
│ 3. 调 Claude 生成    │
│ 4. 写 HTML 文件     │       ┌──────────────────────┐
│ 5. 更新 articles.json│──────▶│ Anthropic Claude API │ 生成 HTML 文章
│ 6. 重新渲染首页+归档 │◀──────│ (claude-sonnet-4.5)  │
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

## 🚀 首次部署步骤

### 1. 申请 API Key

**A. Anthropic API Key（必需）**

- 访问 https://console.anthropic.com/
- Settings → API Keys → Create Key
- 复制 `sk-ant-api03-...` 开头的 Key
- 建议先充值 $10（每次生成约消耗 $0.05-$0.10）

**B. CourtListener Token（推荐，免费）**

- 访问 https://www.courtlistener.com/sign-up/
- 注册账号 → Settings → API 页面
- 复制 40 位 hex 的 Token
- 免费版每天 5000 次请求，够用

> 💡 不填 CourtListener Token 脚本也能跑，只是未登录的 IP 有速率限制。强烈建议填上。

### 2. 把 Key 配置到 GitHub Secrets

在浏览器打开仓库：
```
https://github.com/globallawyer/dcr-tro/settings/secrets/actions
```

点 **New repository secret**，分别添加两个 Secret：

| Name                  | Value                                     |
|-----------------------|-------------------------------------------|
| `ANTHROPIC_API_KEY`   | `sk-ant-api03-xxx...`                    |
| `COURTLISTENER_TOKEN` | `abc123...` （40位 hex）                 |

### 3. 首次手动触发测试

在浏览器打开：
```
https://github.com/globallawyer/dcr-tro/actions/workflows/auto-publish.yml
```

点右上角 **Run workflow** → 保持 `dry_run = false` → 绿色 Run workflow 按钮

观察执行日志：
- 如果成功：约 1-2 分钟后，网站多一篇新文章
- 如果失败：点进 job 看报错，最常见的是 API Key 没配置对

### 4. 启用定时任务

定时任务默认就是开启的，无需额外操作。每周一、三、五 北京时间上午 10:00 自动运行。

如果仓库连续 60 天无 commit，GitHub 会暂停定时任务。到时候手动 Run 一次就会重新激活。

---

## 🧪 本地测试

```bash
cd "/Users/insignificant/my Claude zzx/dcr-tro"

# 安装依赖
pip install -r scripts/requirements.txt

# 设置环境变量
export ANTHROPIC_API_KEY="sk-ant-api03-xxx"
export COURTLISTENER_TOKEN="your_token"

# DRY_RUN 模式：只打印，不写文件、不 commit
export DRY_RUN=1
python scripts/auto_publish.py

# 正式运行：真写文件（不会 commit，需手动 git push）
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

### 改模型 / 文风

编辑 `scripts/auto_publish.py`：

- **换模型**：改 `MODEL = "claude-sonnet-4-5-20250929"` 为其他 Claude 模型
- **改文风**：调整 `ARTICLE_PROMPT_SYSTEM` 里的 editorial voice 段落
- **改字数**：调整 `generate_case_article` 和 `generate_evergreen_article` 里的字符范围

### 加关注品牌

编辑 `KNOWN_BRANDS` 列表（脚本顶部）：

```python
KNOWN_BRANDS = [
    "nike", "adidas", "skechers",
    # 加新品牌
    "your_brand_here",
]
```

品牌命中会让案件的排序分数 +20，更容易被选中发文。

### 加保底选题

编辑 `EVERGREEN_TOPICS` 列表。每个选题需要 5 个字段：`category`, `category_label`, `category_icon`, `theme`, `brief`。

---

## 🛡️ 安全与合规

- ✅ **所有数据源都是公开合法的**：CourtListener 是联邦法院公开数据库，美国司法部门的公共记录
- ✅ **不抄袭**：文章由 Claude 基于公开案件事实 + 律所自有专业视角原创生成
- ✅ **可审计**：每次发布会产生一次 commit，历史可追溯
- ✅ **Key 不落仓库**：全部用 GitHub Secrets，`.gitignore` 已排除 `.env`

### 如何检查某次自动发文

打开仓库 Commits 页：
```
https://github.com/globallawyer/dcr-tro/commits/main
```

搜索 `auto: 自动发布新文章` 前缀的 commit，点进去可以看当次生成的完整 HTML 内容。

### 如何撤回一篇自动文章

```bash
cd "/Users/insignificant/my Claude zzx/dcr-tro"

# 找到那篇的 commit
git log --oneline news/2026-XX-XX-slug.html

# 删除 HTML 文件
rm news/2026-XX-XX-slug.html

# 从 articles.json 中删掉对应条目（手动编辑）
# 然后 commit 推送
git add news/ index.html
git commit -m "撤回文章：YYYY-MM-DD-slug"
git push
```

或者最简单：

```bash
# 回退到某个 commit（所有后续的自动发文都会消失）
git revert <commit-hash>
git push
```

---

## 🩺 故障排查

### "ANTHROPIC_API_KEY 环境变量缺失"
→ GitHub Secrets 没配置。照 [首次部署步骤 2] 添加。

### CourtListener 返回 429 (Rate Limit)
→ 没登录被限流。添加 `COURTLISTENER_TOKEN` 即可。

### Claude 报错 `overloaded_error`
→ Claude API 临时过载，过几分钟重试。脚本不会自动重试，下次 cron 会继续跑。

### 连续几次都没有新案件
→ 说明最近 7 天 CourtListener 里没有匹配的 Schedule A 案件。脚本会自动走"保底选题池"发一篇深度分析。

### 生成的文章格式坏了
→ `extract_article_meta()` 从 HTML 里用正则抽元数据。如果 Claude 生成的 HTML 结构不标准，会抽取失败。检查 `scripts/auto_publish.py` 里的 `ARTICLE_PROMPT_SYSTEM`，强化结构要求，或改用更强的正则。

### 想完全停掉自动发文
→ 打开 GitHub 仓库 → Actions → 左侧列表找到"自动发布 TRO 文章" → 右上角 "..." 菜单 → Disable workflow。

---

## 📊 预期成本

| 项目             | 单次消耗        | 月度（周 3 次）  |
|------------------|----------------|-----------------|
| Claude API       | $0.05 - $0.10   | $0.6 - $1.2    |
| CourtListener    | 免费            | 免费            |
| GitHub Actions   | 免费（公开仓库）| 免费            |
| **合计**         | -               | **< $2/月**     |

---

## 🔗 相关文档

- 文章发布手动指南：`/news/README.md`
- 网站整体架构：`/README.md`
- CourtListener API 文档：https://www.courtlistener.com/help/api/rest/
- Anthropic API 文档：https://docs.anthropic.com/

---

**遇到问题？** 联系张兆新律师 · 微信 `mylearnedfriend`
