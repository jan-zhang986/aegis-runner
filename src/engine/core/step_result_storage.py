# -*- coding: utf-8 -*-
"""
@author Jan
@date 2025-01-16
@packageName packages.engine.src.core
@className StepResultStorage
@describe 步骤结果分片存储服务 - 解决大 workflow 执行时内存溢出问题

核心思想：
1. 每执行完一个步骤，立即将步骤结果存储到 Redis，释放内存
2. 对于后续节点需要引用的数据，只保留摘要/引用在内存中
3. 最终结果组装时从 Redis 分片读取
"""

import json
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from src.engine.core.simple_logger import logger

# Redis 客户端（延迟导入，避免循环依赖）
_redis_client = None


async def get_redis_client():
    """获取 Redis 客户端"""
    global _redis_client
    if _redis_client is None:
        try:
            from src.core.infrastructure.redis_client import get_redis_client as _get_redis
            _redis_client = await _get_redis()
        except ImportError:
            logger.warning("[StepResultStorage] Redis 客户端未配置，使用内存模式")
            _redis_client = None
    return _redis_client


def get_redis_client_sync():
    """同步获取 Redis 客户端（用于非异步上下文）"""
    global _redis_client
    return _redis_client


@dataclass
class StepResultRef:
    """步骤结果引用（轻量级，存储在内存中）"""
    node_id: str
    node_type: str
    status: str
    storage_key: str  # Redis 存储键
    has_output: bool = False
    output_size: int = 0
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "status": self.status,
            "storage_key": self.storage_key,
            "has_output": self.has_output,
            "output_size": self.output_size,
            "error": self.error
        }


class StepResultStorage:
    """
    步骤结果分片存储服务
    
    功能：
    1. 将步骤结果分片存储到 Redis
    2. 提供按需加载能力
    3. 自动管理过期和清理
    """
    
    # 触发分片存储的阈值（字节）
    SHARD_THRESHOLD = 50 * 1024  # 50KB
    
    # 响应体截断阈值
    BODY_TRUNCATE_THRESHOLD = 10 * 1024  # 10KB
    
    # Redis 键过期时间（秒）
    EXPIRE_TIME = 3600  # 1小时
    
    def __init__(self, task_id: str, run_id: str = None):
        """
        初始化存储服务
        
        Args:
            task_id: 任务ID
            run_id: 运行ID（用于构建 Redis 键）
        """
        self.task_id = task_id
        self.run_id = run_id or task_id
        self._step_refs: Dict[str, StepResultRef] = {}  # 步骤引用（轻量级）
        self._step_index = 0  # 步骤计数器
        self._use_redis = True  # 是否使用 Redis
        self._memory_fallback: Dict[str, Dict] = {}  # Redis 不可用时的内存回退
        
        # 用于构建节点引用的摘要数据（供后续节点使用）
        self._node_summaries: Dict[str, Dict[str, Any]] = {}
    
    def _get_step_key(self, step_index: int) -> str:
        """生成步骤存储键"""
        return f"workflow:step:{self.run_id}:{step_index}"
    
    def _get_full_response_key(self, step_index: int) -> str:
        """生成完整响应存储键"""
        return f"workflow:step:{self.run_id}:{step_index}:full_response"
    
    def _get_meta_key(self) -> str:
        """生成元数据存储键"""
        return f"workflow:meta:{self.run_id}"
    
    async def save_step_result(
        self,
        node_id: str,
        node_type: str,
        status: str,
        output: Any,
        error: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        logs: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> StepResultRef:
        """
        保存步骤结果（分片存储）
        
        Args:
            node_id: 节点ID
            node_type: 节点类型
            status: 执行状态
            output: 输出结果
            error: 错误信息
            start_time: 开始时间
            end_time: 结束时间
            logs: 日志
            metadata: 元数据
            
        Returns:
            StepResultRef: 步骤引用对象
        """
        step_index = self._step_index
        self._step_index += 1
        
        storage_key = self._get_step_key(step_index)
        
        # 构建步骤数据
        step_data = {
            "node_id": node_id,
            "node_type": node_type,
            "status": status,
            "error": error,
            "logs": logs,
            "metadata": metadata or {},
            "step_index": step_index,
            "start_time": start_time.isoformat() if start_time else None,
            "end_time": end_time.isoformat() if end_time else None
        }
        
        # 计算输出大小
        output_json = json.dumps(output, default=str) if output else ""
        output_size = len(output_json)
        has_output = output is not None
        
        # 处理输出数据
        if output_size > self.SHARD_THRESHOLD:
            # 大输出：截断存储，完整数据单独存储
            truncated_output, full_output = self._truncate_output(output)
            step_data["output"] = truncated_output
            step_data["_output_truncated"] = True
            step_data["_output_size"] = output_size
            
            # 完整响应单独存储
            await self._save_full_response(step_index, full_output)
            
            logger.info(f"[StepResultStorage] 步骤 {node_id} 输出过大 ({output_size} bytes)，已分片存储")
        else:
            step_data["output"] = output
            step_data["_output_truncated"] = False
        
        # 存储步骤数据
        await self._save_to_storage(storage_key, step_data)
        
        # 创建轻量级引用
        ref = StepResultRef(
            node_id=node_id,
            node_type=node_type,
            status=status,
            storage_key=storage_key,
            has_output=has_output,
            output_size=output_size,
            error=error
        )
        self._step_refs[node_id] = ref
        
        # 保存节点摘要（供后续节点引用）
        self._save_node_summary(node_id, output)
        
        # 更新元数据
        await self._update_meta(step_index + 1)
        
        logger.debug(f"[StepResultStorage] 步骤 {node_id} 已保存，index={step_index}")
        return ref
    
    def _truncate_output(self, output: Any) -> Tuple[Any, Any]:
        """
        截断输出数据
        
        Args:
            output: 原始输出
            
        Returns:
            (truncated_output, full_output): 截断后的输出和完整输出
        """
        if not isinstance(output, dict):
            # 非字典类型，返回摘要
            output_str = json.dumps(output, default=str)
            return {
                "_type": type(output).__name__,
                "_preview": output_str[:1000] + "..." if len(output_str) > 1000 else output_str,
                "_truncated": True
            }, output
        
        truncated = {}
        full = output.copy()
        
        for key, value in output.items():
            if key in ("body", "response", "data", "result"):
                # 响应体类字段，检查大小
                value_str = json.dumps(value, default=str)
                if len(value_str) > self.BODY_TRUNCATE_THRESHOLD:
                    # 截断
                    truncated[key] = {
                        "_truncated": True,
                        "_size": len(value_str),
                        "_preview": value_str[:500] + "..."
                    }
                else:
                    truncated[key] = value
            else:
                # 其他字段保留
                truncated[key] = value
        
        truncated["_has_full_data"] = True
        return truncated, full
    
    def _save_node_summary(self, node_id: str, output: Any):
        """
        保存节点摘要（用于后续节点引用变量）
        
        只保留关键字段，不保留大的响应体
        """
        if output is None:
            self._node_summaries[node_id] = None
            return
        
        if not isinstance(output, dict):
            self._node_summaries[node_id] = output
            return
        
        # 提取摘要字段
        summary = {}
        
        # 保留关键元数据
        for key in ("status", "status_code", "message", "error", "error_code"):
            if key in output:
                summary[key] = output[key]
        
        # 提取的变量
        if "extract_vars" in output:
            summary["extract_vars"] = output["extract_vars"]
        
        # 断言结果
        if "assertion" in output:
            summary["assertion"] = output["assertion"]
        
        # body 字段：只保留小数据或摘要
        if "body" in output:
            body = output["body"]
            if isinstance(body, dict):
                body_str = json.dumps(body, default=str)
                if len(body_str) < 5000:  # 5KB 以下保留
                    summary["body"] = body
                else:
                    # 保留结构但截断大值
                    summary["body"] = self._extract_body_summary(body)
            else:
                body_str = str(body)
                if len(body_str) < 5000:
                    summary["body"] = body
                else:
                    summary["body"] = {"_preview": body_str[:500] + "..."}
        
        self._node_summaries[node_id] = summary
    
    def _extract_body_summary(self, body: dict, max_depth: int = 2) -> dict:
        """从 body 中提取摘要（只保留第一层或第二层的小数据）"""
        if max_depth <= 0:
            return {"_truncated": True}
        
        summary = {}
        for key, value in body.items():
            if isinstance(value, dict):
                value_str = json.dumps(value, default=str)
                if len(value_str) < 1000:
                    summary[key] = value
                else:
                    summary[key] = self._extract_body_summary(value, max_depth - 1)
            elif isinstance(value, list):
                value_str = json.dumps(value, default=str)
                if len(value_str) < 1000:
                    summary[key] = value
                else:
                    summary[key] = {"_type": "list", "_length": len(value), "_truncated": True}
            elif isinstance(value, str) and len(value) > 500:
                summary[key] = value[:500] + "..."
            else:
                summary[key] = value
        
        return summary
    
    def get_node_summary(self, node_id: str) -> Optional[Dict[str, Any]]:
        """获取节点摘要（用于后续节点引用）"""
        return self._node_summaries.get(node_id)
    
    async def _save_to_storage(self, key: str, data: Dict):
        """保存到存储（Redis 或内存）"""
        redis = await get_redis_client()
        
        if redis and self._use_redis:
            try:
                await redis.client.set(
                    key,
                    json.dumps(data, default=str),
                    ex=self.EXPIRE_TIME
                )
            except Exception as e:
                logger.warning(f"[StepResultStorage] Redis 存储失败: {e}，回退到内存")
                self._memory_fallback[key] = data
        else:
            self._memory_fallback[key] = data
    
    async def _save_full_response(self, step_index: int, full_output: Any):
        """保存完整响应（大数据单独存储）"""
        key = self._get_full_response_key(step_index)
        await self._save_to_storage(key, {"full_output": full_output})
    
    async def _update_meta(self, total_steps: int):
        """更新元数据"""
        meta_key = self._get_meta_key()
        meta = {
            "task_id": self.task_id,
            "run_id": self.run_id,
            "total_steps": total_steps,
            "updated_at": datetime.now().isoformat()
        }
        await self._save_to_storage(meta_key, meta)
    
    async def load_step_result(self, step_index: int, include_full_response: bool = False) -> Optional[Dict]:
        """
        加载步骤结果
        
        Args:
            step_index: 步骤索引
            include_full_response: 是否包含完整响应
            
        Returns:
            步骤数据字典
        """
        key = self._get_step_key(step_index)
        data = await self._load_from_storage(key)
        
        if data and include_full_response and data.get("_output_truncated"):
            # 加载完整响应
            full_key = self._get_full_response_key(step_index)
            full_data = await self._load_from_storage(full_key)
            if full_data and "full_output" in full_data:
                data["output"] = full_data["full_output"]
                data["_output_truncated"] = False
        
        return data
    
    async def _load_from_storage(self, key: str) -> Optional[Dict]:
        """从存储加载数据"""
        redis = await get_redis_client()
        
        if redis and self._use_redis:
            try:
                data = await redis.client.get(key)
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.warning(f"[StepResultStorage] Redis 读取失败: {e}")
        
        # 内存回退
        return self._memory_fallback.get(key)
    
    async def load_all_steps(self, include_full_response: bool = False) -> List[Dict]:
        """
        加载所有步骤结果
        
        Args:
            include_full_response: 是否包含完整响应
            
        Returns:
            所有步骤数据列表
        """
        steps = []
        for i in range(self._step_index):
            step_data = await self.load_step_result(i, include_full_response)
            if step_data:
                steps.append(step_data)
        return steps
    
    def get_step_refs(self) -> Dict[str, StepResultRef]:
        """获取所有步骤引用"""
        return self._step_refs.copy()
    
    def get_step_count(self) -> int:
        """获取步骤数量"""
        return self._step_index
    
    async def cleanup(self):
        """清理存储的数据"""
        redis = await get_redis_client()
        
        if redis and self._use_redis:
            try:
                # 删除所有步骤数据
                for i in range(self._step_index):
                    await redis.client.delete(self._get_step_key(i))
                    await redis.client.delete(self._get_full_response_key(i))
                
                # 删除元数据
                await redis.client.delete(self._get_meta_key())
                
                logger.info(f"[StepResultStorage] 已清理 {self._step_index} 个步骤的存储数据")
            except Exception as e:
                logger.warning(f"[StepResultStorage] 清理失败: {e}")
        
        # 清理内存
        self._memory_fallback.clear()
        self._step_refs.clear()
        self._node_summaries.clear()


# ============ 同步适配器（用于同步执行上下文） ============

class SyncStepResultStorage:
    """
    同步版本的步骤结果存储
    
    用于 workflow_engine.py 中的同步执行流程
    
    注意：在同步执行上下文中（线程池），不能直接使用异步 Redis 客户端
    因此只使用内存模式，Redis 操作延迟到主事件循环中执行
    """
    
    def __init__(self, task_id: str, run_id: str = None):
        self._async_storage = StepResultStorage(task_id, run_id)
        # 在同步上下文中，强制使用内存模式，避免事件循环冲突
        self._async_storage._use_redis = False
        self._loop = None
        self._pending_operations = []  # 待执行的 Redis 操作队列
    
    def _get_loop(self):
        """
        获取主事件循环（不创建新的）
        
        注意：在同步执行上下文中，不能创建新的事件循环
        因为 Redis 客户端绑定在主事件循环中
        """
        try:
            # 尝试获取当前事件循环
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            try:
                # 如果没有运行中的循环，尝试获取主循环
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                # 如果都没有，说明在同步上下文中，返回 None
                # 这种情况下只使用内存模式
                self._loop = None
        return self._loop
    
    def save_step_result(self, **kwargs) -> StepResultRef:
        """
        同步保存步骤结果
        
        在同步执行上下文中，只保存到内存，不执行 Redis 操作
        避免事件循环冲突
        """
        # 在同步上下文中，只使用内存模式
        # 直接调用异步存储的同步部分（内存回退）
        try:
            loop = self._get_loop()
            if loop and loop.is_running():
                # 如果有运行中的事件循环，尝试异步执行
                # 但这在同步上下文中通常不会发生
                return loop.run_until_complete(self._async_storage.save_step_result(**kwargs))
            else:
                # 在同步上下文中，只使用内存模式
                # 手动构建步骤引用，不执行 Redis 操作
                return self._save_to_memory_only(**kwargs)
        except Exception as e:
            logger.warning(f"[SyncStepResultStorage] 保存步骤结果失败: {e}，使用内存模式")
            return self._save_to_memory_only(**kwargs)
    
    def _save_to_memory_only(self, **kwargs) -> StepResultRef:
        """只保存到内存，不执行 Redis 操作"""
        node_id = kwargs.get('node_id', 'unknown')
        node_type = kwargs.get('node_type', 'unknown')
        status = kwargs.get('status', 'success')
        output = kwargs.get('output')
        
        # 计算输出大小
        import json
        output_json = json.dumps(output, default=str) if output else ""
        output_size = len(output_json)
        
        # 创建轻量级引用（只保存在内存中）
        step_index = self._async_storage._step_index
        self._async_storage._step_index += 1
        
        storage_key = self._async_storage._get_step_key(step_index)
        
        ref = StepResultRef(
            node_id=node_id,
            node_type=node_type,
            status=status,
            storage_key=storage_key,
            has_output=output is not None,
            output_size=output_size,
            error=kwargs.get('error')
        )
        self._async_storage._step_refs[node_id] = ref
        
        # 保存到内存回退
        step_data = {
            "node_id": node_id,
            "node_type": node_type,
            "status": status,
            "error": kwargs.get('error'),
            "logs": kwargs.get('logs'),
            "metadata": kwargs.get('metadata') or {},
            "step_index": step_index,
            "start_time": kwargs.get('start_time').isoformat() if kwargs.get('start_time') else None,
            "end_time": kwargs.get('end_time').isoformat() if kwargs.get('end_time') else None,
            "output": output,
            "_output_truncated": False
        }
        self._async_storage._memory_fallback[storage_key] = step_data
        
        # 保存节点摘要
        self._async_storage._save_node_summary(node_id, output)
        
        logger.debug(f"[SyncStepResultStorage] 步骤 {node_id} 已保存到内存（同步上下文），index={step_index}")
        return ref
    
    def load_step_result(self, step_index: int, include_full_response: bool = False) -> Optional[Dict]:
        """同步加载步骤结果"""
        # 在同步上下文中，只从内存加载
        key = self._async_storage._get_step_key(step_index)
        return self._async_storage._memory_fallback.get(key)
    
    def load_all_steps(self, include_full_response: bool = False) -> List[Dict]:
        """同步加载所有步骤"""
        # 在同步上下文中，只从内存加载
        steps = []
        for i in range(self._async_storage._step_index):
            step_data = self.load_step_result(i, include_full_response)
            if step_data:
                steps.append(step_data)
        return steps
    
    def get_node_summary(self, node_id: str) -> Optional[Dict[str, Any]]:
        """获取节点摘要"""
        return self._async_storage.get_node_summary(node_id)
    
    def get_step_refs(self) -> Dict[str, StepResultRef]:
        """获取步骤引用"""
        return self._async_storage.get_step_refs()
    
    def get_step_count(self) -> int:
        """获取步骤数量"""
        return self._async_storage.get_step_count()
    
    def cleanup(self):
        """清理"""
        loop = self._get_loop()
        loop.run_until_complete(self._async_storage.cleanup())
    
    @property
    def run_id(self) -> str:
        return self._async_storage.run_id
    
    @property
    def task_id(self) -> str:
        return self._async_storage.task_id
