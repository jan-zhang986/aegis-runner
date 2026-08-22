# -*- coding: utf-8 -*-
"""
检查点与恢复机制 - 支持断点恢复
inspired by LangGraph's checkpointing system
"""

import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, asdict
import networkx as nx

from aegis_runner.engine.workflow_engine import WorkflowExecutor
from aegis_runner.engine.models import ExecutionResult, ExecutionStatus
from aegis_runner.engine.core.factory import ProcessorFactory
from aegis_runner.engine.core.simple_logger import logger


@dataclass
class Checkpoint:
    """
    检查点数据结构
    
    包含执行状态的完整快照，用于恢复执行
    """
    workflow_id: str
    execution_id: str
    timestamp: str
    
    # 执行进度
    completed_nodes: List[str]
    failed_node: Optional[str] = None
    next_node_id: Optional[str] = None
    
    # 上下文快照
    context_variables: Dict[str, Any] = None
    node_results: Dict[str, Any] = None
    
    # 执行统计
    total_nodes: int = 0
    completed_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Checkpoint':
        """从字典创建"""
        return cls(**data)


class CheckpointManager:
    """
    检查点管理器
    
    负责检查点的保存、加载和管理
    """
    
    def __init__(self, storage_path: str = "./.aegis_checkpoints"):
        """
        初始化检查点管理器
        
        Args:
            storage_path: 检查点存储路径
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"💾 检查点存储路径: {self.storage_path.absolute()}")
    
    def save_checkpoint(self, checkpoint: Checkpoint) -> str:
        """
        保存检查点
        
        Args:
            checkpoint: 检查点对象
            
        Returns:
            str: 检查点文件路径
        """
        checkpoint_file = self.storage_path / f"{checkpoint.execution_id}.json"
        
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint.to_dict(), f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 检查点已保存: {checkpoint_file.name}")
        logger.info(f"   执行ID: {checkpoint.execution_id}")
        logger.info(f"   已完成: {checkpoint.completed_count}/{checkpoint.total_nodes} 节点")
        
        return str(checkpoint_file)
    
    def load_checkpoint(self, execution_id: str) -> Optional[Checkpoint]:
        """
        加载检查点
        
        Args:
            execution_id: 执行ID
            
        Returns:
            Checkpoint: 检查点对象，不存在则返回None
        """
        checkpoint_file = self.storage_path / f"{execution_id}.json"
        
        if not checkpoint_file.exists():
            logger.warning(f"⚠️  检查点不存在: {execution_id}")
            return None
        
        with open(checkpoint_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        checkpoint = Checkpoint.from_dict(data)
        
        logger.info(f"📂 检查点已加载: {checkpoint_file.name}")
        logger.info(f"   执行ID: {checkpoint.execution_id}")
        logger.info(f"   已完成: {checkpoint.completed_count}/{checkpoint.total_nodes} 节点")
        logger.info(f"   继续节点: {checkpoint.next_node_id}")
        
        return checkpoint
    
    def list_checkpoints(self, workflow_id: str = None) -> List[Dict[str, Any]]:
        """
        列出所有检查点
        
        Args:
            workflow_id: 工作流ID，None表示列出所有
            
        Returns:
            List[Dict]: 检查点列表
        """
        checkpoints = []
        
        for file in self.storage_path.glob("*.json"):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if workflow_id is None or data.get("workflow_id") == workflow_id:
                    checkpoints.append({
                        "execution_id": data.get("execution_id"),
                        "workflow_id": data.get("workflow_id"),
                        "timestamp": data.get("timestamp"),
                        "completed_count": data.get("completed_count"),
                        "total_nodes": data.get("total_nodes"),
                        "failed_node": data.get("failed_node"),
                        "next_node_id": data.get("next_node_id")
                    })
            except Exception as e:
                logger.warning(f"⚠️  读取检查点文件失败: {file.name} | {e}")
        
        # 按时间排序
        checkpoints.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return checkpoints
    
    def delete_checkpoint(self, execution_id: str) -> bool:
        """
        删除检查点
        
        Args:
            execution_id: 执行ID
            
        Returns:
            bool: 是否删除成功
        """
        checkpoint_file = self.storage_path / f"{execution_id}.json"
        
        if not checkpoint_file.exists():
            return False
        
        checkpoint_file.unlink()
        logger.info(f"🗑️  检查点已删除: {execution_id}")
        return True
    
    def clean_old_checkpoints(self, days: int = 7):
        """
        清理旧检查点
        
        Args:
            days: 保留天数
        """
        cutoff_time = time.time() - (days * 24 * 3600)
        deleted_count = 0
        
        for file in self.storage_path.glob("*.json"):
            if file.stat().st_mtime < cutoff_time:
                file.unlink()
                deleted_count += 1
        
        if deleted_count > 0:
            logger.info(f"🗑️  清理了 {deleted_count} 个旧检查点（>{days}天）")


class ResumableWorkflowExecutor(WorkflowExecutor):
    """
    支持断点恢复的工作流引擎
    
    特点：
    1. 自动保存检查点
    2. 失败后可从断点恢复
    3. 不需要重跑已完成的节点
    
    使用示例:
        # 第一次执行（假设失败）
        executor = ResumableWorkflowExecutor(
            workflow,
            execution_id="test_run_001"
        )
        try:
            result = executor.execute_with_checkpoint()
        except Exception as e:
            print(f"执行失败，检查点已保存")
        
        # 修复问题后，从失败点继续
        executor = ResumableWorkflowExecutor(
            workflow,
            execution_id="test_run_001"  # 使用相同的ID
        )
        result = executor.execute_with_checkpoint()  # 继续执行！
    """
    
    def __init__(
        self, 
        workflow_data: Any, 
        execution_id: str = None,
        checkpoint_manager: CheckpointManager = None,
        environment: str = None,
        auto_checkpoint: bool = True
    ):
        """
        初始化可恢复执行器
        
        Args:
            workflow_data: 工作流数据
            execution_id: 执行ID，如果为None则自动生成
            checkpoint_manager: 检查点管理器
            environment: 环境名称
            auto_checkpoint: 是否自动保存检查点
        """
        super().__init__(workflow_data, environment)
        
        self.execution_id = execution_id or f"exec_{int(time.time() * 1000)}"
        self.checkpoint_manager = checkpoint_manager or CheckpointManager()
        self.auto_checkpoint = auto_checkpoint
        self.checkpoint: Optional[Checkpoint] = None
        
        logger.info(f"🔄 可恢复执行器已初始化")
        logger.info(f"   执行ID: {self.execution_id}")
        logger.info(f"   自动检查点: {'启用' if auto_checkpoint else '禁用'}")
    
    def execute_with_checkpoint(self, save_on_complete: bool = False) -> ExecutionResult:
        """
        执行工作流并支持检查点恢复
        
        Args:
            save_on_complete: 完成后是否保留检查点
            
        Returns:
            ExecutionResult: 执行结果
        """
        # 尝试加载检查点
        self.checkpoint = self.checkpoint_manager.load_checkpoint(self.execution_id)
        
        if self.checkpoint:
            print(f"""
╔════════════════════════════════════════════════════════════╗
║                  🔄 从检查点恢复执行                        ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  执行ID: {self.checkpoint.execution_id:<48}║
║  工作流: {self.checkpoint.workflow_id:<48}║
║                                                            ║
║  进度: {self.checkpoint.completed_count}/{self.checkpoint.total_nodes} 节点已完成                                  ║
║                                                            ║
║  已完成节点:                                                ║""")
            for node_id in self.checkpoint.completed_nodes[-5:]:  # 显示最后5个
                print(f"║    ✅ {node_id:<53}║")
            
            if len(self.checkpoint.completed_nodes) > 5:
                print(f"║    ... 还有 {len(self.checkpoint.completed_nodes) - 5} 个节点                                      ║")
            
            print(f"""║                                                            ║
║  继续节点: {self.checkpoint.next_node_id or '无':<48}║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
            """)
            
            # 恢复上下文
            if self.checkpoint.context_variables:
                for key, value in self.checkpoint.context_variables.items():
                    self.context.set_variable(key, value)
            
            if self.checkpoint.node_results:
                for node_id, result in self.checkpoint.node_results.items():
                    self.context.set_node_result(node_id, result)
        else:
            logger.info(f"🆕 开始新的执行")
        
        # 设置执行开始时间
        self.execution_result.start_time = datetime.now()
        self.execution_result.status = ExecutionStatus.RUNNING
        
        # 获取执行顺序
        execution_order = list(nx.topological_sort(self.graph))
        
        # 如果有检查点，跳过已完成的节点
        if self.checkpoint and self.checkpoint.next_node_id:
            try:
                start_index = execution_order.index(self.checkpoint.next_node_id)
                execution_order = execution_order[start_index:]
                logger.info(f"⏩ 跳过已完成的 {start_index} 个节点")
            except ValueError:
                logger.warning(f"⚠️  检查点中的节点 '{self.checkpoint.next_node_id}' 不在执行顺序中")
        
        logger.info(f"📋 剩余执行顺序: {execution_order}")
        
        # 执行节点
        completed_nodes = self.checkpoint.completed_nodes if self.checkpoint else []
        
        for node_id in execution_order:
            node = self.node_map[node_id]
            
            logger.info(f"⏳ 开始执行节点: {node_id} ({node.type})")
            
            # 检查前置条件
            should_skip = self._check_should_skip(node_id)
            if should_skip:
                logger.info(f"⏭️  跳过节点: {node_id}")
                continue
            
            # 获取前驱节点结果
            predecessors = list(self.graph.predecessors(node_id))
            predecessor_results = {
                p: self.context.get_node_result(p) 
                for p in predecessors
            }
            
            try:
                # 执行节点
                processor = ProcessorFactory.get_processor(node.type)
                result = processor.execute(node.to_dict(), self.context, predecessor_results)
                
                # 保存结果（仅存 node_results，不再注册为全局变量以节省内存）
                self.context.set_node_result(node_id, result)
                
                # 记录已完成
                completed_nodes.append(node_id)
                
                # 自动保存检查点
                if self.auto_checkpoint:
                    self._save_checkpoint_after_node(node_id, execution_order, completed_nodes)
                
                logger.info(f"✅ 节点执行完成: {node_id}")
                
            except Exception as e:
                logger.error(f"❌ 节点执行失败: {node_id} | 错误: {str(e)}")
                
                # 失败时保存检查点
                if self.auto_checkpoint:
                    self._save_checkpoint_on_failure(node_id, execution_order, completed_nodes)
                
                # 设置工作流失败状态
                self.execution_result.status = ExecutionStatus.FAILED
                self.execution_result.end_time = datetime.now()
                
                raise e
        
        # 执行成功
        self.execution_result.status = ExecutionStatus.SUCCESS
        self.execution_result.end_time = datetime.now()
        self.execution_result.variables = self.context.get_all_variables()
        
        # 完成后清理检查点（可选）
        if not save_on_complete and self.auto_checkpoint:
            self.checkpoint_manager.delete_checkpoint(self.execution_id)
            logger.info(f"✅ 执行成功，检查点已清理")
        
        logger.info(f"🎉 工作流执行完成: {self.execution_result.workflow_id}")
        
        return self.execution_result
    
    def _save_checkpoint_after_node(
        self, 
        node_id: str, 
        execution_order: List[str],
        completed_nodes: List[str]
    ):
        """节点执行完成后保存检查点"""
        # 确定下一个节点
        try:
            current_index = execution_order.index(node_id)
            next_node_id = execution_order[current_index + 1] if current_index + 1 < len(execution_order) else None
        except ValueError:
            next_node_id = None
        
        checkpoint = Checkpoint(
            workflow_id=self.execution_result.workflow_id,
            execution_id=self.execution_id,
            timestamp=datetime.now().isoformat(),
            completed_nodes=completed_nodes.copy(),
            next_node_id=next_node_id,
            context_variables=self.context.get_all_variables(),
            node_results=self.context.get_all_node_results(),
            total_nodes=len(self.node_map),
            completed_count=len(completed_nodes)
        )
        
        self.checkpoint_manager.save_checkpoint(checkpoint)
    
    def _save_checkpoint_on_failure(
        self, 
        failed_node_id: str, 
        execution_order: List[str],
        completed_nodes: List[str]
    ):
        """失败时保存检查点（用于恢复）"""
        checkpoint = Checkpoint(
            workflow_id=self.execution_result.workflow_id,
            execution_id=self.execution_id,
            timestamp=datetime.now().isoformat(),
            completed_nodes=completed_nodes.copy(),
            failed_node=failed_node_id,
            next_node_id=failed_node_id,  # 下次从失败的节点重新开始
            context_variables=self.context.get_all_variables(),
            node_results=self.context.get_all_node_results(),
            total_nodes=len(self.node_map),
            completed_count=len(completed_nodes)
        )
        
        self.checkpoint_manager.save_checkpoint(checkpoint)
        
        print(f"""
╔════════════════════════════════════════════════════════════╗
║                  💾 失败检查点已保存                        ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  执行ID: {self.execution_id:<48}║
║  失败节点: {failed_node_id:<46}║
║  已完成: {len(completed_nodes)}/{len(self.node_map)} 节点                                            ║
║                                                            ║
║  💡 修复问题后，使用相同的 execution_id 继续执行：           ║
║                                                            ║
║  executor = ResumableWorkflowExecutor(                     ║
║      workflow,                                             ║
║      execution_id="{self.execution_id:<37}"  ║
║  )                                                         ║
║  result = executor.execute_with_checkpoint()               ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
        """)
    
    def _check_should_skip(self, node_id: str) -> bool:
        """检查节点是否应该跳过"""
        predecessors = list(self.graph.predecessors(node_id))
        for pred_id in predecessors:
            pred_node = self.node_map[pred_id]
            if pred_node.type == "condition":
                pred_result = self.context.get_node_result(pred_id)
                edge_data = self.graph.get_edge_data(pred_id, node_id)
                source_handle = edge_data.get('source_handle')
                if pred_result != source_handle:
                    return True
        return False
