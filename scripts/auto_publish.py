#!/usr/bin/env python3
"""
TRO稻草人 · 自动发文脚本

流程：
1. 查询 CourtListener 最近 7 天 Schedule A / TRO 新案件
2. 按品牌 + 法院 + 关键词排序，挑出最值得写的一个
3. 调 Claude API 生成文章 HTML
4. 保存到 news/YYYY-MM-DD-slug.html
5. 更新 news/articles.json
6. 重新渲染首页 + 归档页
7. 打印 commit 指令（或直接被 GitHub Actions 调用执行）

需要环境变量：
- ANTHROPIC_API_KEY    (必需)
- COURTLISTENER_TOKEN  (推荐，free signup at courtlistener.com)
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests  # anthropic 仅在 LLM_PROVIDER=claude 时才 import

# ==================== 配置 ====================
REPO_ROOT = Path(__file__).resolve().parent.parent
NEWS_DIR = REPO_ROOT / "news"
ARTICLES_JSON = NEWS_DIR / "articles.json"
INDEX_HTML = REPO_ROOT / "index.html"
ARCHIVE_HTML = NEWS_DIR / "index.html"

# LLM 提供商：deepseek（接近免费，推荐中国用户）/ gemini（美国区免费） / claude（付费质量稳）
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "deepseek").lower()

# DeepSeek 相关（接近免费：充 1 元跑 100+ 篇，支持支付宝/微信）
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

# Gemini 相关（美国区账号免费，中国区常见 limit=0）
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Claude 相关（付费方案）
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

# 法院数据源
COURTLISTENER_TOKEN = os.environ.get("COURTLISTENER_TOKEN", "")

# 不在生产环境则允许 dry-run（只打印不写文件）
DRY_RUN = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")

# Schedule A 常见法院代码
TRO_COURTS = ["ilnd", "flmd", "gand", "cacd", "nysd", "txed"]

# 高频原告品牌（用于筛案件）
KNOWN_BRANDS = [
    "nike", "adidas", "skechers", "puma", "new balance", "jordan",
    "ugg", "deckers", "chanel", "gucci", "louis vuitton", "hermes", "rolex", "coach",
    "disney", "marvel", "pokemon", "nintendo", "pop mart", "labubu", "bts", "blackpink",
    "yeti", "stanley", "hydro flask", "dyson", "apple", "lego", "lacoste",
]

# 保底选题（抓不到案件时用）
EVERGREEN_TOPICS: list[dict[str, Any]] = [
    {
        "category": "guide",
        "category_label": "科普教程",
        "category_icon": "fa-book",
        "theme": "PayPal 资金冻结全流程详解",
        "brief": "详解 PayPal 在 TRO 案件中冻结资金的完整流程、法律依据、解冻条件和卖家应对策略",
    },
    {
        "category": "analysis",
        "category_label": "深度分析",
        "category_icon": "fa-gavel",
        "theme": "Schedule A 批量诉讼的法律本质",
        "brief": "深度解读 Schedule A 这种批量诉讼机制的法律依据、程序特点、以及为何成为跨境电商维权的主流",
    },
    {
        "category": "warn",
        "category_label": "行业预警",
        "category_icon": "fa-exclamation-triangle",
        "theme": "2026年跨境电商 IP 维权趋势观察",
        "brief": "基于 TROTracker 监控数据，分析 2026 年 TRO 案件的品牌、律所、法院、地域趋势变化",
    },
    {
        "category": "guide",
        "category_label": "科普教程",
        "category_icon": "fa-shield-halved",
        "theme": "商标 vs 版权 vs 外观专利在 TRO 中的区别",
        "brief": "讲清楚三种 IP 权利在 TRO 案件中的不同诉因、赔偿标准、抗辩空间和卖家应对区别",
    },
    {
        "category": "analysis",
        "category_label": "深度分析",
        "category_icon": "fa-balance-scale",
        "theme": "法定赔偿 $200 万上限是如何计算出来的",
        "brief": "解读美国兰哈姆法下商标法定赔偿的计算方式、影响因素、以及实际判决中的常见区间",
    },
    {
        "category": "guide",
        "category_label": "科普教程",
        "category_icon": "fa-handshake",
        "theme": "TRO 和解协议必须看的 8 个条款",
        "brief": "Full Release / No Admission / Confidentiality 等关键条款解读，帮卖家避开和解协议中的坑",
    },
    {
        "category": "warn",
        "category_label": "行业预警",
        "category_icon": "fa-magnifying-glass",
        "theme": "POP MART 维权策略观察",
        "brief": "泡泡玛特旗下 LABUBU / MOLLY / DIMOO 等 IP 在海外维权力度、涉及律所、典型案件",
    },
    {
        "category": "analysis",
        "category_label": "深度分析",
        "category_icon": "fa-building-columns",
        "theme": "为什么 Schedule A 都在伊利诺伊北区法院立案",
        "brief": "N.D. Illinois 成为 Schedule A 大本营的历史、法律、实务原因，以及对卖家应对的影响",
    },
    {
        "category": "guide",
        "category_label": "科普教程",
        "category_icon": "fa-file-contract",
        "theme": "跨境卖家如何留存采购合规证据",
        "brief": "从供应商合同、发票、授权文件到产品检测报告，详解合规证据的留存策略",
    },
    {
        "category": "guide",
        "category_label": "科普教程",
        "category_icon": "fa-user-tie",
        "theme": "美国联邦法院律师选择指南",
        "brief": "Bar Admission / Federal Court Admission / Pro Hac Vice 的区别，以及选择 TRO 律师的硬指标",
    },
]


# ==================== CourtListener 客户端 ====================

def search_courtlistener(days_back: int = 7) -> list[dict[str, Any]]:
    """从 CourtListener 查询最近 N 天的 TRO / Schedule A 案件。"""
    base_url = "https://www.courtlistener.com/api/rest/v4/search/"
    filed_after = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")

    headers = {}
    if COURTLISTENER_TOKEN:
        headers["Authorization"] = f"Token {COURTLISTENER_TOKEN}"

    queries = [
        '"schedule a defendants"',
        '"doe defendants" trademark',
        '"temporary restraining order" counterfeit',
    ]

    all_cases: list[dict[str, Any]] = []
    seen_dockets: set[str] = set()

    for court in TRO_COURTS:
        for q in queries:
            params = {
                "type": "r",  # RECAP docs
                "q": q,
                "court": court,
                "filed_after": filed_after,
                "order_by": "dateFiled desc",
            }
            try:
                r = requests.get(base_url, headers=headers, params=params, timeout=30)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                print(f"[warn] CourtListener 查询失败 {court} q={q!r}: {e}", file=sys.stderr)
                continue

            for case in (data.get("results") or [])[:10]:
                docket = case.get("docketNumber") or case.get("docket_number") or ""
                if not docket or docket in seen_dockets:
                    continue
                seen_dockets.add(docket)
                all_cases.append({
                    "case_name": case.get("caseName") or case.get("case_name") or "",
                    "docket_number": docket,
                    "court": case.get("court") or court,
                    "court_id": court,
                    "date_filed": case.get("dateFiled") or case.get("date_filed") or "",
                    "nature_of_suit": case.get("suitNature") or case.get("nature_of_suit") or "",
                    "attorney": case.get("attorney") or "",
                    "url": f"https://www.courtlistener.com{case.get('absolute_url', '')}",
                })

    return all_cases


def rank_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """对案件打分排序。"""
    scored: list[tuple[int, dict[str, Any]]] = []

    for c in cases:
        score = 0
        name_lower = c["case_name"].lower()

        # 知名品牌加分
        for brand in KNOWN_BRANDS:
            if brand in name_lower:
                score += 20
                c["matched_brand"] = brand
                break

        # Schedule A 特征加分
        if "schedule a" in name_lower or "doe" in name_lower:
            score += 10

        # 新案件加分（越新越好）
        if c.get("date_filed"):
            try:
                age_days = (datetime.now(timezone.utc).date() - datetime.fromisoformat(c["date_filed"]).date()).days
                score += max(0, 10 - age_days)
            except Exception:
                pass

        # IP相关诉因加分
        nos = c.get("nature_of_suit", "").lower()
        if "trademark" in nos or "copyright" in nos or "patent" in nos:
            score += 5

        # 首选法院加分
        if c.get("court_id") == "ilnd":
            score += 3

        if score > 0:
            scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored]


# ==================== 已发布文章去重 ====================

def load_articles_json() -> dict[str, Any]:
    """加载 articles.json。"""
    with open(ARTICLES_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def save_articles_json(data: dict[str, Any]) -> None:
    """保存 articles.json。"""
    with open(ARTICLES_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_case_already_published(case: dict[str, Any], articles: list[dict[str, Any]]) -> bool:
    """检查该案件是否已写过文章。"""
    docket = case.get("docket_number", "").replace(":", "").replace("-", "").lower()
    if not docket:
        return False
    for a in articles:
        existing = (a.get("case_no") or "").replace(":", "").replace("-", "").lower()
        if existing and existing == docket:
            return True
    return False


# ==================== Slug / 文件名生成 ====================

def slugify(text: str, max_len: int = 40) -> str:
    """把中英文标题变成文件名安全的 slug。"""
    text = text.lower()
    # 去掉大部分非字母数字
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text)
    text = text.strip("-")
    # 非 ASCII 字符太多时，用时间戳兜底
    ascii_ratio = sum(1 for c in text if ord(c) < 128) / max(len(text), 1)
    if ascii_ratio < 0.5:
        text = "auto-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    return text[:max_len].rstrip("-")


def case_to_slug(case: dict[str, Any]) -> str:
    """根据案件生成 slug，优先用品牌+案号。"""
    brand = case.get("matched_brand", "")
    docket = case.get("docket_number", "")
    # 从 docket 抽出 cv 编号，如 1:26-cv-02891 → 26cv02891
    m = re.search(r"(\d+)[\-\s]*cv[\-\s]*(\d+)", docket, flags=re.I)
    cv_id = f"{m.group(1)}cv{m.group(2)}" if m else slugify(docket)
    if brand:
        return f"{slugify(brand)}-tro-{cv_id}"
    return f"tro-{cv_id}"


# ==================== Claude 文章生成 ====================

ARTICLE_PROMPT_SYSTEM = """你是 TRO稻草人律所研究部资深法律内容编辑。你为跨境电商卖家撰写 TRO 案件动态与法律解读文章。

你的风格：
- 语言简洁专业，不说废话
- 有具体数据（但只引用你被明确给出的真实数据；绝不编造案号、金额、人数）
- 案件速报偏中立客观；律所分析偏锐利洞察；科普教程偏实用可执行
- 在合适的位置引导读者联系稻草人团队

严格要求：
- 你只输出 HTML 内容，不要任何解释、不要 markdown 代码块
- 你必须严格使用给定的模板结构
- 不要改变 CSS class 名称
- 不要使用任何外部图片
- 遇到不确定的具体数字，用"据稻草人分析"、"预计"、"多名"等表述
- 不要承诺具体的和解金额或胜率
- 全文中文简体，专业术语保留英文原文"""


def _article_template_reference() -> str:
    """返回给 LLM 参考的 HTML 模板（提示用，不要让它完整复制）。"""
    return """
## HTML 模板参考（你要返回的格式）

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{文章标题}} | TRO稻草人</title>
    <meta name="description" content="{{150字内摘要}}">
    <meta name="keywords" content="{{关键词1,关键词2,...}}">
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚖️</text></svg>">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <link rel="stylesheet" href="article.css">
</head>
<body>

<nav class="navbar">
    <div class="nav-inner">
        <a href="../" class="nav-logo">
            <img src="../logo.png" alt="TRO稻草人" onerror="this.style.display='none'">
            <div class="nav-logo-text"><span>TRO</span>稻草人</div>
        </a>
        <a href="../#news" class="nav-back"><i class="fas fa-arrow-left"></i> 返回首页</a>
    </div>
</nav>

<div class="breadcrumb">
    <a href="../">首页</a><span>›</span>
    <a href="./">TRO新闻</a><span>›</span>
    <span>{{面包屑短标题}}</span>
</div>

<main class="article-container">
    <header class="article-header">
        <span class="article-cat {{cat-class}}"><i class="fas {{category_icon}}"></i> {{category_label}}</span>
        <h1 class="article-title">{{大标题}}</h1>
        <div class="article-meta">
            <div class="article-author">
                <div class="article-author-avatar">张</div>
                <div class="article-author-info">
                    <strong>{{作者}}</strong>
                    <small>{{作者简介，如 "稻草人研究部" 或 "中美双证 · 天册律所"}}</small>
                </div>
            </div>
            <span><i class="far fa-calendar"></i> {{YYYY-MM-DD}}</span>
            <span><i class="far fa-clock"></i> 阅读约 {{N}} 分钟</span>
            <span><i class="far fa-eye"></i> {{阅读数字}}</span>
        </div>
    </header>

    <div class="article-body">
        <!-- 正文。用 <h2><h3><p><ul><ol><table><blockquote> 等标签组织。 -->
        <!-- 如果是案件速报，必须包含 <div class="case-info-card"> 展示案件摘要 -->
        <!-- 适当使用 <div class="callout warn/key/tip/success"> 做提示 -->
        <!-- 中段插入一次 <div class="article-cta"> 做转化 -->
    </div>

    <footer class="article-footer">
        <div class="article-tags">
            <a href="#">#{{标签1}}</a>
            <a href="#">#{{标签2}}</a>
            <a href="#">#{{标签3}}</a>
        </div>
        <div class="author-card">
            <div class="author-card-avatar">张</div>
            <div class="author-card-body">
                <h4>张兆新 律师</h4>
                <p>中国 + 美国加州双证律师 · 天册律师事务所 · TRO稻草人团队创始人 · 累计代理TRO案件500+，成功解冻总金额超 $8,000,000</p>
            </div>
        </div>
    </footer>
</main>

<div class="article-footer-bar">
    <p>&copy; 2024-2026 TRO稻草人 | <a href="../">返回首页</a> | <a href="../#contact">联系律师</a> | <a href="./">全部新闻</a></p>
</div>

</body>
</html>
```

## 可用的 callout 样式

- `<div class="callout warn">` ⚠️ 警告/风险
- `<div class="callout key">` 🔑 关键要点
- `<div class="callout tip">` 💡 提示
- `<div class="callout success">` ✅ 建议/好消息

每个 callout 内部结构：
```html
<div class="callout warn">
    <i class="fas fa-triangle-exclamation callout-icon"></i>
    <div class="callout-content">
        <h4>标题</h4>
        <p>内容</p>
    </div>
</div>
```

## article-cta 转化条格式

```html
<div class="article-cta">
    <div class="article-cta-text">
        <h4><i class="fab fa-weixin"></i> CTA 标题</h4>
        <p>引导文案</p>
    </div>
    <a href="../#contact" class="article-cta-btn"><i class="fab fa-weixin"></i> 按钮文字</a>
</div>
```

## case-info-card 案件卡片格式

```html
<div class="case-info-card">
    <h4><i class="fas fa-folder-open"></i> 案件摘要</h4>
    <div class="case-info-grid">
        <div class="case-info-item"><div class="label">案号</div><div class="value">{{案号}}</div></div>
        <div class="case-info-item"><div class="label">法院</div><div class="value">{{法院}}</div></div>
        <div class="case-info-item"><div class="label">原告</div><div class="value">{{原告}}</div></div>
        <div class="case-info-item"><div class="label">立案日期</div><div class="value">{{日期}}</div></div>
    </div>
</div>
```
"""


# cat-class 映射
CAT_CLASS = {
    "analysis": "cat-analysis",
    "alert": "cat-alert",
    "warn": "cat-warn",
    "win": "cat-win",
    "guide": "cat-guide",
}


# ==================== LLM 抽象层 ====================

def call_llm(system: str, user: str, max_tokens: int = 8000) -> str:
    """根据 LLM_PROVIDER 调用 LLM，返回生成文本。"""
    if LLM_PROVIDER == "deepseek":
        return _call_deepseek(system, user, max_tokens)
    if LLM_PROVIDER == "gemini":
        return _call_gemini(system, user, max_tokens)
    if LLM_PROVIDER == "claude":
        return _call_claude(system, user, max_tokens)
    raise RuntimeError(
        f"未知的 LLM_PROVIDER: {LLM_PROVIDER!r}（必须是 'deepseek'、'gemini' 或 'claude'）"
    )


def _call_deepseek(system: str, user: str, max_tokens: int) -> str:
    """调用 DeepSeek Chat API（OpenAI 兼容接口，支持中国支付）。"""
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY 环境变量")
    url = f"{DEEPSEEK_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.7,
        "max_tokens": max_tokens,
        "stream": False,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=180)
    if r.status_code != 200:
        try:
            err = r.json().get("error", {}).get("message", r.text[:300])
        except Exception:
            err = r.text[:300]
        raise RuntimeError(f"DeepSeek HTTP {r.status_code}: {err}")
    data = r.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"DeepSeek 返回格式异常: {data}") from e


def _call_gemini(system: str, user: str, max_tokens: int) -> str:
    """调用 Google Gemini API（免费额度），带 429 重试和清晰错误。"""
    if not GEMINI_API_KEY:
        raise RuntimeError("缺少 GEMINI_API_KEY 环境变量")

    # 多个候选模型：主模型失败时自动降级
    candidate_models = [GEMINI_MODEL]
    # 若用户未显式指定，额外准备几个保底模型（按 2026 年在架列表）
    if GEMINI_MODEL in ("gemini-2.5-flash", "gemini-2.0-flash"):
        for fb in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"):
            if fb not in candidate_models:
                candidate_models.append(fb)

    last_error: Exception | None = None
    for model_name in candidate_models:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_name}:generateContent?key={GEMINI_API_KEY}"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": max_tokens,
            },
        }

        # 每个模型最多重试 2 次（429 等待 30s 后重试一次）
        for attempt in range(2):
            try:
                r = requests.post(url, json=payload, timeout=180)
            except requests.RequestException as e:
                last_error = e
                print(f"[warn] Gemini {model_name} 网络异常: {e}", file=sys.stderr)
                break

            if r.status_code == 200:
                data = r.json()
                try:
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    if model_name != GEMINI_MODEL:
                        print(f"[info] 已降级到 {model_name} 成功生成")
                    return text
                except (KeyError, IndexError) as e:
                    # 可能是 safety filter / finish_reason 异常
                    print(
                        f"[warn] Gemini {model_name} 返回无 text："
                        f"finish_reason={data.get('candidates', [{}])[0].get('finishReason')} "
                        f"body={json.dumps(data, ensure_ascii=False)[:500]}",
                        file=sys.stderr,
                    )
                    last_error = e
                    break

            # 非 200：打印详细错误
            try:
                err_body = r.json()
            except Exception:
                err_body = {"raw": r.text[:500]}
            err_msg = err_body.get("error", {}).get("message", str(err_body))[:400]
            print(
                f"[warn] Gemini {model_name} HTTP {r.status_code}: {err_msg}",
                file=sys.stderr,
            )
            last_error = requests.exceptions.HTTPError(
                f"{r.status_code}: {err_msg}", response=r
            )

            # 429 第一次尝试失败，等 30s 重试一次
            if r.status_code == 429 and attempt == 0:
                import time
                print(f"[info] 429 rate limit，等 30 秒后重试 {model_name}...")
                time.sleep(30)
                continue

            # 其他错误（400 / 403 / 404 等）：不重试，直接换下一个模型
            break

    # 所有模型全失败
    diag = (
        "\n所有候选 Gemini 模型全部失败。若错误含 'limit: 0' 或 'quota exceeded'：\n"
        "  → 你的 Google 账号在此区域没有 Gemini 免费额度（中国大陆账号常见）\n"
        "  → 换用 DeepSeek 接近免费方案：Variables 加 LLM_PROVIDER=deepseek，Secrets 加 DEEPSEEK_API_KEY\n"
        "  → 或 Claude 付费方案：Variables 加 LLM_PROVIDER=claude，Secrets 加 ANTHROPIC_API_KEY"
    )
    raise RuntimeError(f"Gemini API 调用失败: {last_error}{diag}")


def _call_claude(system: str, user: str, max_tokens: int) -> str:
    """调用 Anthropic Claude API。"""
    import anthropic  # 延迟 import，避免 gemini 路径也要装这个包
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("缺少 ANTHROPIC_API_KEY 环境变量")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text


def generate_case_article(case: dict[str, Any]) -> dict[str, Any]:
    """为具体案件生成文章（使用当前 LLM_PROVIDER）。返回 {html, meta}。"""
    category = "alert" if "schedule a" in case["case_name"].lower() else "warn"
    category_label = "案件速报" if category == "alert" else "行业预警"
    category_icon = "fa-bolt" if category == "alert" else "fa-exclamation-triangle"

    user_prompt = f"""请为以下刚刚立案的 TRO / Schedule A 案件写一篇 **案件速报** 文章（700-1100字）。

# 案件真实信息（只能使用这些事实，不要编造任何未列出的数据）

- **案号**: {case['docket_number']}
- **案件名**: {case['case_name']}
- **法院**: {case['court']} ({case.get('court_id','')})
- **立案日期**: {case.get('date_filed', '近期')}
- **诉因**: {case.get('nature_of_suit', '知识产权侵权')}
- **涉及品牌（推断）**: {case.get('matched_brand', '未明确')}
- **CourtListener 链接**: {case.get('url', '')}

# 文章元信息

- 分类: {category_label}
- 作者: 稻草人研究部
- 作者简介: TROTracker 监控系统 · 天册律所
- 发布日期: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}

# 写作要求

1. **标题**: 20-35 字，包含案号后 5 位或品牌名，形式如 "【案件速报】XXX品牌再度启动TRO · {case['docket_number']} 观察"
2. **结构**:
   - 开头 100 字内说清楚"什么时间、什么案号、什么品牌、哪个法院、谁代理"
   - 必须包含 <div class="case-info-card"> 展示案件摘要（用上面给的真实数据）
   - 分 2-3 个 <h2> 小节：案件基本信息、诉讼特征分析、卖家应对建议
   - 不要编造具体被告数、金额、胜率——用"多名"、"据稻草人分析"、"预计"等表述
   - 中段插入一次 <div class="article-cta"> 引导加微信
   - 结尾 <blockquote> 金句
3. **标签**: 3-5 个，必须包含品牌名（如有）和"TRO速报"
4. **摘要**: 100-150 字

{_article_template_reference()}

现在请完整输出 HTML，不要任何解释。"""

    html = call_llm(ARTICLE_PROMPT_SYSTEM, user_prompt, max_tokens=8000).strip()
    # 如果模型返回 markdown 代码块，剥掉
    html = re.sub(r"^```html\s*\n", "", html)
    html = re.sub(r"\n```\s*$", "", html)

    meta = extract_article_meta(html)
    meta.update({
        "category": category,
        "category_label": category_label,
        "category_icon": category_icon,
        "source": "auto",
        "case_no": case["docket_number"],
        "author": "稻草人研究部",
    })
    return {"html": html, "meta": meta}


def generate_evergreen_article(topic: dict[str, Any]) -> dict[str, Any]:
    """没有新案件时，用保底选题生成文章（使用当前 LLM_PROVIDER）。"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    user_prompt = f"""请写一篇 TRO 相关的 **{topic['category_label']}** 文章（1000-1500字）。

# 选题

**主题**: {topic['theme']}
**要点**: {topic['brief']}

# 文章元信息

- 分类: {topic['category_label']}（Font Awesome: {topic['category_icon']}）
- 作者: 张兆新 律师（中美双证 · 天册律所）
- 发布日期: {today}

# 写作要求

1. **标题**: 20-35 字，要有吸引力，可以加「深度」「干货」「必读」等前缀
2. **结构**: 开头 + 2-4 个 <h2> 小节 + 结尾金句
3. 必须插入一次 <div class="article-cta"> 中段引导
4. 至少使用 2 个不同类型的 <div class="callout ...">
5. 不要编造具体案号和金额，除非是历史上真实知名案例
6. 充分体现稻草人"500+ 案件经验 · TROTracker 监控数据"的专业背景
7. **标签**: 3-5 个
8. **摘要**: 100-150 字

{_article_template_reference()}

现在请完整输出 HTML，不要任何解释。"""

    html = call_llm(ARTICLE_PROMPT_SYSTEM, user_prompt, max_tokens=10000).strip()
    html = re.sub(r"^```html\s*\n", "", html)
    html = re.sub(r"\n```\s*$", "", html)

    meta = extract_article_meta(html)
    meta.update({
        "category": topic["category"],
        "category_label": topic["category_label"],
        "category_icon": topic["category_icon"],
        "source": "auto",
        "author": "张兆新",
    })
    return {"html": html, "meta": meta}


# ==================== 从生成的 HTML 提取元信息 ====================

def extract_article_meta(html: str) -> dict[str, Any]:
    """从 AI 生成的 HTML 中抽取标题、摘要、标签等。"""
    title_m = re.search(r"<h1 class=\"article-title\">(.*?)</h1>", html, flags=re.S)
    title = (title_m.group(1) if title_m else "").strip()
    # 去掉可能的 HTML 标签
    title = re.sub(r"<[^>]+>", "", title).strip()

    desc_m = re.search(r'<meta name="description" content="([^"]+)"', html)
    excerpt = desc_m.group(1).strip() if desc_m else title

    # 粗估阅读时长：按正文字数 / 300字每分钟
    body_m = re.search(r'<div class="article-body">(.*?)</div>\s*<footer', html, flags=re.S)
    body_text = re.sub(r"<[^>]+>", "", body_m.group(1)) if body_m else ""
    read_min = max(3, min(15, round(len(body_text) / 300)))

    # 抽标签
    tags = re.findall(r'<a href="#">#(.+?)</a>', html)
    tags = [t.strip() for t in tags][:5]

    return {
        "title": title or "TRO 案件动态",
        "excerpt": excerpt[:200],
        "read_time": f"{read_min}分钟",
        "tags": tags,
    }


# ==================== 首页 Ticker + News + 归档页渲染 ====================


def render_ticker(articles: list[dict[str, Any]]) -> str:
    """把 articles 前 6 条渲染成跑马灯 ticker（重复一次实现无缝滚动）。"""
    items = []
    for a in articles[:6]:
        cat = a.get("category", "analysis")
        # 标签类型：warn/alert → 预警；win → 胜诉/和解；其他 → NEW
        if cat in ("warn", "alert"):
            tag = '<span class="tag-warn">预警</span>'
        elif cat == "win":
            tag = '<span class="tag-win">胜诉</span>'
        else:
            tag = '<span class="tag-new">NEW</span>'

        # 标题截短到 30 字
        title = a.get("title", "")
        if len(title) > 30:
            title = title[:28] + "…"

        # 日期 MM-DD
        try:
            d = datetime.fromisoformat(a["date"])
            badge = d.strftime("%m-%d")
        except Exception:
            badge = a.get("date", "")[-5:]

        items.append(
            f'                <div class="ticker-item">{tag} {title} '
            f'<span class="badge">{badge}</span></div>'
        )

    # 无缝滚动需要重复一份
    single_block = "\n".join(items)
    return f"{single_block}\n{single_block}"


def render_homepage_news_block(articles: list[dict[str, Any]]) -> str:
    """把 articles 列表渲染成首页 news 区块（Featured + 侧边 4 条 + 下方 3 张卡）。"""
    if not articles:
        return ""

    featured = articles[0]
    side_list = articles[1:5]
    grid = articles[5:8]

    def fmt_date(d: str) -> str:
        try:
            return datetime.fromisoformat(d).strftime("%Y-%m-%d")
        except Exception:
            return d

    def short_date(d: str) -> str:
        try:
            dt = datetime.fromisoformat(d)
            return dt.strftime("%m-%d")
        except Exception:
            return d

    def cat_badge_style(a: dict[str, Any]) -> tuple[str, str]:
        """(visual-class, inline-style)"""
        m = {
            "analysis": ("cat-analysis", ""),
            "alert":    ("cat-alert", ""),
            "warn":     ("cat-warn", ""),
            "win":      ("cat-win", ""),
            "guide":    ("cat-guide", ""),
        }
        return m.get(a.get("category", "analysis"), ("cat-analysis", ""))

    def status_badge(a: dict[str, Any]) -> str:
        cat = a.get("category", "")
        label = a.get("category_label", "")
        if cat == "warn" or cat == "alert":
            return f'<span class="alert-status st-warn">{label}</span>'
        if cat == "win":
            return f'<span class="alert-status st-settled">{label}</span>'
        if cat == "guide":
            return f'<span class="alert-status" style="background:rgba(142,78,198,0.15);color:#8e4ec6">{"科普"}</span>'
        if cat == "analysis":
            return f'<span class="alert-status" style="background:rgba(26,58,92,0.12);color:var(--primary)">{"深度"}</span>'
        return f'<span class="alert-status">{label}</span>'

    # Featured
    f_url = f"news/{featured['date']}-{featured['slug']}.html"
    f_views = f"{featured.get('views', 0):,}" if featured.get("views") else "—"
    hot_flag = '<span class="news-hot-flag"><i class="fas fa-fire"></i> HOT</span>' if featured.get("hot") else ""
    f_cat_class = cat_badge_style(featured)[0].replace("cat-", "cat-")  # keeps cat-xxx
    featured_html = f'''            <!-- Featured Article -->
            <a href="{f_url}" class="news-featured">
                <div class="news-featured-visual">
                    <span class="news-cat-badge">{featured.get("category_label", "")}</span>
                    {hot_flag}
                    <i class="fas {featured.get("category_icon", "fa-newspaper")}"></i>
                </div>
                <div class="news-featured-body">
                    <div class="news-meta">
                        <span><i class="far fa-calendar"></i> {fmt_date(featured["date"])}</span>
                        <span><i class="far fa-eye"></i> {f_views}</span>
                        <span><i class="fas fa-user-tie"></i> {featured.get("author", "稻草人")}</span>
                    </div>
                    <h3>{featured["title"]}</h3>
                    <p>{featured["excerpt"]}</p>
                    <span class="news-read-more">阅读全文 <i class="fas fa-arrow-right"></i></span>
                </div>
            </a>
'''

    # Side list
    side_html_parts = []
    for i, a in enumerate(side_list, start=1):
        a_url = f"news/{a['date']}-{a['slug']}.html"
        side_html_parts.append(f'''                <a href="{a_url}" class="news-item">
                    <div class="news-item-num">{i:02d}</div>
                    <div class="news-item-body">
                        <h4>{a["title"]}</h4>
                        <div class="news-meta">
                            <span><i class="far fa-calendar"></i> {short_date(a["date"])}</span>
                            {status_badge(a)}
                        </div>
                    </div>
                </a>''')
    side_html = "\n".join(side_html_parts)

    # Grid cards
    grid_html_parts = []
    for a in grid:
        a_url = f"news/{a['date']}-{a['slug']}.html"
        a_views = f"{a.get('views', 0):,}" if a.get("views") else "—"
        cat_key = a.get("category", "analysis")
        cat_color_class = {
            "analysis": "cat-analysis",
            "alert":    "cat-alert",
            "warn":     "cat-warn",
            "win":      "cat-win",
            "guide":    "cat-guide",
        }.get(cat_key, "cat-analysis")
        grid_html_parts.append(f'''            <a href="{a_url}" class="news-card">
                <div class="news-card-img {cat_color_class}">
                    <span class="news-cat-badge">{a.get("category_label", "")}</span>
                    <i class="fas {a.get("category_icon", "fa-newspaper")}"></i>
                </div>
                <div class="news-card-body">
                    <h4>{a["title"]}</h4>
                    <p>{a["excerpt"]}</p>
                    <div class="news-meta">
                        <span><i class="far fa-calendar"></i> {fmt_date(a["date"])}</span>
                        <span><i class="far fa-eye"></i> {a_views}</span>
                    </div>
                </div>
            </a>''')
    grid_html = "\n".join(grid_html_parts)

    # Combine
    return f'''        <div class="news-layout reveal">
{featured_html}
            <!-- Side List (latest 4 compact items) -->
            <div class="news-list">
{side_html}
            </div>
        </div>

        <!-- More Articles Grid -->
        <div class="news-grid reveal">
{grid_html}
        </div>'''


def render_archive_cards(articles: list[dict[str, Any]]) -> str:
    """把 articles 列表渲染成归档页卡片列表。"""
    cards = []
    for a in articles:
        a_url = f"{a['date']}-{a['slug']}.html"
        a_views = f"{a.get('views', 0):,}" if a.get("views") else "—"
        cat_class = {
            "analysis": "cat-analysis",
            "alert":    "cat-alert",
            "warn":     "cat-warn",
            "win":      "cat-win",
            "guide":    "cat-guide",
        }.get(a.get("category", "analysis"), "cat-analysis")
        hot_badge = '<span style="font-size:var(--text-xs);color:var(--danger);font-weight:700;"><i class="fas fa-fire"></i> HOT</span>' if a.get("hot") else ""
        cards.append(f'''    <a href="{a_url}" class="archive-card">
        <div class="archive-card-header">
            <span class="article-cat {cat_class}"><i class="fas {a.get('category_icon', 'fa-newspaper')}"></i> {a.get('category_label', '')}</span>
            {hot_badge}
        </div>
        <div class="archive-card-body">
            <h3>{a["title"]}</h3>
            <p>{a["excerpt"]}</p>
            <div class="archive-card-meta">
                <span><i class="far fa-calendar"></i> {a["date"]}</span>
                <span><i class="far fa-clock"></i> {a.get("read_time", "5分钟")}</span>
                <span><i class="far fa-eye"></i> {a_views}</span>
                <span><i class="fas fa-user-tie"></i> {a.get("author", "稻草人")}</span>
            </div>
        </div>
    </a>''')
    return "\n\n".join(cards)


def replace_between_markers(content: str, start: str, end: str, new_body: str) -> str:
    """把 content 中 start...end 之间的内容替换为 new_body。"""
    pattern = re.compile(
        re.escape(start) + r".*?" + re.escape(end),
        flags=re.S,
    )
    replacement = start + "\n" + new_body + "\n        " + end
    result, count = pattern.subn(replacement, content)
    if count == 0:
        raise RuntimeError(f"未找到标记: {start} ... {end}")
    return result


def update_homepage(articles: list[dict[str, Any]]) -> None:
    """更新首页 index.html 的 ticker + news 区块。"""
    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        content = f.read()

    # 更新"最近更新"日期
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    content = re.sub(
        r'最近更新 \d{4}-\d{2}-\d{2}',
        f'最近更新 {today_str}',
        content,
    )

    # 更新跑马灯 ticker
    ticker_html = render_ticker(articles)
    content = replace_between_markers(
        content,
        "<!-- AUTO-TICKER-START · 此区块由 scripts/auto_publish.py 自动重新生成 -->",
        "<!-- AUTO-TICKER-END -->",
        ticker_html,
    )

    # 更新新闻卡片区
    new_block = render_homepage_news_block(articles)
    content = replace_between_markers(
        content,
        "<!-- AUTO-NEWS-START · 此区块由 scripts/auto_publish.py 自动重新生成，手动修改将被覆盖 -->",
        "<!-- AUTO-NEWS-END -->",
        new_block,
    )
    if not DRY_RUN:
        with open(INDEX_HTML, "w", encoding="utf-8") as f:
            f.write(content)


def update_archive(articles: list[dict[str, Any]]) -> None:
    """更新归档页。"""
    with open(ARCHIVE_HTML, "r", encoding="utf-8") as f:
        content = f.read()
    new_cards = render_archive_cards(articles)
    content = replace_between_markers(
        content,
        "<!-- AUTO-ARCHIVE-START · 此区块由 scripts/auto_publish.py 自动重新生成，手动修改将被覆盖 -->",
        "<!-- AUTO-ARCHIVE-END -->",
        new_cards,
    )
    if not DRY_RUN:
        with open(ARCHIVE_HTML, "w", encoding="utf-8") as f:
            f.write(content)


# ==================== 主流程 ====================

def main() -> int:
    # 校验当前 provider 对应的 API Key
    if LLM_PROVIDER == "deepseek":
        if not DEEPSEEK_API_KEY:
            print("[error] LLM_PROVIDER=deepseek 但缺少 DEEPSEEK_API_KEY 环境变量", file=sys.stderr)
            return 1
        current_model = DEEPSEEK_MODEL
    elif LLM_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            print("[error] LLM_PROVIDER=gemini 但缺少 GEMINI_API_KEY 环境变量", file=sys.stderr)
            return 1
        current_model = GEMINI_MODEL
    elif LLM_PROVIDER == "claude":
        if not ANTHROPIC_API_KEY:
            print("[error] LLM_PROVIDER=claude 但缺少 ANTHROPIC_API_KEY 环境变量", file=sys.stderr)
            return 1
        current_model = CLAUDE_MODEL
    else:
        print(
            f"[error] 未知的 LLM_PROVIDER: {LLM_PROVIDER!r}"
            f"（必须是 'deepseek'、'gemini' 或 'claude'）",
            file=sys.stderr,
        )
        return 1

    print(
        f"[start] provider={LLM_PROVIDER} model={current_model} "
        f"DRY_RUN={DRY_RUN} UTC={datetime.now(timezone.utc).isoformat()}"
    )

    # 1. 加载已有文章列表
    data = load_articles_json()
    articles = data["articles"]

    # 2. 抓案件
    print("[step 1] 查询 CourtListener 最近 7 天案件...")
    cases = []
    try:
        raw_cases = search_courtlistener(days_back=7)
        print(f"  获得 {len(raw_cases)} 条原始案件")
        ranked = rank_cases(raw_cases)
        # 过滤已发布
        cases = [c for c in ranked if not is_case_already_published(c, articles)]
        print(f"  去重后剩余 {len(cases)} 条可写")
    except Exception as e:
        print(f"[warn] CourtListener 查询失败（将降级到保底选题）: {e}", file=sys.stderr)

    # 3. 选题 & 生成文章
    if cases:
        top_case = cases[0]
        print(f"[step 2] 选中案件: {top_case['docket_number']} - {top_case['case_name'][:80]}")
        article = generate_case_article(top_case)
    else:
        # 从未用过的 evergreen topic 里挑
        used_themes = {(a.get("tags") or [""])[0] for a in articles if a.get("source") == "auto"}
        pool = [t for t in EVERGREEN_TOPICS if t["theme"] not in used_themes] or EVERGREEN_TOPICS
        # 按日期循环挑选
        idx = datetime.now(timezone.utc).toordinal() % len(pool)
        topic = pool[idx]
        print(f"[step 2] 无新案件，选择保底选题: {topic['theme']}")
        article = generate_evergreen_article(topic)

    meta = article["meta"]
    html = article["html"]

    # 4. 生成 slug + 文件名
    if "case_no" in meta and meta["case_no"]:
        slug = case_to_slug({"matched_brand": "", "docket_number": meta["case_no"]})
    else:
        slug = slugify(meta["title"], max_len=30)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = NEWS_DIR / f"{today}-{slug}.html"

    # 如果当天已有同名文件，加后缀
    if filename.exists():
        filename = NEWS_DIR / f"{today}-{slug}-{datetime.now(timezone.utc).strftime('%H%M')}.html"

    print(f"[step 3] 写入文章: {filename.relative_to(REPO_ROOT)}")
    if not DRY_RUN:
        filename.write_text(html, encoding="utf-8")

    # 5. 更新 articles.json
    new_entry = {
        "date": today,
        "slug": filename.stem.split("-", 3)[-1] if filename.stem.count("-") >= 3 else slug,
        "title": meta["title"],
        "category": meta.get("category", "analysis"),
        "category_label": meta.get("category_label", "深度分析"),
        "category_icon": meta.get("category_icon", "fa-gavel"),
        "excerpt": meta["excerpt"],
        "read_time": meta.get("read_time", "5分钟"),
        "views": 0,
        "author": meta.get("author", "稻草人研究部"),
        "hot": False,
        "tags": meta.get("tags", []),
        "source": "auto",
    }
    if meta.get("case_no"):
        new_entry["case_no"] = meta["case_no"]

    articles.insert(0, new_entry)
    data["articles"] = articles
    if not DRY_RUN:
        save_articles_json(data)

    # 6. 重渲染首页 + 归档页
    print("[step 4] 重渲染首页 + 归档页...")
    update_homepage(articles)
    update_archive(articles)

    print(f"[done] ✅ 新文章: {new_entry['title']}")
    print(f"       URL: https://trolawyer.site/news/{today}-{new_entry['slug']}.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
