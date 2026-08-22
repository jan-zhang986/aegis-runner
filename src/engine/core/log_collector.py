# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-13
@packageName src.core
@className LogCollector
@describe 日志收集器，用于收集每个节点执行期间的日志
"""

import threading
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger


class LogCollector:
    """日志收集器，用于收集特定节点执行期间的日志"""
    
    def __init__(self, node_id: str):
        """
        初始化日志收集器
        
        Args:
            node_id: 节点ID，用于标识收集的日志属于哪个节点
        """
        self.node_id = node_id
        self.logs: List[Dict[str, Any]] = []
        self.handler_id: Optional[int] = None
        self.lock = threading.Lock()
        self._enabled = False
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
    
    def start(self):
        """开始收集日志"""
        if self._enabled:
            return
        
        self._enabled = True
        self.logs.clear()
        self.start_time = datetime.now()
        self.end_time = None
        self._thread_id = threading.current_thread().ident
        
        # 添加自定义sink来收集日志
        def log_sink(message):
            """日志收集sink"""
            if not self._enabled:
                return
            
            # 线程隔离：只收集同一线程产生的日志，避免并发时日志交叉污染
            if threading.current_thread().ident != self._thread_id:
                return
            
            # 解析日志消息
            record = message.record
            log_time = datetime.fromtimestamp(record["time"].timestamp())
            
            # 只收集在收集期间产生的日志
            if self.start_time and log_time < self.start_time:
                return
            
            if self.end_time and log_time > self.end_time:
                return
            
            # 格式化日志消息
            try:
                # 获取格式化的消息（包含时间戳、级别等信息）
                message_text = str(message).strip()
            except:
                # 如果转换失败，尝试获取原始消息
                try:
                    message_text = record.get("message", str(message))
                except:
                    message_text = "无法解析日志消息"
            
            log_entry = {
                "timestamp": log_time.isoformat(),
                "level": record["level"].name,
                "message": message_text,
                "module": record.get("module", ""),
                "function": record.get("function", ""),
                "line": record.get("line", 0),
                "name": record.get("name", "")
            }
            
            with self.lock:
                self.logs.append(log_entry)
        
        # 添加sink到logger
        self.handler_id = logger.add(
            log_sink,
            level="DEBUG",  # 收集所有级别的日志
            format="{time} | {level} | {name} | {message}",
            enqueue=False  # 不使用队列，直接同步处理
        )
    
    def stop(self):
        """停止收集日志"""
        if not self._enabled:
            return
        
        self.end_time = datetime.now()
        self._enabled = False
        
        # 移除sink
        if self.handler_id is not None:
            try:
                logger.remove(self.handler_id)
            except ValueError:
                # handler可能已经被移除
                pass
            finally:
                self.handler_id = None
    
    def get_logs(self) -> List[Dict[str, Any]]:
        """获取收集的日志"""
        with self.lock:
            return self.logs.copy()
    
    def clear(self):
        """清空收集的日志"""
        with self.lock:
            self.logs.clear()
    
    def __enter__(self):
        """上下文管理器入口"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.stop()


class ThreadLocalLogCollector:
    """线程本地日志收集器，使用contextvars来区分不同节点的日志"""
    
    def __init__(self):
        self.collectors: Dict[str, LogCollector] = {}
        self.current_node_id: Optional[str] = None
        self.lock = threading.Lock()
    
    def set_current_node(self, node_id: str):
        """设置当前执行的节点ID"""
        with self.lock:
            self.current_node_id = node_id
            # 为节点创建收集器（如果不存在）
            if node_id not in self.collectors:
                self.collectors[node_id] = LogCollector(node_id)
    
    def get_collector(self, node_id: str) -> Optional[LogCollector]:
        """获取节点的日志收集器"""
        with self.lock:
            return self.collectors.get(node_id)
    
    def start_collection(self, node_id: str):
        """开始收集指定节点的日志"""
        with self.lock:
            if node_id not in self.collectors:
                self.collectors[node_id] = LogCollector(node_id)
            self.collectors[node_id].start()
            self.current_node_id = node_id
    
    def stop_collection(self, node_id: str):
        """停止收集指定节点的日志"""
        with self.lock:
            if node_id in self.collectors:
                self.collectors[node_id].stop()
    
    def get_logs(self, node_id: str) -> List[Dict[str, Any]]:
        """获取指定节点的日志"""
        with self.lock:
            collector = self.collectors.get(node_id)
            if collector:
                return collector.get_logs()
            return []
    
    def clear_collector(self, node_id: str):
        """清除指定节点的收集器"""
        with self.lock:
            if node_id in self.collectors:
                self.collectors[node_id].stop()
                del self.collectors[node_id]


# 全局日志收集器实例
_global_log_collector = ThreadLocalLogCollector()


def get_log_collector() -> ThreadLocalLogCollector:
    """获取全局日志收集器实例"""
    return _global_log_collector

