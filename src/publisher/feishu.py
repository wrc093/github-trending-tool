"""飞书发布器 — 通过 Open API 发送 PDF 文件 + 文本摘要"""

import json
import logging
import os
import time

import requests

import config
from src.publisher.base import BasePublisher

logger = logging.getLogger(__name__)


class FeishuPublisher(BasePublisher):
    """通过飞书 Open API 推送消息"""

    def __init__(self, app_id: str = "", app_secret: str = ""):
        self.app_id = app_id or config.FEISHU_APP_ID
        self.app_secret = app_secret or config.FEISHU_APP_SECRET
        self._tenant_token: str = ""
        self._token_expires: float = 0

        if not self.app_id or not self.app_secret:
            raise ValueError("飞书 APP_ID 和 APP_SECRET 未配置，请在 .env 或 GitHub Secrets 中设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
            raise ValueError("飞书 Webhook URL 和 APP_ID 均未配置")

    # ── Open API 认证 ──────────────────────────────────

    def _get_tenant_token(self) -> str:
        """获取 tenant_access_token（自动缓存）"""
        if self._tenant_token and time.time() < self._token_expires - 60:
            return self._tenant_token

        resp = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取 tenant_access_token 失败: {data}")

        self._tenant_token = data["tenant_access_token"]
        self._token_expires = time.time() + data.get("expire", 7200)
        return self._tenant_token

    def _api_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_tenant_token()}"}

    # ── 文件上传 & 发送 ────────────────────────────────

    def _upload_file(self, file_path: str) -> str:
        """上传文件到飞书，返回 file_key"""
        resp = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/files",
            headers=self._api_headers(),
            files={
                "file": (os.path.basename(file_path), open(file_path, "rb"), "application/pdf"),
            },
            data={
                "file_type": "pdf",
                "file_name": os.path.basename(file_path),
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"上传文件失败: {data}")
        return data["data"]["file_key"]

    def _send_file_message(self, chat_id: str, file_key: str) -> None:
        """发送文件消息到群聊"""
        resp = requests.post(
            f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
            headers={**self._api_headers(), "Content-Type": "application/json"},
            json={
                "receive_id": chat_id,
                "msg_type": "file",
                "content": json.dumps({"file_key": file_key}),
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"发送文件消息失败: {data}")

    def _get_bot_chat_id(self) -> str:
        """获取机器人所在的群聊 chat_id"""
        resp = requests.get(
            "https://open.feishu.cn/open-apis/im/v1/chats",
            headers=self._api_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取群列表失败: {data}")

        items = data.get("data", {}).get("items", [])
        if not items:
            raise RuntimeError("机器人未加入任何群聊，请先将机器人添加到目标群组")

        # 取第一个群聊
        chat_id = items[0].get("chat_id")
        logger.info("找到群聊: %s", items[0].get("name", chat_id))
        return chat_id

    # ─ 公开接口 ────────────────────────────────────────

    def publish(self, summary: str) -> None:
        """
        发送消息到飞书。
        使用 Open API 发送 PDF 文件 + 文本摘要。
        """
        if not self.app_id or not self.app_secret:
            raise RuntimeError("未配置 FEISHU_APP_ID / FEISHU_APP_SECRET，无法发送文件")

        chat_id = self._get_bot_chat_id()

        # 发送 PDF 文件
        pdf_path = self._find_latest_pdf()
        if pdf_path and os.path.exists(pdf_path):
            logger.info("正在通过 Open API 发送 PDF: %s", pdf_path)
            file_key = self._upload_file(pdf_path)
            self._send_file_message(chat_id, file_key)
            logger.info("PDF 文件发送成功")

        # 发送文本摘要
        self._send_text_message(chat_id, summary)
        logger.info("文本摘要发送成功")

    def _send_text_message(self, chat_id: str, text: str) -> None:
        """发送文本消息到群聊"""
        resp = requests.post(
            f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
            headers={**self._api_headers(), "Content-Type": "application/json"},
            json={
                "receive_id": chat_id,
                "msg_type": "text",
                "content": json.dumps({"text": text}),
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"发送文本消息失败: {data}")

    def publish_pdf(self, pdf_path: str) -> None:
        """直接发送 PDF 文件到飞书"""
        if not self.app_id or not self.app_secret:
            raise RuntimeError("未配置 FEISHU_APP_ID / FEISHU_APP_SECRET，无法发送文件")

        chat_id = self._get_bot_chat_id()
        file_key = self._upload_file(pdf_path)
        self._send_file_message(chat_id, file_key)
        logger.info("PDF 发送成功: %s", pdf_path)

    @staticmethod
    def _find_latest_pdf() -> str:
        """查找 output 目录下最新的 PDF 文件"""
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "output")
        if not os.path.isdir(output_dir):
            return ""
        pdfs = []
        for root, _, files in os.walk(output_dir):
            for f in files:
                if f.endswith(".pdf"):
                    pdfs.append(os.path.join(root, f))
        if not pdfs:
            return ""
        return max(pdfs, key=os.path.getmtime)
