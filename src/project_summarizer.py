"""项目概括模块 — 为 Top 10 项目生成简洁的中文概括"""

import logging
import time
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


class ProjectSummarizer:
    """为 GitHub 项目生成简要概括"""

    def __init__(self, use_llm: bool = False, llm_api_key: Optional[str] = None):
        self.use_llm = use_llm
        self.llm_api_key = llm_api_key
        self.timeout = 10

    def get_readme_content(self, repo: Repo) -> str:
        """获取项目的 README 内容"""
        # 尝试通过 GitHub API 获取 README
        api_url = f"https://api.github.com/repos/{repo.name}/readme"
        try:
            resp = requests.get(api_url, headers={**HEADERS, "Accept": "application/vnd.github.v3.raw"}, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.text[:2000]  # 限制长度
        except Exception as e:
            logger.debug(f"获取 README 失败 {repo.name}: {e}")

        # 降级：尝试直接访问 GitHub 页面
        try:
            resp = requests.get(repo.url, headers=HEADERS, timeout=self.timeout)
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                # 提取 README 内容
                readme_div = soup.select_one("#readme, .readme-content, article")
                if readme_div:
                    return readme_div.get_text()[:1500]
        except Exception as e:
            logger.debug(f"获取页面失败 {repo.name}: {e}")

        return ""

    def generate_summary(self, repo: Repo) -> str:
        """为单个项目生成概括"""
        if self.use_llm and self.llm_api_key:
            return self._llm_summary(repo)
        else:
            return self._simple_summary(repo)

    def _simple_summary(self, repo: Repo) -> str:
        """基于现有信息生成简单概括"""
        parts = []

        # 项目类型
        if repo.language:
            parts.append(f"这是一个 {repo.language} 项目")

        # 热度
        if repo.today_stars > 500:
            parts.append("今日极度热门")
        elif repo.today_stars > 100:
            parts.append("今日非常热门")
        elif repo.today_stars > 50:
            parts.append("今日热门")

        # 总星数等级
        if repo.stars > 100000:
            parts.append("超级明星项目")
        elif repo.stars > 50000:
            parts.append("知名项目")
        elif repo.stars > 10000:
            parts.append("成熟项目")

        # 描述提取关键信息
        if repo.description:
            # 尝试提取关键词
            desc = repo.description.lower()
            if any(k in desc for k in ["ai", "llm", "gpt", "chat", "bot"]):
                parts.append("AI 相关")
            elif any(k in desc for k in ["web", "frontend", "react", "vue", "ui"]):
                parts.append("前端/ Web 相关")
            elif any(k in desc for k in ["data", "ml", "train", "model"]):
                parts.append("数据/机器学习相关")
            elif any(k in desc for k in ["dev", "tool", "cli", "build"]):
                parts.append("开发工具")

        return "，".join(parts) if parts else "GitHub 开源项目"

    def _llm_summary(self, repo: Repo) -> str:
        """使用 LLM 生成概括（需要 API Key）"""
        try:
            import openai
            import config
            client = openai.OpenAI(
                api_key=self.llm_api_key or config.LLM_API_KEY,
                base_url=config.LLM_API_BASE,
            )

            # 获取 README
            readme = self.get_readme_content(repo)

            prompt = f"""请用 1-2 句话简要概括这个 GitHub 项目：
项目名：{repo.name}
描述：{repo.description}
语言：{repo.language}
Stars: {repo.stars}

README 摘要：
{readme[:1000] if readme else '无'}

请用中文回答，简洁明了。"""

            response = client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.3,
            )

            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"LLM 概括失败 {repo.name}: {e}")
            return self._simple_summary(repo)

    def summarize_top_repos(self, repos: list[Repo], top_n: int = 10) -> dict[str, str]:
        """为 Top N 项目生成概括，返回 {repo_name: summary}"""
        summaries = {}
        top_repos = repos[:top_n]

        for i, repo in enumerate(top_repos, 1):
            logger.info(f"正在生成概括 ({i}/{len(top_repos)}): {repo.name}")
            summary = self.generate_summary(repo)
            summaries[repo.name] = summary

            # 避免请求过快
            if i < len(top_repos):
                time.sleep(0.5)

        return summaries
