"""导出模块 — 生成 Markdown / HTML / PDF 三份产物"""

import html as _html
import logging
import os
import sys
import tempfile
from collections import Counter
from typing import Optional, Tuple

# ── WeasyPrint macOS 库路径修复 ─
# 在导入 weasyprint 之前设置 DYLD_FALLBACK_LIBRARY_PATH
_MACOS = sys.platform == "darwin"
if _MACOS:
    _dylib_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".dylib")
    _hb_dir = "/opt/homebrew/lib"
    _existing = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    _paths = [p for p in [_dylib_dir, _hb_dir] if p and os.path.isdir(p)]
    if _paths:
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = ":".join(_paths + [_existing]) if _existing else ":".join(_paths)

from src.scraper import Repo
from src.project_summarizer import ProjectSummary

logger = logging.getLogger(__name__)

# ── macOS 系统字体目录 ─
_MACOS_FONT_DIRS = [
    "/System/Library/Fonts",
    "/System/Library/Fonts/Supplemental",
    "/Library/Fonts",
    os.path.expanduser("~/Library/Fonts"),
]

# 候选中文字体（按优先级排序）
_CJK_FONT_CANDIDATES = [
    ("/System/Library/Fonts/PingFang.ttc", "PingFang SC"),
    ("/System/Library/Fonts/Supplemental/STHeiti Light.ttc", "STHeiti Light"),
    ("/System/Library/Fonts/Supplemental/STHeiti Medium.ttc", "STHeiti Medium"),
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", "Hiragino Sans GB"),
    ("/Library/Fonts/Arial Unicode.ttf", "Arial Unicode MS"),
]

# ── 标签颜色定义 (bg_color, text_color) ──
_TAG_COLORS: dict[str, tuple[str, str]] = {
    "agent":        ("#ddf4ff", "#0969da"),
    "memory":       ("#fbefff", "#8250df"),
    "llm":          ("#fff8c5", "#9a6700"),
    "frontend":     ("#fff0f0", "#cf222e"),
    "devtool":      ("#dafbe1", "#116329"),
    "framework":    ("#ddf4ff", "#0550ae"),
    "security":     ("#ffebe9", "#bc4c00"),
    "data":         ("#ddf4ff", "#0969da"),
    "infra":        ("#f6f8fa", "#59636e"),
    "language":     ("#f6f8fa", "#59636e"),
    "productivity": ("#fff8c5", "#9a6700"),
    "ocr":          ("#fbefff", "#8250df"),
    "voice":        ("#fff0f0", "#cf222e"),
    "search":       ("#dafbe1", "#116329"),
    "multimedia":   ("#fff8c5", "#9a6700"),
    "career":       ("#ddf4ff", "#0550ae"),
    "harness":      ("#fbefff", "#8250df"),
    "plugin":       ("#dafbe1", "#116329"),
    "notebook":     ("#ddf4ff", "#0969da"),
    "copilot":      ("#dafbe1", "#116329"),
}

_TAG_MAP_FOR_EXPORT = {
    k: (cn, em) for k, cn, em in [
        ("agent", "Agent", "🤖"), ("memory", "Memory", "🧠"),
        ("llm", "LLM", "💬"), ("frontend", "Frontend", "🎨"),
        ("devtool", "DevTool", "🔧"), ("framework", "Framework", "🏗️"),
        ("security", "Security", "🔒"), ("data", "Data/ML", "📊"),
        ("infra", "Infra", "🌐"), ("language", "Language", "📝"),
        ("productivity", "Productivity", "⚡"), ("ocr", "OCR", "👁️"),
        ("voice", "Voice", "🎤"), ("search", "Search", "🔍"),
        ("multimedia", "Multimedia", "🎬"), ("career", "Career", "💼"),
        ("harness", "Harness", "🎯"), ("plugin", "Plugin", "🔌"),
        ("notebook", "Notebook", "📓"), ("copilot", "Copilot", "🧑‍💻"),
    ]
}


def _find_cjk_font() -> Optional[Tuple[str, str]]:
    """查找可用的中文字体，返回 (文件路径, 字体族名)"""
    for path, family in _CJK_FONT_CANDIDATES:
        if os.path.exists(path):
            return path, family
    return None


# ─────────────────────────────────────────────
#  工具函数
# ─────────────────────────────────────────────

def _get_summary_stats(repos: list[Repo]) -> dict:
    """提取摘要统计信息"""
    lang_counter = Counter(r.language for r in repos if r.language != "Unknown")
    top_lang = lang_counter.most_common(1)[0][0] if lang_counter else "-"
    total_today_stars = sum(r.today_stars for r in repos)
    top_today = max(repos, key=lambda r: r.today_stars) if repos else None
    return {
        "total": len(repos),
        "top_lang": top_lang,
        "total_today_stars": total_today_stars,
        "top_today": top_today,
        "lang_counter": lang_counter,
    }


def _ps_by_name(project_summaries: Optional[list[ProjectSummary]]) -> dict[str, ProjectSummary]:
    """将 ProjectSummary 列表转为 {repo_name: ProjectSummary} 索引"""
    if not project_summaries:
        return {}
    return {ps.repo_name: ps for ps in project_summaries}


# ─────────────────────────────────────────────
#  Markdown 生成
# ─────────────────────────────────────────────

def generate_markdown(repos: list[Repo], summary: str, date: str,
                      project_summaries: Optional[list[ProjectSummary]] = None) -> str:
    """生成 Markdown 内容"""
    stats = _get_summary_stats(repos)
    lang_dist = ", ".join(f"{lang} ({c})" for lang, c in stats["lang_counter"].most_common(5))

    lines = [
        "---",
        "title: GitHub Trending 日报",
        f"date: {date}",
        f"total_repos: {stats['total']}",
        f"top_language: {stats['top_lang']}",
        "---",
        "",
        f"# GitHub Trending 日报 ({date})",
        "",
        "## 📌 概览",
        "",
        "| 指标 | 值 |",
        "|------|-----|",
        f"| 上榜项目数 | {stats['total']} |",
        f"| 覆盖语言 | {lang_dist} |",
    ]
    if stats["top_today"]:
        lines.append(f"| 今日最热 | {stats['top_today'].name} (+{stats['top_today'].today_stars}⭐) |")
    lines.append("")

    if summary:
        lines += ["##  今日总结", "", summary, ""]

    # ── Top 10 项目概括（编号列表 + 标签）──
    if project_summaries:
        lines.append("## 🔟 Top 10 项目概括")
        lines.append("")
        ps_index = _ps_by_name(project_summaries)
        for i, repo in enumerate(repos[:10], 1):
            ps = ps_index.get(repo.name)
            if not ps:
                continue
            # 标签
            tag_str = ""
            if ps.tags:
                tag_str = " " + " ".join(
                    f"`{_TAG_MAP_FOR_EXPORT.get(t, (t, '❓'))[1]} {_TAG_MAP_FOR_EXPORT.get(t, (t, '❓'))[0]}`" for t in ps.tags
                )
            lines.append(f"### {i}. [{repo.name}]({repo.url}){tag_str}")
            lines.append("")
            lines.append(ps.summary)
            lines.append("")
            lines.append(f"> {repo.language} | ⭐ {repo.stars:,} | 📈 +{repo.today_stars:,} today | 🍴 {repo.forks}")
            lines.append("")

    top_by_today = sorted(repos, key=lambda r: r.today_stars, reverse=True)[:5]
    lines.append("## 🔥 今日热点 Top 5")
    lines.append("")
    for r in top_by_today:
        lines += [
            f"### {r.name} (+{r.today_stars}⭐ 今天 | {r.stars}⭐)",
            f"- **语言**: {r.language}",
            f"- **Forks**: {r.forks}",
            f"- **描述**: {r.description}",
        ]
        lines.append(f"- **链接**: {r.url}")
        lines.append("")

    lines.append("## 📋 完整榜单")
    lines.append("")
    lines.append("| # | 仓库 | 语言 | Stars | 今日新增 |")
    lines.append("|---|------|------|-------|----------|")
    for r in repos:
        lines.append(f"| {r.rank} | [{r.name}]({r.url}) | {r.language} | {r.stars:,} | +{r.today_stars:,} |")

    lines += ["", "---", "*Generated by github-trending-tool*", ""]
    return "\n".join(lines)


# ─────────────────────────────────────────────
#  精美 HTML 模板（GitHub 风格 + 现代设计）
# ─────────────────────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
{font_face_css}
  @page {{
    size: A4;
    margin: 0;
    @top-center {{
      content: "GitHub Trending 日报";
      font-family: "GHFont", "Helvetica Neue", Arial, sans-serif;
      font-size: 9px;
      color: #8b949e;
      padding: 8px 0;
    }}
    @bottom-center {{
      content: "第 " counter(page) " 页 / 共 " counter(pages) " 页";
      font-family: "GHFont", "Helvetica Neue", Arial, sans-serif;
      font-size: 9px;
      color: #8b949e;
      padding: 8px 0;
    }}
  }}

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    font-family: "GHFont", "Helvetica Neue", Arial, sans-serif;
    font-size: 11px;
    line-height: 1.6;
    color: #1f2328;
    background: #ffffff;
    padding: 20px 24px;
  }}

  /* ── 封面头部 ── */
  .cover {{
    background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #21262d 100%);
    color: #ffffff;
    padding: 32px 28px 28px;
    margin: -20px -24px 24px;
    position: relative;
    overflow: hidden;
  }}
  .cover::before {{
    content: "";
    position: absolute;
    top: -30px;
    right: -30px;
    width: 180px;
    height: 180px;
    background: radial-gradient(circle, rgba(88, 166, 255, 0.15) 0%, transparent 70%);
    border-radius: 50%;
  }}
  .cover::after {{
    content: "";
    position: absolute;
    bottom: -20px;
    left: 40%;
    width: 120px;
    height: 120px;
    background: radial-gradient(circle, rgba(63, 185, 80, 0.1) 0%, transparent 70%);
    border-radius: 50%;
  }}
  .cover .icon {{
    font-size: 28px;
    margin-bottom: 10px;
    display: block;
  }}
  .cover h1 {{
    font-size: 26px;
    font-weight: 700;
    letter-spacing: -0.5px;
    margin-bottom: 6px;
    position: relative;
    z-index: 1;
  }}
  .cover .subtitle {{
    font-size: 12px;
    color: #8b949e;
    font-weight: 400;
    position: relative;
    z-index: 1;
  }}
  .cover .badge {{
    display: inline-block;
    background: rgba(88, 166, 255, 0.2);
    color: #58a6ff;
    font-size: 10px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 12px;
    margin-top: 10px;
    position: relative;
    z-index: 1;
  }}

  /* ── 概览卡片 ── */
  .overview {{
    display: flex;
    gap: 12px;
    margin-bottom: 22px;
  }}
  .overview .card {{
    flex: 1;
    background: #f6f8fa;
    border: 1px solid #d0d7de;
    border-radius: 8px;
    padding: 14px 16px;
    position: relative;
  }}
  .overview .card::before {{
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    border-radius: 8px 8px 0 0;
  }}
  .overview .card:nth-child(1)::before {{ background: linear-gradient(90deg, #58a6ff, #79c0ff); }}
  .overview .card:nth-child(2)::before {{ background: linear-gradient(90deg, #3fb950, #56d364); }}
  .overview .card:nth-child(3)::before {{ background: linear-gradient(90deg, #f0883e, #ffa657); }}
  .overview .card .label {{
    font-size: 9px;
    color: #656d76;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    font-weight: 600;
  }}
  .overview .card .value {{
    font-size: 24px;
    font-weight: 700;
    color: #1f2328;
    margin-top: 4px;
    letter-spacing: -0.5px;
  }}
  .overview .card .sub {{
    font-size: 9px;
    color: #8b949e;
    margin-top: 2px;
  }}

  /* ── 标题 + 首个条目绑定（防止标题单独一页）── */
  .section-header {{
    page-break-inside: avoid;
  }}

  /* ── 章节标题 ── */
  .section-title {{
    font-size: 14px;
    font-weight: 700;
    color: #1f2328;
    margin: 20px 0 12px;
    padding-bottom: 8px;
    border-bottom: 2px solid #d0d7de;
    display: flex;
    align-items: center;
    gap: 8px;
    page-break-after: avoid;   /* 标题与紧随其后的第一个元素绑定在一起 */
  }}
  .section-title .emoji {{
    font-size: 16px;
  }}
  .section-title .accent {{
    display: inline-block;
    width: 3px;
    height: 16px;
    background: #0969da;
    border-radius: 2px;
  }}

  /* ── AI 总结 ── */
  .summary-box {{
    background: #f6f8fa;
    border-left: 4px solid #0969da;
    border-radius: 0 8px 8px 0;
    padding: 16px 20px;
    margin-bottom: 22px;
    white-space: pre-wrap;
    font-size: 11px;
    line-height: 1.8;
    color: #1f2328;
  }}

  /* ── Top 10 项目概括 ── */
  /* 不用 flex 容器包裹，让 .tp-item 作为普通 block 独立渲染，自然跨页 */
  .tp-item {{
    display: flex;
    gap: 14px;
    padding: 14px 16px;
    background: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 8px;
    margin-bottom: 10px;
    page-break-inside: avoid;
    transition: border-color 0.2s;
    page-break-inside: avoid;
  }}
  .tp-item:hover {{
    border-color: #0969da;
  }}
  .tp-item .tp-rank {{
    flex-shrink: 0;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: 700;
    border-radius: 8px;
    color: #ffffff;
    background: linear-gradient(135deg, #0969da, #388bfd);
  }}
  .tp-item:nth-child(1) .tp-rank {{ background: linear-gradient(135deg, #f0883e, #d29922); }}
  .tp-item:nth-child(2) .tp-rank {{ background: linear-gradient(135deg, #8b949e, #6e7681); }}
  .tp-item:nth-child(3) .tp-rank {{ background: linear-gradient(135deg, #a371f7, #8b5cf6); }}
  .tp-item .tp-content {{
    flex: 1;
    min-width: 0;
  }}
  .tp-item .tp-header {{
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 6px;
  }}
  .tp-item .tp-name {{
    font-size: 13px;
    font-weight: 600;
    color: #0969da;
    text-decoration: none;
  }}
  .tp-tag {{
    display: inline-block;
    font-size: 9px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 10px;
    line-height: 1.4;
  }}
  .tp-item .tp-summary {{
    font-size: 10.5px;
    color: #1f2328;
    line-height: 1.7;
    margin-bottom: 8px;
  }}
  .tp-item .tp-summary p {{
    margin: 0 0 6px 0;
  }}
  .tp-item .tp-summary p:last-child {{
    margin-bottom: 0;
  }}
  .tp-item .tp-meta {{
    font-size: 9px;
    color: #656d76;
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }}
  .tp-item .tp-meta .mtag {{
    display: inline-flex;
    align-items: center;
    gap: 3px;
    background: #f6f8fa;
    padding: 2px 8px;
    border-radius: 10px;
  }}
  .tp-item .tp-meta .mtag.stars {{ color: #9a6700; }}
  .tp-item .tp-meta .mtag.today {{ color: #1a7f37; font-weight: 600; }}

  /* ── Top 5 热点 ─ */
  .top-list {{
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-bottom: 22px;
  }}
  .top-item {{
    display: flex;
    gap: 14px;
    padding: 14px 16px;
    background: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 8px;
    transition: border-color 0.2s;
    page-break-inside: avoid;
  }}
  .top-item:hover {{
    border-color: #0969da;
  }}
  .top-item .rank {{
    flex-shrink: 0;
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    font-weight: 700;
    border-radius: 8px;
    color: #ffffff;
  }}
  .top-item:nth-child(1) .rank {{ background: linear-gradient(135deg, #f0883e, #d29922); }}
  .top-item:nth-child(2) .rank {{ background: linear-gradient(135deg, #8b949e, #6e7681); }}
  .top-item:nth-child(3) .rank {{ background: linear-gradient(135deg, #a371f7, #8b5cf6); }}
  .top-item:nth-child(n+4) .rank {{ background: linear-gradient(135deg, #0969da, #388bfd); }}
  .top-item .content {{
    flex: 1;
    min-width: 0;
  }}
  .top-item .name {{
    font-size: 13px;
    font-weight: 600;
    color: #0969da;
    text-decoration: none;
    display: block;
    margin-bottom: 3px;
  }}
  .top-item .meta {{
    font-size: 9px;
    color: #656d76;
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 5px;
  }}
  .top-item .meta .tag {{
    display: inline-flex;
    align-items: center;
    gap: 3px;
    background: #f6f8fa;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 9px;
  }}
  .top-item .meta .tag.stars {{ color: #9a6700; }}
  .top-item .meta .tag.today {{ color: #1a7f37; font-weight: 600; }}
  .top-item .desc {{
    font-size: 10px;
    color: #656d76;
    line-height: 1.5;
    overflow: hidden;
    text-overflow: ellipsis;
  }}

  /* ── 完整榜单表格 ── */
  .table-wrap {{
    border: 1px solid #d0d7de;
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 20px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 10px;
  }}
  thead {{
    background: #f6f8fa;
  }}
  th {{
    font-weight: 600;
    color: #656d76;
    text-align: left;
    padding: 8px 12px;
    border-bottom: 1px solid #d0d7de;
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  th:last-child, td:last-child {{ text-align: right; }}
  th:nth-child(4), td:nth-child(4) {{ text-align: right; }}
  td {{
    padding: 7px 12px;
    border-bottom: 1px solid #f0f0f0;
    color: #1f2328;
  }}
  tr:last-child td {{ border-bottom: none; }}
  tr:nth-child(even) {{ background: #fafbfc; }}
  tr:hover {{ background: #f6f8fa; }}
  td .repo-link {{
    color: #0969da;
    text-decoration: none;
    font-weight: 500;
  }}
  td .lang-badge {{
    display: inline-block;
    font-size: 9px;
    color: #656d76;
    background: #f6f8fa;
    padding: 1px 6px;
    border-radius: 3px;
  }}
  td .today-val {{
    color: #1a7f37;
    font-weight: 600;
  }}
  td .rank-num {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    background: #f6f8fa;
    border-radius: 4px;
    font-size: 9px;
    font-weight: 600;
    color: #656d76;
  }}
  tr:nth-child(1) td .rank-num {{ background: #fff8f0; color: #d29922; }}
  tr:nth-child(2) td .rank-num {{ background: #f6f8fa; color: #6e7681; }}
  tr:nth-child(3) td .rank-num {{ background: #f5f0ff; color: #8b5cf6; }}

  /* ── 页脚 ── */
  .footer {{
    margin-top: 24px;
    padding-top: 12px;
    border-top: 1px solid #d0d7de;
    text-align: center;
    font-size: 9px;
    color: #8b949e;
  }}
  .footer .heart {{ color: #f85149; }}
</style>
</head>
<body>
{body}
<div class="footer">Generated with <span class="heart">❤</span> by github-trending-tool &middot; {date}</div>
</body>
</html>
"""


def _render_summary_html(text: str) -> str:
    """将概括文本分段渲染为 HTML 段落"""
    # 按换行符或句号分段
    paragraphs = [p.strip() for p in text.replace('\n\n', '\n').split('\n') if p.strip()]
    if not paragraphs:
        return f'<p>{_html.escape(text)}</p>'
    return ''.join(f'<p>{_html.escape(p)}</p>' for p in paragraphs)


def _build_tag_html(tag: str) -> str:
    """生成单个标签的 HTML"""
    bg, fg = _TAG_COLORS.get(tag, ("#f6f8fa", "#59636e"))
    info = _TAG_MAP_FOR_EXPORT.get(tag)
    label = f"{info[0]} {info[1]}" if info else tag
    return f'<span class="tp-tag" style="background:{bg};color:{fg}">{_html.escape(label)}</span>'


def _build_html_body(repos: list[Repo], summary: str, date: str,
                     project_summaries: Optional[list[ProjectSummary]] = None) -> str:
    """构建 HTML body 内容"""
    stats = _get_summary_stats(repos)
    parts = []

    # ── 封面 ──
    parts.append(
        f'<div class="cover">'
        f'  <span class="icon"></span>'
        f'  <h1>GitHub Trending 日报</h1>'
        f'  <div class="subtitle">{date} &nbsp;·&nbsp; 共 {stats["total"]} 个开源项目登上今日热榜</div>'
        f'  <span class="badge">Daily Report</span>'
        f'</div>'
    )

    # ── 概览卡片 ──
    lang_dist = ", ".join(f"{lang}" for lang, _ in stats["lang_counter"].most_common(3))
    parts.append(
        '<div class="overview">'
        f'  <div class="card"><div class="label">上榜项目</div><div class="value">{stats["total"]}</div><div class="sub">今日热榜总数</div></div>'
        f'  <div class="card"><div class="label">最热语言</div><div class="value">{stats["top_lang"]}</div><div class="sub">{lang_dist}</div></div>'
        f'  <div class="card"><div class="label">今日新增 ⭐</div><div class="value">{stats["total_today_stars"]:,}</div><div class="sub">累计新增 Stars</div></div>'
        '</div>'
    )

    # ─ AI 总结 ──
    if summary:
        parts.append(
            f'<div class="section-header">'
            f'<div class="section-title"><span class="accent"></span> 今日总结</div>'
            f'<div class="summary-box">{_html.escape(summary)}</div>'
            f'</div>'
        )

    # ── Top 10 项目概括 ──
    if project_summaries:
        ps_index = _ps_by_name(project_summaries)
        valid = [(i, r, ps_index[r.name]) for i, r in enumerate(repos[:10], 1) if r.name in ps_index]
        if valid:
            # 标题 + 第一个条目绑定在一起（page-break-inside: avoid）
            i, repo, ps = valid[0]
            tags_html = "".join(_build_tag_html(t) for t in ps.tags)
            summary_html = _render_summary_html(ps.summary)
            parts.append(
                f'<div class="section-header">'
                f'<div class="section-title"><span class="accent"></span>🔟 Top 10 项目概括</div>'
                f'<div class="tp-item">'
                f'  <div class="tp-rank">{i}</div>'
                f'  <div class="tp-content">'
                f'    <div class="tp-header">'
                f'      <a class="tp-name" href="{repo.url}">{_html.escape(repo.name)}</a>'
                f'      {tags_html}'
                f'    </div>'
                f'    <div class="tp-summary">{summary_html}</div>'
                f'    <div class="tp-meta">'
                f'      <span class="mtag">{_html.escape(repo.language)}</span>'
                f'      <span class="mtag stars">⭐ {repo.stars:,}</span>'
                f'      <span class="mtag today">📈 +{repo.today_stars:,} 今天</span>'
                f'      <span class="mtag">🍴 {repo.forks}</span>'
                f'    </div>'
                f'  </div>'
                f'</div>'
                f'</div>'
            )
            # 剩余条目作为普通 block，自然跨页
            for i, repo, ps in valid[1:]:
                    tags_html = "".join(_build_tag_html(t) for t in ps.tags)
                    summary_html = _render_summary_html(ps.summary)
                    parts.append(
                        f'<div class="tp-item">'
                        f'  <div class="tp-rank">{i}</div>'
                        f'  <div class="tp-content">'
                        f'    <div class="tp-header">'
                        f'      <a class="tp-name" href="{repo.url}">{_html.escape(repo.name)}</a>'
                        f'      {tags_html}'
                        f'    </div>'
                        f'    <div class="tp-summary">{summary_html}</div>'
                        f'    <div class="tp-meta">'
                        f'      <span class="mtag">{_html.escape(repo.language)}</span>'
                        f'      <span class="mtag stars">⭐ {repo.stars:,}</span>'
                        f'      <span class="mtag today">📈 +{repo.today_stars:,} 今天</span>'
                        f'      <span class="mtag">🍴 {repo.forks}</span>'
                        f'    </div>'
                        f'  </div>'
                        f'</div>'
                    )

    # ─ Top 5 热点（按今日 star 排序）──
    top_by_today = sorted(repos, key=lambda r: r.today_stars, reverse=True)[:5]
    if top_by_today:
        # 标题 + 第一个条目绑定
        first = top_by_today[0]
        parts.append(
            f'<div class="section-header">'
            f'<div class="section-title"><span class="accent"></span>🔥 今日热点 Top 5</div>'
            f'<div class="top-item">'
            f'  <div class="rank">#{first.rank}</div>'
            f'  <div class="content">'
            f'    <a class="name" href="{first.url}">{first.name}</a>'
            f'    <div class="meta">'
            f'      <span class="tag">{first.language}</span>'
            f'      <span class="tag stars">⭐ {first.stars:,}</span>'
            f'      <span class="tag today">📈 +{first.today_stars:,} 今天</span>'
            f'      <span class="tag">🍴 {first.forks} forks</span>'
            f'    </div>'
            f'    <div class="desc">{first.description}</div>'
            f'  </div>'
            f'</div>'
            f'</div>'
        )
        for r in top_by_today[1:]:
                parts.append(
                    f'<div class="top-item">'
                    f'  <div class="rank">#{r.rank}</div>'
                    f'  <div class="content">'
                    f'    <a class="name" href="{r.url}">{r.name}</a>'
                    f'    <div class="meta">'
                    f'      <span class="tag">{r.language}</span>'
                    f'      <span class="tag stars">⭐ {r.stars:,}</span>'
                    f'      <span class="tag today">📈 +{r.today_stars:,} 今天</span>'
                    f'      <span class="tag">🍴 {r.forks} forks</span>'
                    f'    </div>'
                    f'    <div class="desc">{r.description}</div>'
                    f'  </div>'
                    f'</div>'
                )

    # ── 完整榜单表格 ──
    parts.append('<div class="section-title"><span class="accent"></span> 完整榜单</div>')
    rows = "\n".join(
        f'<tr>'
        f'<td><span class="rank-num">{r.rank}</span></td>'
        f'<td><a class="repo-link" href="{r.url}">{r.name}</a></td>'
        f'<td><span class="lang-badge">{r.language}</span></td>'
        f'<td>{r.stars:,}</td>'
        f'<td class="today-val">+{r.today_stars:,}</td>'
        f'</tr>'
        for r in repos
    )
    parts.append(
        '<div class="table-wrap"><table>'
        '<thead><tr><th>#</th><th>仓库</th><th>语言</th><th>Stars</th><th>今日</th></tr></thead>'
        f'<tbody>{rows}</tbody>'
        '</table></div>'
    )

    return "\n".join(parts)


def generate_html(repos: list[Repo], summary: str, date: str,
                  project_summaries: Optional[list[ProjectSummary]] = None) -> str:
    """生成带样式的 HTML 内容（自动注入 @font-face 确保字体嵌入 PDF）"""
    body = _build_html_body(repos, summary, date, project_summaries)

    # ── 注入 @font-face，指向单个字体文件（非 .ttc 集合），确保 WeasyPrint 嵌入字体 ─
    font_face_css = _build_font_face_css()

    return _HTML_TEMPLATE.format(
        title=f"GitHub Trending 日报 {date}",
        font_face_css=font_face_css,
        body=body,
        date=date,
    )


def _build_font_face_css() -> str:
    """
    构建 @font-face CSS，指向单个 .ttf/.otf 字体文件。
    WeasyPrint 无法处理 .ttc（TrueType Collection），必须用单个字体文件。
    文件路径用 urllib.parse.quote 做 URL 编码（处理空格等）。
    """
    from urllib.parse import quote

    # 优先找单个 .ttf/.otf 文件（非 .ttc）
    single_font_candidates = [
        # Ubuntu (GitHub Actions)
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        # macOS
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]

    for font_path in single_font_candidates:
        if os.path.isfile(font_path):
            encoded_path = quote(font_path, safe="/:")
            return f"""  @font-face {{
    font-family: "GHFont";
    src: url("file://{encoded_path}");
  }}
"""

    # 降级：尝试 .ttc（WeasyPrint 可能不支持，但聊胜于无）
    cjk_font = _find_cjk_font()
    if cjk_font:
        font_path, _ = cjk_font
        encoded_path = quote(font_path, safe="/:")
        logger.warning("未找到单个字体文件，降级使用 .ttc: %s", font_path)
        return f"""  @font-face {{
    font-family: "GHFont";
    src: url("file://{encoded_path}");
  }}
"""

    logger.warning("未找到可用的中文字体，PDF 中文可能显示异常")
    return ""


# ─────────────────────────────────────────────
#  PDF 生成（WeasyPrint + 精美模板）
# ─────────────────────────────────────────────

def _ensure_macos_fonts():
    """
    macOS 上 fontconfig 默认不扫描系统字体目录。
    调用 fc-cache 刷新字体缓存，让 WeasyPrint 能找到并嵌入中文字体。
    """
    font_dirs = [d for d in _MACOS_FONT_DIRS if os.path.isdir(d)]
    if not font_dirs:
        return

    try:
        import subprocess
        subprocess.run(
            ["fc-cache", "-f"] + font_dirs,
            capture_output=True, timeout=15,
        )
        logger.info("已刷新 fontconfig 缓存（%d 个字体目录）", len(font_dirs))
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning("fc-cache 不可用: %s，尝试 fontconfig XML 配置", e)
        # 降级：创建 fontconfig XML 配置
        existing = os.environ.get("FONTCONFIG_FILE", "")
        if existing and os.path.isfile(existing):
            return
        dir_elements = "\n    ".join(f'<dir>{d}</dir>' for d in font_dirs)
        config_xml = (
            '<?xml version="1.0"?>\n'
            '<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">\n'
            '<fontconfig>\n'
            f'    {dir_elements}\n'
            '    <cachedir>/tmp/fontconfig-cache</cachedir>\n'
            '</fontconfig>'
        )
        fd, config_path = tempfile.mkstemp(suffix=".conf", prefix="wp-fonts-")
        os.write(fd, config_xml.encode())
        os.close(fd)
        os.environ["FONTCONFIG_FILE"] = config_path
        logger.info("已创建 fontconfig 配置: %s", config_path)


def generate_pdf(repos: list[Repo], summary: str, date: str, output_path: str,
                 project_summaries: Optional[list[ProjectSummary]] = None) -> str:
    """使用 WeasyPrint 将 HTML 渲染为高质量 PDF"""
    from weasyprint import HTML

    html_content = generate_html(repos, summary, date, project_summaries)

    if _MACOS:
        _ensure_macos_fonts()

    HTML(string=html_content).write_pdf(output_path)
    return output_path


# ─────────────────────────────────────────────
#  统一导出
# ─────────────────────────────────────────────

OUTPUT_DIR_NAME = "output"


def export_all(repos: list[Repo], summary: str, date: str, base_dir: str = ".",
               project_summaries: Optional[list[ProjectSummary]] = None) -> dict[str, str]:
    """
    一次性生成 MD / HTML / PDF 三份文件。
    返回 { "md": path, "html": path, "pdf": path }
    """
    output_dir = os.path.join(base_dir, OUTPUT_DIR_NAME, date)
    os.makedirs(output_dir, exist_ok=True)

    filename = f"github-trending-{date}"

    # 1. Markdown
    md_path = os.path.join(output_dir, f"{filename}.md")
    md_content = generate_markdown(repos, summary, date, project_summaries)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    logger.info("Markdown 已保存: %s", md_path)

    # 2. HTML
    html_path = os.path.join(output_dir, f"{filename}.html")
    html_content = generate_html(repos, summary, date, project_summaries)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    logger.info("HTML 已保存: %s", html_path)

    # 3. PDF
    pdf_path = os.path.join(output_dir, f"{filename}.pdf")
    generate_pdf(repos, summary, date, pdf_path, project_summaries)
    logger.info("PDF 已保存: %s", pdf_path)

    return {"md": md_path, "html": html_path, "pdf": pdf_path}
