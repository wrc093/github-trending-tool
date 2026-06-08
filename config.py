import os
from dotenv import load_dotenv

load_dotenv()


# ---- 飞书 ----
FEISHU_WEBHOOK_URL: str = os.getenv("FEISHU_WEBHOOK_URL", "")
FEISHU_SECRET: str = os.getenv("FEISHU_SECRET", "")
FEISHU_APP_ID: str = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET: str = os.getenv("FEISHU_APP_SECRET", "")

# ---- LLM ----
LLM_ENABLED: bool = os.getenv("LLM_ENABLED", "false").lower() in ("true", "1", "yes")
LLM_API_BASE: str = os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")

# ---- Trending ----
TRENDING_LANGUAGE: str = os.getenv("TRENDING_LANGUAGE", "")
TRENDING_TOP_N: int = int(os.getenv("TRENDING_TOP_N", "25"))
TRENDING_TIMEOUT: int = int(os.getenv("TRENDING_TIMEOUT", "30"))

# ---- 仓库信息（用于飞书消息中的下载链接）----
REPO_URL: str = os.getenv("REPO_URL", "")
