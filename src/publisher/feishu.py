"""飞书 Webhook 发布器"""

import hashlib
import hmac
import base64
import json
import logging
import time

import requests

import config
from src.publisher.base import BasePublisher

logger = logging.getLogger(__name__)


class FeishuPublisher(BasePublisher):
    """通过飞书自定义机器人 Webhook 推送消息"""

    def __init__(self, webhook_url: str = "", secret: str = ""):
        self.webhook_url = webhook_url or config.FEISHU_WEBHOOK_URL
        self.secret = secret or config.FEISHU_SECRET

        if not self.webhook_url:
            raise ValueError("飞书 Webhook URL 未配置，请在 .env 中设置 FEISHU_WEBHOOK_URL")

    def _generate_sign(self, timestamp: str) -> str:
        """生成签名（飞书签名校验模式）"""
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        return base64.b64encode(hmac_code).decode("utf-8")

    def _build_payload(self, summary: str) -> dict:
        """构建消息体 — 使用富文本 (post) 格式"""
        # 将纯文本按行拆分为富文本段落
        lines = summary.split("\n")
        content = []
        for line in lines:
            content.append([{
                "tag": "text",
                "text": line + "\n",
            }])

        return {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": "GitHub Trending 日报",
                        "content": content,
                    }
                }
            },
        }

    def publish(self, summary: str) -> None:
        """发送消息到飞书，末尾附加 PDF 下载链接"""
        # 如果配置了仓库地址，追加下载链接
        if config.REPO_URL:
            summary = summary + f"\n\n PDF 下载：{config.REPO_URL}/actions"
        payload = self._build_payload(summary)

        # 签名校验
        if self.secret:
            timestamp = str(int(time.time()))
            payload["timestamp"] = timestamp
            payload["sign"] = self._generate_sign(timestamp)

        logger.info("正在发送消息到飞书...")
        resp = requests.post(
            self.webhook_url,
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()

        result = resp.json()
        if result.get("code") == 0 or result.get("StatusCode") == 0:
            logger.info("飞书消息发送成功")
        else:
            logger.error("飞书消息发送失败: %s", json.dumps(result, ensure_ascii=False))
            raise RuntimeError(f"飞书推送失败: {result}")
