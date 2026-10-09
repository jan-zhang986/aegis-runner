# -*- coding: utf-8 -*-
"""
Aegis 统一事件协议定义 (Event Protocol)
与 Java (JUnit 5)、Go (testing.T) 跨语言对齐的 JSON Event Schema。
"""
import time
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass, field


class EventType(str, Enum):
    RUN_START = "RUN_START"
    RUN_END = "RUN_END"
    CASE_START = "CASE_START"
    CASE_END = "CASE_END"
    STEP_START = "STEP_START"
    STEP_END = "STEP_END"


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class AegisEvent:
    """跨语言统一结构化事件实体"""
    event_type: str
    run_id: Optional[str] = None
    case_id: Optional[str] = None
    req_id: Optional[str] = None
    risk: Optional[str] = None
    title: Optional[str] = None
    priority: Optional[str] = None
    feature: Optional[str] = None
    epic: Optional[str] = None
    step_name: Optional[str] = None
    status: Optional[str] = None
    duration_ms: int = 0
    evidence: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_dict(self) -> Dict[str, Any]:
        """序列化为平台与 Local Companion 兼容的标准字典"""
        return {
            "eventType": self.event_type,
            "runId": self.run_id,
            "caseId": self.case_id,
            "reqId": self.req_id,
            "risk": self.risk,
            "title": self.title,
            "priority": self.priority,
            "feature": self.feature,
            "epic": self.epic,
            "stepName": self.step_name,
            "status": self.status,
            "durationMs": self.duration_ms,
            "evidence": self.evidence,
            "error": self.error,
            "timestamp": self.timestamp,
        }
