# -*- coding: utf-8 -*-
"""
Aegis 事件上报器 (Reporters)
负责将 AegisEvent 分发至终端控制台、本地伴侣 (Local Companion) 或平台云端。
"""
import os
import json
import logging
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from typing import List, Optional
from aegis.protocol import AegisEvent

logger = logging.getLogger("aegis.reporter")


class BaseReporter(ABC):
    """上报器抽象基类"""

    @abstractmethod
    def report(self, event: AegisEvent) -> None:
        """接收并处理事件"""
        pass

    def close(self) -> None:
        """关闭上报器（如刷新缓冲区等）"""
        pass


class ConsoleReporter(BaseReporter):
    """本地控制台打印上报器（彩色友好展示）"""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def report(self, event: AegisEvent) -> None:
        if not self.verbose:
            return

        ev_type = event.event_type
        if ev_type == "CASE_START":
            risk_info = f" [风险: {event.risk}]" if event.risk else ""
            print(f"\n🚀 [Aegis Case Start] {event.case_id}: {event.title}{risk_info}")
        elif ev_type == "CASE_END":
            icon = "✅" if event.status == "PASSED" else "❌"
            print(f"{icon} [Aegis Case End] {event.case_id} => {event.status} ({event.duration_ms}ms)")
        elif ev_type == "STEP_START":
            print(f"   ▶ {event.step_name} ...", end="", flush=True)
        elif ev_type == "STEP_END":
            icon = "✓" if event.status == "PASSED" else "✗"
            evidence_str = f" | 证据: {event.evidence}" if event.evidence else ""
            if event.status == "PASSED":
                print(f" \033[32m{icon} PASSED\033[0m ({event.duration_ms}ms){evidence_str}")
            else:
                print(f" \033[31m{icon} FAILED\033[0m ({event.duration_ms}ms) Error: {event.error}")


class HttpReporter(BaseReporter):
    """HTTP 实时推送上报器（上报到 Local Companion 127.0.0.1:8989 或 Aegis Server）"""

    def __init__(self, target_url: str, timeout: float = 1.5, token: Optional[str] = None):
        self.target_url = target_url.rstrip("/")
        # 若是完整端点直接使用，否则自动补充 /api/v1/events
        if not self.target_url.endswith("/events") and not self.target_url.endswith("/api/v1/events"):
            self.endpoint = f"{self.target_url}/api/v1/events"
        else:
            self.endpoint = self.target_url
        self.timeout = timeout
        self.token = token

    def report(self, event: AegisEvent) -> None:
        data = json.dumps(event.to_dict()).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=data,
            headers={
                "Content-Type": "application/json",
                **( {"Authorization": f"Bearer {self.token}"} if self.token else {} ),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                pass
        except Exception as e:
            # 本地调试或网络不可达时不中断测试本身执行（Fail-safe 机制）
            logger.debug(f"[Aegis HttpReporter] Failed to send event to {self.endpoint}: {e}")


class JsonLinesReporter(BaseReporter):
    """将事件追加保存至本地 jsonl 文件（供 CI/CD 或离线分析）"""

    def __init__(self, file_path: str):
        self.file_path = file_path
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)

    def report(self, event: AegisEvent) -> None:
        try:
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.debug(f"[Aegis JsonLinesReporter] Failed to write event: {e}")


class CompositeReporter(BaseReporter):
    """复合上报器：管理多个上报通道"""

    def __init__(self, reporters: Optional[List[BaseReporter]] = None):
        self.reporters: List[BaseReporter] = reporters or []

    def add_reporter(self, reporter: BaseReporter) -> None:
        self.reporters.append(reporter)

    def report(self, event: AegisEvent) -> None:
        for r in self.reporters:
            try:
                r.report(event)
            except Exception as e:
                logger.debug(f"[Aegis CompositeReporter] Reporter {r} failed: {e}")

    def close(self) -> None:
        for r in self.reporters:
            try:
                r.close()
            except Exception:
                pass
