"""项目概括模块 — 为 Top 10 项目生成详细的中文概括 + 自定义标签"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional

import requests

from src.scraper import Repo

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/plain, text/html, application/json, */*",
}


# ── 自定义标签定义 ──────────────────────────────
# 格式：(key, 中文标签, emoji)
TAG_DEFINITIONS: list[tuple[str, str, str]] = [
    ("agent",        "Agent",        "🤖"),
    ("memory",       "Memory",       "🧠"),
    ("llm",          "LLM",          "💬"),
    ("frontend",     "Frontend",     "🎨"),
    ("devtool",      "DevTool",      "🔧"),
    ("framework",    "Framework",    "🏗️"),
    ("security",     "Security",     "🔒"),
    ("data",         "Data/ML",      "📊"),
    ("infra",        "Infra",        "🌐"),
    ("language",     "Language",     "📝"),
    ("productivity", "Productivity", "⚡"),
    ("ocr",          "OCR",          "👁️"),
    ("voice",        "Voice",        "🎤"),
    ("search",       "Search",       "🔍"),
    ("multimedia",   "Multimedia",   "🎬"),
    ("career",       "Career",       "💼"),
    ("harness",      "Harness",      "🎯"),
    ("plugin",       "Plugin",       "🔌"),
    ("notebook",     "Notebook",     "📓"),
    ("copilot",      "Copilot",      "🧑‍💻"),
]

# key → (中文, emoji) 快速索引
_TAG_MAP: dict[str, tuple[str, str]] = {k: (cn, em) for k, cn, em in TAG_DEFINITIONS}


@dataclass
class ProjectSummary:
    """单个项目的概括结果"""
    repo_name: str
    summary: str            # 3–5 句详细描述
    tags: list[str] = field(default_factory=list)   # 标签 key 列表


class ProjectSummarizer:
    """为 GitHub 项目生成详细概括 + 自定义标签"""

    def __init__(self, use_llm: bool = False, llm_api_key: Optional[str] = None):
        self.use_llm = use_llm
        self.llm_api_key = llm_api_key
        self.timeout = 15

    # ── README 获取 ──────────────────────────────

    def get_readme_content(self, repo: Repo) -> str:
        """获取项目的 README 内容（最多 2000 字符）"""
        api_url = f"https://api.github.com/repos/{repo.name}/readme"
        try:
            resp = requests.get(
                api_url,
                headers={**HEADERS, "Accept": "application/vnd.github.v3.raw"},
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                return resp.text[:2000]
        except Exception as e:
            logger.debug(f"获取 README 失败 {repo.name}: {e}")

        # 降级：直接访问 GitHub 页面
        try:
            resp = requests.get(repo.url, headers=HEADERS, timeout=self.timeout)
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                readme_div = soup.select_one("#readme, .readme-content, article")
                if readme_div:
                    return readme_div.get_text()[:1500]
        except Exception as e:
            logger.debug(f"获取页面失败 {repo.name}: {e}")

        return ""

    # ── 标签推断 ─────────────────────────────────

    @staticmethod
    def _infer_tags(repo: Repo) -> list[str]:
        """基于 description / name / language 推断标签（使用词边界匹配避免误判）"""
        tags: list[str] = []
        text = ((repo.description or "") + " " + (repo.name or "")).lower()

        # 用词边界匹配短关键词，避免 "ui" 误匹配 "building" 等
        def _match(keywords: list[str]) -> bool:
            for kw in keywords:
                # 短关键词（<=3 字符）用词边界匹配
                if len(kw) <= 3:
                    if re.search(r'\b' + re.escape(kw) + r'\b', text):
                        return True
                else:
                    if kw in text:
                        return True
            return False

        rules: list[tuple[list[str], str]] = [
            (["agent", "agents", "agentic"],                          "agent"),
            (["memory", "mempalace", "remember", "knowledge"],        "memory"),
            (["llm", "gpt", "chat", "claude", "openai", "anthropic"],"llm"),
            (["copilot", "code gen", "vibe coding"],                  "copilot"),
            (["react", "angular", "vue", "svelte", "frontend",
              "ui", "generative ui", "css", "web component"],         "frontend"),
            (["notebook", "notebooklm", "jupyter"],                   "notebook"),
            (["cli", "devtool", "dev tool", "developer tool",
              "build", "debug", "lint"],                              "devtool"),
            (["framework", "library", "sdk", "toolkit"],              "framework"),
            (["security", "vuln", "scan", "trivy", "cve"],            "security"),
            (["data", "train", "deep learning",
              "neural", "nlp", "embedding"],                          "data"),
            (["ml", "machine learning", "model"],                     "data"),
            (["infra", "server", "nginx", "kubernetes", "docker",
              "deploy", "cloud"],                                     "infra"),
            (["golang", "rust", "compiler", "runtime"],               "language"),
            (["ocr", "image", "vision", "photo", "video"],            "ocr"),
            (["voice", "audio", "speech", "whisper", "tts",
              "sound"],                                               "voice"),
            (["search", "crawl", "scrape", "spider", "fetch"],        "search"),
            (["plugin", "extension", "addon", "plugins"],             "plugin"),
            (["career", "job", "resume", "hire", "interview"],        "career"),
            (["skill", "harness", "superpowers"],                     "harness"),
            (["productivity", "todo", "task", "workflow",
              "automate"],                                            "productivity"),
            (["multimedia", "media", "ffmpeg", "stream"],             "multimedia"),
        ]

        for keywords, tag in rules:
            if _match(keywords):
                if tag not in tags:
                    tags.append(tag)

        return tags[:5]   # 最多 5 个

    # ── 简单模式 ─────────────────────────────────

    def _simple_summary(self, repo: Repo) -> ProjectSummary:
        """基于现有信息 + 关键词规则生成概括（LLM 不可用时的降级方案）"""
        tags = self._infer_tags(repo)
        parts: list[str] = []

        # 热度描述
        if repo.today_stars > 500:
            parts.append(f"今日爆火，单日新增 {repo.today_stars} 颗 Star")
        elif repo.today_stars > 200:
            parts.append(f"今日非常热门，新增 {repo.today_stars} 颗 Star")
        elif repo.today_stars > 50:
            parts.append(f"今日热门，新增 {repo.today_stars} 颗 Star")

        # 项目描述
        if repo.description:
            parts.append(repo.description)

        # 标签中文说明
        if tags:
            tag_desc = "、".join(
                f"{_TAG_MAP[t][1]} {_TAG_MAP[t][0]}" for t in tags if t in _TAG_MAP
            )
            if tag_desc:
                parts.append(f"涉及领域：{tag_desc}")

        # 编程语言 & 规模
        if repo.language:
            size_note = ""
            if repo.stars > 100000:
                size_note = "，是 GitHub 上的超级明星项目"
            elif repo.stars > 50000:
                size_note = "，已是广为人知的知名项目"
            elif repo.stars > 10000:
                size_note = "，拥有成熟的社区生态"
            parts.append(f"使用 {repo.language} 开发{size_note}")

        summary = "。".join(parts) + "。" if parts else "GitHub 开源项目。"
        return ProjectSummary(repo_name=repo.name, summary=summary, tags=tags)

    # ── LLM 模式 ─────────────────────────────────

    def _llm_summary(self, repo: Repo) -> ProjectSummary:
        """使用 LLM 生成详细概括 + 标签"""
        try:
            import config
            import openai
            client = openai.OpenAI(
                api_key=self.llm_api_key or config.LLM_API_KEY,
                base_url=config.LLM_API_BASE,
            )

            readme = self.get_readme_content(repo)

            tag_list_str = ", ".join(k for k, _, _ in TAG_DEFINITIONS)

            prompt = f"""你是一位 GitHub 项目分析师。请根据以下信息，为这个项目写一段详细的中文概括。

要求：
1. 用 3-5 句话说明：这个项目是做什么的、解决了什么问题、适合什么场景/人群、为什么值得关注
2. 从以下标签中选择 2-4 个最合适的标签：
   {tag_list_str}
3. 以严格 JSON 格式返回，不要包含任何其他文字：
   {{"summary": "你的详细概括", "tags": ["tag1", "tag2"]}}

项目信息：
- 名称：{repo.name}
- 描述：{repo.description or '无'}
- 语言：{repo.language}
- Stars：{repo.stars:,}（今日 +{repo.today_stars:,}）
- README 摘要：
{readme[:1200] if readme else '无'}"""

            response = client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.3,
            )

            raw = response.choices[0].message.content.strip()
            return self._parse_llm_response(repo, raw)

        except Exception as e:
            logger.warning(f"LLM 概括失败 {repo.name}: {e}")
            return self._simple_summary(repo)

    @staticmethod
    def _parse_llm_response(repo: Repo, text: str) -> ProjectSummary:
        """解析 LLM 返回的 JSON"""
        # 尝试直接解析
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # 尝试从 ```json ... ``` 中提取
            import re
            m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
            if m:
                data = json.loads(m.group(1).strip())
            else:
                raise ValueError(f"无法解析 LLM 返回: {text[:200]}")

        summary = data.get("summary", "").strip()
        tags = [t for t in data.get("tags", []) if t in _TAG_MAP]

        if not summary:
            raise ValueError("LLM 返回空 summary")

        return ProjectSummary(repo_name=repo.name, summary=summary, tags=tags)

    # ── 批量入口 ─────────────────────────────────

    def generate_summary(self, repo: Repo) -> ProjectSummary:
        """为单个项目生成概括"""
        if self.use_llm and self.llm_api_key:
            return self._llm_summary(repo)
        return self._simple_summary(repo)

    def summarize_top_repos(self, repos: list[Repo], top_n: int = 10) -> list[ProjectSummary]:
        """为 Top N 项目生成概括，按榜单排名顺序返回"""
        results: list[ProjectSummary] = []
        top_repos = repos[:top_n]

        for i, repo in enumerate(top_repos, 1):
            logger.info(f"正在生成概括 ({i}/{len(top_repos)}): {repo.name}")
            ps = self.generate_summary(repo)
            results.append(ps)
            if i < len(top_repos):
                time.sleep(0.5)

        return results
