"""发布器抽象基类"""

from abc import ABC, abstractmethod


class BasePublisher(ABC):
    """发布器接口 — 所有发布器实现此接口"""

    @abstractmethod
    def publish(self, summary: str) -> None:
        """发布总结内容"""
        ...
