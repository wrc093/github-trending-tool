"""总结器模块 — 支持纯模板和 LLM 两种模式"""

import logging
from collections import Counter
from typing import Optional, Union

import config
from src.scraper import Repo

logger = logging.getLogger(__name__)


class TemplateSummarizer:
    """基于模板的纯文本总结器（无需 LLM）"""

    def __init__(self, top_n: Optional[int] = None):
        self.top_n = top_n or config.TRENDING_TOP_N

    def summarize(self, repos: list[Repo], date: str = "") -> str:
        """生成模板摘要"""
        if not repos:
            return "今日 GitHub Trending 暂无数据。"

        top = repos[:self.top_n]
        language = config.TRENDING_LANGUAGE or "全部"

        # 语言统计
        lang_counter = Counter(r.language for r in repos if r.language != "Unknown")
        lang_summary = ", ".join(f"{lang} ({count})" for lang, count in lang_counter.most_common(5))

        # 按今日 Stars 排序的亮点项目
        top_by_today = sorted(repos, key=lambda r: r.today_stars, reverse=True)[:5]
        highlights = "\n".join(
            f"  🔥 {r.name} (+{r.today_stars}⭐ 今天 | ⭐{r.stars})\n"
            f"     {r.description[:100]}" if r.description else
            f"  🔥 {r.name} (+{r.today_stars}⭐ 今天 | ⭐{r.stars})"
            for r in top_by_today
        )

        # Top 仓库列表
        repo_list = "\n".join(
            f"  {i}. {r.name} - {r.language} - ⭐{r.stars} (+{r.today_stars})"
            for i, r in enumerate(top, 1)
        )

        summary = (
            f"📊 GitHub Trending 日报 ({date})\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📌 榜单：{language} | 共 {len(repos)} 个项目\n"
            f"📈 语言分布：{lang_summary}\n"
            f"\n🔥 今日热点 Top 5:\n{highlights}\n"
            f"\n📋 完整 Top {self.top_n}:\n{repo_list}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🤖 by github-trending-tool"
        )
        return summary


class LLMSummarizer:
    """基于 LLM 的智能总结器（需要配置 API Key）"""

    SYSTEM_PROMPT = (
        "你是一个 GitHub 开源趋势分析师。根据用户提供的 GitHub Trending 仓库数据，"
        "生成一份简洁、有洞察的中文日报。要求：\n"
        "1. 开头用一句话总结今日趋势主题\n"
        "2. 列出 3-5 个最值得关注的亮点项目，简要说明为什么值得关注\n"
        "3. 给出语言分布的简要分析\n"
        "4. 结尾用一句话给出今日建议（值得关注什么方向）\n"
        "保持简洁，总字数控制在 500 字以内。"
    )

    def __init__(self, top_n: Optional[int] = None):
        if not config.LLM_API_KEY:
            raise ValueError("LLM 模式需要配置 LLM_API_KEY")

        from openai import OpenAI
        self.client = OpenAI(
            api_key=config.LLM_API_KEY,
            base_url=config.LLM_API_BASE,
        )
        self.model = config.LLM_MODEL
        self.top_n = top_n or config.TRENDING_TOP_N

    def summarize(self, repos: list[Repo], date: str = "") -> str:
        """调用 LLM 生成智能摘要，失败时降级为模板模式"""
        try:
            return self._llm_summarize(repos, date)
        except Exception as e:
            logger.warning(f"LLM 总结失败，降级为模板模式: {e}")
            template = TemplateSummarizer(top_n=self.top_n)
            return template.summarize(repos, date)

    def _llm_summarize(self, repos: list[Repo], date: str = "") -> str:
        """实际调用 LLM"""
        top = repos[:self.top_n]

        # 构建 prompt 数据
        repo_data = "\n".join(
            f"- {r.name} | {r.language} | ⭐{r.stars} (+{r.today_stars}) | {r.description}"
            for r in top
        )

        user_prompt = (
            f"以下是 {date} 的 GitHub Trending 数据（共 {len(repos)} 个项目，取 Top {self.top_n}）：\n\n"
            f"{repo_data}\n\n"
            f"请生成今日趋势日报。"
        )

        logger.info("正在调用 LLM (%s) 生成总结...", self.model)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=1024,
        )

        result = response.choices[0].message.content.strip()
        logger.info("LLM 总结生成完成")
        return f"📊 GitHub Trending 智能日报 ({date})\n━━━━━━━━━━━━━━━━━━\n\n{result}\n\n━━━━━━━━━━━━━━━━━━\n🤖 by github-trending-tool"


def create_summarizer() -> Union[TemplateSummarizer, LLMSummarizer]:
    """工厂函数：根据配置返回合适的总结器。LLM 初始化失败时降级为模板模式"""
    if config.LLM_ENABLED:
        try:
            return LLMSummarizer()
        except Exception as e:
            logger.warning("LLM 初始化失败，降级为模板模式: %s", e)
    return TemplateSummarizer()
