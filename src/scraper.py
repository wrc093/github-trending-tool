"""GitHub Trending 爬虫模块"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup

import config

logger = logging.getLogger(__name__)

TRENDING_URL = "https://github.com/trending"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass
class Repo:
    """GitHub Trending 仓库数据"""
    rank: int
    name: str              # owner/repo
    url: str
    description: str
    language: str
    stars: int
    forks: int
    today_stars: int       # 今日新增 Stars
    built_by: list[str] = field(default_factory=list)  # 贡献者头像 URL


class GitHubTrendingScraper:
    """GitHub Trending 页面爬虫"""

    def __init__(self, language: Optional[str] = None):
        self.language = language or config.TRENDING_LANGUAGE
        self.timeout = config.TRENDING_TIMEOUT

    def _build_url(self) -> str:
        if self.language:
            return f"{TRENDING_URL}/{self.language}"
        return TRENDING_URL

    def _parse_int(self, text: str) -> int:
        """解析 '1,234' 格式的数字字符串"""
        return int(text.replace(",", "").strip()) if text.strip() else 0

    def _parse_stars_total(self, link_text: str) -> int:
        """从 'xxx stars today' 或纯数字中提取总 Stars"""
        # 链接文本通常只包含总星数，格式如 "1,234"
        return self._parse_int(link_text)

    def scrape(self) -> list[Repo]:
        """爬取 GitHub Trending 页面，返回仓库列表"""
        url = self._build_url()
        logger.info("正在爬取: %s", url)

        resp = requests.get(url, headers=HEADERS, timeout=self.timeout)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.select("article.Box-row")

        repos: list[Repo] = []
        for idx, article in enumerate(articles, start=1):
            try:
                repo = self._parse_article(article, idx)
                repos.append(repo)
            except Exception as e:
                logger.warning("解析第 %d 个仓库失败: %s", idx, e)
                continue

            # 适当延迟，避免触发 GitHub 限流
            if idx % 10 == 0:
                time.sleep(0.5)

        logger.info("成功爬取 %d 个仓库", len(repos))
        return repos

    def _parse_article(self, article, rank: int) -> Repo:
        """解析单个 article 标签"""
        # 仓库名称和 URL
        h2 = article.select_one("h2")
        a_tag = h2.select_one("a") if h2 else None
        href = a_tag["href"].strip() if a_tag else ""
        name = href.lstrip("/")  # /owner/repo -> owner/repo

        # 描述
        p_tag = article.select_one("p")
        description = p_tag.get_text(strip=True) if p_tag else ""

        # 语言
        lang_span = article.select_one("[itemprop='programmingLanguage']")
        language = lang_span.get_text(strip=True) if lang_span else "Unknown"

        # Stars 和 Forks（在最后的 span 组中）
        links = article.select("a.Link--muted")
        stars = 0
        forks = 0
        for link in links:
            href_val = link.get("href", "")
            text = link.get_text(strip=True)
            if "/stargazers" in href_val:
                stars = self._parse_int(text)
            elif "/forks" in href_val:
                forks = self._parse_int(text)

        # 今日 Stars
        today_span = article.select_one("span.d-inline-block.float-sm-right")
        today_stars = 0
        if today_span:
            today_text = today_span.get_text(strip=True)
            # 格式: "xxx stars today"
            import re
            match = re.search(r"([\d,]+)", today_text)
            if match:
                today_stars = self._parse_int(match.group(1))

        # 贡献者头像
        built_by = []
        avatars = article.select("a img[src*='avatars']")
        for img in avatars:
            avatar_url = img.get("src", "")
            if avatar_url:
                built_by.append(avatar_url)

        return Repo(
            rank=rank,
            name=name,
            url=f"https://github.com{name}" if name.startswith("/") else f"https://github.com/{name}",
            description=description,
            language=language,
            stars=stars,
            forks=forks,
            today_stars=today_stars,
            built_by=built_by,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scraper = GitHubTrendingScraper()
    repos = scraper.scrape()
    for repo in repos[:5]:
        print(f"#{repo.rank} {repo.name} - {repo.stars} (+{repo.today_stars} today)")
        print(f"   {repo.description[:80]}")
        print()
