# TRO稻草人新闻发布指南

本目录存放网站的 **TRO新闻 & 深度分析** 文章。本文档说明如何发布一篇新文章。

---

## 📁 目录结构

```
news/
├── index.html                          ← 新闻归档页（所有文章列表）
├── article.css                         ← 所有文章共用的样式表
├── _template.html                      ← 新文章模板（复制这个开始）
├── README.md                           ← 本说明文件
└── YYYY-MM-DD-slug.html               ← 每篇文章一个文件
```

## 🚀 快速发布新文章（5 步走）

### 第 1 步：复制模板

把 `_template.html` 复制一份，命名规则：

```
YYYY-MM-DD-英文短标题.html
```

**示例：**
- ✅ `2026-05-01-new-gbc-case.html`
- ✅ `2026-05-03-client-win-50k.html`
- ❌ `新文章.html`（不要用中文文件名）
- ❌ `article1.html`（文件名要有意义）

### 第 2 步：修改模板中的【替换】标记

打开新复制的文件，所有 `【替换】` 注释的地方都要改：

| 位置 | 内容 |
|------|------|
| `<title>` | 文章标题 |
| `<meta name="description">` | 150字内的摘要 |
| `<meta name="keywords">` | SEO关键词，逗号分隔 |
| `<span class="article-cat">` | 分类标签（见下表） |
| `<h1 class="article-title">` | 大标题 |
| `article-meta` 中的日期 | 发布日期 |
| `<div class="article-body">` | 正文内容 |
| `article-tags` | 文章标签 |
| `related-section` | 相关阅读（挑 3 篇） |

### 第 3 步：正文内容

正文写在 `<div class="article-body">` 里面。常用元素：

| 元素 | 代码 |
|------|------|
| 大标题 | `<h2>一、小节名</h2>` |
| 小标题 | `<h3>1.1 子节名</h3>` |
| 段落 | `<p>正文...</p>` |
| 加粗 | `<strong>重点</strong>` |
| 无序列表 | `<ul><li>项</li></ul>` |
| 有序列表 | `<ol><li>项</li></ol>` |
| 案号 | `<code>1:26-cv-00626</code>` |
| 引用 | `<blockquote>金句...</blockquote>` |
| 表格 | `<table>` 见模板示例 |
| 警告框 | `<div class="callout warn">` |
| 案件卡片 | `<div class="case-info-card">` |
| 中段CTA | `<div class="article-cta">` |

**所有样式都在 `article.css` 里定义好了**，直接用 class 名就行。

### 第 4 步：把文章添加到首页和归档页

#### (A) 更新首页 `/index.html`

在 `<section id="news">` 里把最新文章的链接更新到合适位置。

首页新闻区有 3 个区域：
- **左侧Featured大卡**：放最新最重要的一篇
- **右侧侧边列表（4个）**：最近 4 篇按时间倒序
- **下方小卡片（3个）**：更早的文章

直接改 HTML 里的标题、链接、日期就行。

#### (B) 更新归档页 `/news/index.html`

在 `<main class="archive-list">` 里，**最新的文章放到最上面**。
复制已有的 `<a class="archive-card">` 块，改成新文章的内容。

### 第 5 步：推送到 GitHub

在终端执行（Mac 打开 "终端" App）：

```bash
cd "/Users/insignificant/my Claude zzx/dcr-tro"
git add news/ index.html
git commit -m "发布新文章：文章标题"
git push
```

约 1-2 分钟后，`https://trolawyer.site/` 自动更新上线 ✅

---

## 📝 分类标签说明

| Class | 图标 | 场景 |
|-------|------|------|
| `cat-analysis` | `fa-gavel` / `fa-chart-line` | 深度分析 · 长篇解读 |
| `cat-alert` | `fa-bolt` | 紧急预警 · 突发新案件 |
| `cat-warn` | `fa-exclamation-triangle` | 行业预警 · 策略动向 |
| `cat-win` | `fa-trophy` | 胜诉快讯 · 客户成功案例 |
| `cat-guide` | `fa-book` / `fa-shield-halved` | 科普教程 · 新手指南 |

---

## 💡 内容写作建议

### 哪些选题容易"爆"

1. **新案件速报** — 立案 24 小时内第一时间拆解（对标 SellerAgis）
2. **律所策略动向** — GBC/Keith 新玩法分析（对标麦家支持）
3. **胜诉案例** — 具体金额、具体过程、具体证据（最有说服力）
4. **数据报告** — 月度/季度 TRO 数据（权威性）
5. **科普 Checklist** — 可以打印保存的干货（传播力强）

### 写作节奏建议

- **开头 150 字**：案件背景 + 关键数字（案号、金额、被告数）
- **中段**：用 `<h2>` 分 3-5 个小节，每节不超过 3 段
- **案件卡片**：放在第 2-3 段后，提升可读性
- **中段 CTA**：文章中间放一个 `article-cta`，引导加微信
- **结尾金句**：用 `<blockquote>` 收尾，让读者有记忆点

### SEO 建议

- **标题包含关键词**：如"Skechers TRO"、"GBC律所"、"胜诉快讯"
- **摘要 150 字内**：前 100 字最重要（搜索引擎优先抓取）
- **关键词 5-10 个**：品牌名、律所名、案件类型、案号
- **内链丰富**：每篇文章至少链接到 3 篇相关文章
- **图片 alt 文字**：如果加图，alt 属性写清楚产品/人物

### 更新频率建议

| 频率 | 内容 |
|------|------|
| **每周 1-2 篇** | 新案件速报（保持活跃度） |
| **每月 1 篇** | 深度分析 / 律所档案（建立专业形象） |
| **每月 1 篇** | 胜诉案例（转化利器） |
| **每季度 1 篇** | 数据报告（权威背书） |

## 🔗 辅助工具

### 写作 AI 辅助
- **Claude / ChatGPT**：先写一稿中文，再请 AI 帮你改口吻和结构
- **改编他人文章**：参考麦家支持、SellerAgis 的文章选题，用自己的语言和案例重写（不要直接抄袭）

### 案件信息源
- **TROTracker.com** — 你们的自研平台，第一手数据
- **CourtListener** (https://www.courtlistener.com/) — 联邦法院公开文件
- **PACER** (https://pacer.uscourts.gov/) — 官方案件档案（需付费）

### 图标查询
- **Font Awesome** (https://fontawesome.com/icons)
  搜索后复制类名即可，如 `fa-gavel`

---

## ❓ 常见问题

**Q1: 我不会 HTML，怎么办？**
A: 只需替换模板里【替换】标记的文字，HTML 结构不用动。遇到问题截图发微信给技术支持。

**Q2: 文章能带图片吗？**
A: 可以。把图片放在 `/news/images/` 子目录下，然后在正文用 `<img src="images/xxx.jpg" alt="描述">` 引用。

**Q3: 改了之后网站多久更新？**
A: `git push` 后 1-2 分钟 GitHub Pages 会自动重新部署。硬刷新浏览器（Cmd+Shift+R）可看到最新版。

**Q4: 万一改错了怎么办？**
A: Git 有版本历史，可以随时回退。告诉技术支持"回到上一版"即可。

**Q5: 能用 Markdown 写吗？**
A: 当前是纯 HTML。如果以后文章多了，可以改造成 Markdown + 静态生成器（Jekyll/Hugo），目前手动维护更灵活。

---

## 📞 技术支持

有任何技术问题，联系：张兆新律师 · 微信 `mylearnedfriend`

---

**祝写作顺利，多出爆款！** 🎉
