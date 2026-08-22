"""
工作流调试器
提供单步调试、断点、上下文查看等功能
"""

import json
import pickle
import networkx as nx
from typing import Any, Dict, List, Optional, Set, Callable
from datetime import datetime
from pathlib import Path

from aegis_runner.engine.context import ExecutionContext
from aegis_runner.engine.core.factory import ProcessorFactory
from aegis_runner.engine.models import Workflow, Node, ExecutionStatus, StepStatus, StepResult
from aegis_runner.engine.core.simple_logger import logger
from aegis_runner.engine.workflow_engine import WorkflowParser


class DebugSnapshot:
    """调试快照 - 保存某个节点执行前后的状态"""
    
    def __init__(self, node_id: str, timestamp: datetime = None):
        self.node_id = node_id
        self.timestamp = timestamp or datetime.now()
        self.context_variables: Dict[str, Any] = {}
        self.node_results: Dict[str, Any] = {}
        self.predecessor_results: Dict[str, Any] = {}
        self.node_output: Any = None
        self.node_config: Dict[str, Any] = {}
        self.error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "node_id": self.node_id,
            "timestamp": self.timestamp.isoformat(),
            "context_variables": self.context_variables,
            "node_results": self.node_results,
            "predecessor_results": self.predecessor_results,
            "node_output": self.node_output,
            "node_config": self.node_config,
            "error": self.error
        }


class WorkflowDebugger:
    """
    工作流调试器
    
    功能：
    1. 单步执行节点
    2. 设置断点
    3. 查看和修改上下文
    4. 查看节点输入输出
    5. 回退到之前的节点
    6. 保存和恢复调试会话
    7. 动态修改节点配置
    """
    
    def __init__(self, workflow_data: Any, environment: str = None):
        """
        初始化调试器
        
        Args:
            workflow_data: 工作流数据
            environment: 环境名称
        """
        self.workflow_data = workflow_data
        self.parser = WorkflowParser(workflow_data)
        self.graph, self.node_map = self.parser.parse()
        self.context = ExecutionContext()
        self.environment = environment
        
        # 调试状态
        self.execution_order = list(nx.topological_sort(self.graph))
        self.current_index = 0
        self.breakpoints: Set[str] = set()
        self.completed_nodes: List[str] = []
        self.snapshots: List[DebugSnapshot] = []
        self.paused = False
        self.stop_requested = False
        
        # 回调函数
        self.on_node_start: Optional[Callable] = None
        self.on_node_end: Optional[Callable] = None
        self.on_breakpoint: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        
        logger.info(f"🐛 调试器已初始化 | 节点数: {len(self.execution_order)}")
        logger.info(f"📋 执行顺序: {' -> '.join(self.execution_order)}")
    
    def add_breakpoint(self, node_id: str):
        """添加断点"""
        if node_id in self.node_map:
            self.breakpoints.add(node_id)
            logger.info(f"🔴 断点已添加: {node_id}")
        else:
            logger.warning(f"⚠️  节点不存在: {node_id}")
    
    def remove_breakpoint(self, node_id: str):
        """移除断点"""
        if node_id in self.breakpoints:
            self.breakpoints.remove(node_id)
            logger.info(f"⚪ 断点已移除: {node_id}")
    
    def clear_breakpoints(self):
        """清除所有断点"""
        self.breakpoints.clear()
        logger.info("🔵 所有断点已清除")
    
    def list_breakpoints(self) -> List[str]:
        """列出所有断点"""
        return list(self.breakpoints)
    
    def set_variable(self, name: str, value: Any):
        """设置上下文变量"""
        self.context.set_variable(name, value)
        logger.info(f"📝 变量已设置: {name} = {value}")
    
    def get_variable(self, name: str) -> Any:
        """获取上下文变量"""
        return self.context.get_variable(name)
    
    def get_all_variables(self) -> Dict[str, Any]:
        """获取所有上下文变量"""
        return self.context._variables.copy()
    
    def get_node_result(self, node_id: str) -> Any:
        """获取节点结果"""
        return self.context.get_node_result(node_id)
    
    def get_all_node_results(self) -> Dict[str, Any]:
        """获取所有节点结果"""
        return self.context._node_results.copy()
    
    def get_current_node(self) -> Optional[Node]:
        """获取当前节点"""
        if self.current_index < len(self.execution_order):
            node_id = self.execution_order[self.current_index]
            return self.node_map[node_id]
        return None
    
    def get_next_node(self) -> Optional[Node]:
        """获取下一个节点"""
        if self.current_index + 1 < len(self.execution_order):
            node_id = self.execution_order[self.current_index + 1]
            return self.node_map[node_id]
        return None
    
    def get_snapshot(self, index: int = -1) -> Optional[DebugSnapshot]:
        """获取快照"""
        if self.snapshots:
            return self.snapshots[index]
        return None
    
    def get_all_snapshots(self) -> List[DebugSnapshot]:
        """获取所有快照"""
        return self.snapshots.copy()
    
    def get_node_info(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        获取节点完整信息
        
        Args:
            node_id: 节点ID
            
        Returns:
            节点信息字典，包含id、type、data等
        """
        if node_id not in self.node_map:
            logger.warning(f"⚠️  节点不存在: {node_id}")
            return None
        
        node = self.node_map[node_id]
        return node.to_dict()
    
    def get_node_config(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        获取节点配置
        
        Args:
            node_id: 节点ID
            
        Returns:
            节点配置字典
        """
        if node_id not in self.node_map:
            logger.warning(f"⚠️  节点不存在: {node_id}")
            return None
        
        node = self.node_map[node_id]
        node_dict = node.to_dict()
        return node_dict.get("data", {}).get("config", {})
    
    def update_node_config(self, node_id: str, config: Dict[str, Any]) -> bool:
        """
        更新节点配置
        
        Args:
            node_id: 节点ID
            config: 新的配置字典
            
        Returns:
            是否更新成功
        """
        if node_id not in self.node_map:
            logger.warning(f"⚠️  节点不存在: {node_id}")
            return False
        
        node = self.node_map[node_id]
        node_dict = node.to_dict()
        
        # 更新配置
        if "data" not in node_dict:
            node_dict["data"] = {}
        node_dict["data"]["config"] = config
        
        # 重新创建节点
        new_node = Node.from_dict(node_dict)
        self.node_map[node_id] = new_node
        
        logger.info(f"✏️  节点配置已更新: {node_id}")
        return True
    
    def update_node_data(self, node_id: str, data: Dict[str, Any]) -> bool:
        """
        更新节点数据（包括config和其他数据）
        
        Args:
            node_id: 节点ID
            data: 新的数据字典
            
        Returns:
            是否更新成功
        """
        if node_id not in self.node_map:
            logger.warning(f"⚠️  节点不存在: {node_id}")
            return False
        
        node = self.node_map[node_id]
        node_dict = node.to_dict()
        
        # 更新数据
        node_dict["data"] = data
        
        # 重新创建节点
        new_node = Node.from_dict(node_dict)
        self.node_map[node_id] = new_node
        
        logger.info(f"✏️  节点数据已更新: {node_id}")
        return True
    
    def update_node_type(self, node_id: str, node_type: str) -> bool:
        """
        更新节点类型
        
        Args:
            node_id: 节点ID
            node_type: 新的节点类型
            
        Returns:
            是否更新成功
        """
        if node_id not in self.node_map:
            logger.warning(f"⚠️  节点不存在: {node_id}")
            return False
        
        node = self.node_map[node_id]
        node_dict = node.to_dict()
        
        # 更新类型
        node_dict["type"] = node_type
        
        # 重新创建节点
        new_node = Node.from_dict(node_dict)
        self.node_map[node_id] = new_node
        
        logger.info(f"✏️  节点类型已更新: {node_id} -> {node_type}")
        return True
    
    def update_node(self, node_id: str, updates: Dict[str, Any]) -> bool:
        """
        批量更新节点属性
        
        Args:
            node_id: 节点ID
            updates: 要更新的属性字典，可以包含:
                    - type: 节点类型
                    - data: 节点数据
                    - config: 节点配置（会合并到data.config中）
            
        Returns:
            是否更新成功
            
        Example:
            debugger.update_node("api_call", {
                "config": {"timeout": 60, "retry": 3}
            })
        """
        if node_id not in self.node_map:
            logger.warning(f"⚠️  节点不存在: {node_id}")
            return False
        
        node = self.node_map[node_id]
        node_dict = node.to_dict()
        
        # 更新类型
        if "type" in updates:
            node_dict["type"] = updates["type"]
        
        # 更新数据
        if "data" in updates:
            node_dict["data"] = updates["data"]
        
        # 更新配置（合并到data.config）
        if "config" in updates:
            if "data" not in node_dict:
                node_dict["data"] = {}
            if "config" not in node_dict["data"]:
                node_dict["data"]["config"] = {}
            node_dict["data"]["config"].update(updates["config"])
        
        # 重新创建节点
        new_node = Node.from_dict(node_dict)
        self.node_map[node_id] = new_node
        
        logger.info(f"✏️  节点已更新: {node_id} | 更新项: {list(updates.keys())}")
        return True
    
    def print_node_info(self, node_id: str):
        """打印节点信息"""
        node_info = self.get_node_info(node_id)
        if not node_info:
            return
        
        print("\n" + "="*60)
        print(f"📦 节点信息: {node_id}")
        print("="*60)
        print(f"类型: {node_info.get('type', 'N/A')}")
        print(f"ID: {node_info.get('id', 'N/A')}")
        
        data = node_info.get('data', {})
        if data:
            print(f"\n数据:")
            print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
        
        print("="*60 + "\n")
    
    def _create_snapshot(self, node_id: str, predecessor_results: Dict[str, Any] = None) -> DebugSnapshot:
        """创建快照"""
        snapshot = DebugSnapshot(node_id)
        snapshot.context_variables = self.context._variables.copy()
        snapshot.node_results = self.context._node_results.copy()
        snapshot.predecessor_results = predecessor_results or {}
        
        node = self.node_map[node_id]
        snapshot.node_config = node.to_dict()
        
        return snapshot
    
    def _should_pause_at_node(self, node_id: str) -> bool:
        """判断是否应该在节点处暂停"""
        return node_id in self.breakpoints
    
    def step_over(self) -> Dict[str, Any]:
        """
        单步执行下一个节点
        
        Returns:
            执行结果
        """
        if self.current_index >= len(self.execution_order):
            logger.info("✅ 工作流已执行完成")
            return {
                "status": "completed",
                "message": "工作流已执行完成"
            }
        
        node_id = self.execution_order[self.current_index]
        node = self.node_map[node_id]
        node_type = node.type
        
        logger.info(f"🔍 执行节点 [{self.current_index + 1}/{len(self.execution_order)}]: {node_id} ({node_type})")
        
        # 检查前置条件（分支处理）
        should_skip = False
        predecessors = list(self.graph.predecessors(node_id))
        for pred_id in predecessors:
            pred_node = self.node_map[pred_id]
            if pred_node.type == "condition":
                pred_result = self.context.get_node_result(pred_id)
                edge_data = self.graph.get_edge_data(pred_id, node_id)
                source_handle = edge_data.get('source_handle')
                if pred_result != source_handle:
                    logger.info(f"⏭️  跳过节点 {node_id} (分支条件不满足)")
                    should_skip = True
                    break
        
        if should_skip:
            self.current_index += 1
            return {
                "status": "skipped",
                "node_id": node_id,
                "node_type": node_type,
                "message": f"节点 {node_id} 已跳过"
            }
        
        # 获取前驱节点结果
        predecessor_results = {p: self.context.get_node_result(p) for p in predecessors}
        
        # 创建执行前快照
        snapshot = self._create_snapshot(node_id, predecessor_results)
        
        # 触发节点开始回调
        if self.on_node_start:
            self.on_node_start(node_id, node, predecessor_results)
        
        try:
            # 执行节点
            processor = ProcessorFactory.get_processor(node_type)
            result = processor.execute(node.to_dict(), self.context, predecessor_results)
            
            # 保存结果（仅存 node_results，不再注册为全局变量以节省内存）
            self.context.set_node_result(node_id, result)
            
            # 记录快照
            snapshot.node_output = result
            self.snapshots.append(snapshot)
            
            # 标记已完成
            self.completed_nodes.append(node_id)
            self.current_index += 1
            
            # 触发节点结束回调
            if self.on_node_end:
                self.on_node_end(node_id, node, result)
            
            logger.info(f"✅ 节点执行成功: {node_id}")
            
            return {
                "status": "success",
                "node_id": node_id,
                "node_type": node_type,
                "output": result,
                "snapshot": snapshot.to_dict()
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ 节点执行失败: {node_id} | 错误: {error_msg}")
            
            # 记录错误快照
            snapshot.error = error_msg
            self.snapshots.append(snapshot)
            
            # 触发错误回调
            if self.on_error:
                self.on_error(node_id, node, e)
            
            return {
                "status": "failed",
                "node_id": node_id,
                "node_type": node_type,
                "error": error_msg,
                "snapshot": snapshot.to_dict()
            }
    
    def continue_execution(self) -> Dict[str, Any]:
        """
        继续执行直到遇到断点或完成
        
        Returns:
            执行结果
        """
        logger.info("▶️  继续执行...")
        
        while self.current_index < len(self.execution_order):
            node_id = self.execution_order[self.current_index]
            
            # 检查断点
            if self._should_pause_at_node(node_id):
                logger.info(f"🛑 遇到断点: {node_id}")
                if self.on_breakpoint:
                    self.on_breakpoint(node_id, self.node_map[node_id])
                return {
                    "status": "paused",
                    "node_id": node_id,
                    "message": f"在断点处暂停: {node_id}"
                }
            
            # 执行节点
            result = self.step_over()
            
            if result["status"] == "failed":
                return result
        
        logger.info("✅ 工作流执行完成")
        return {
            "status": "completed",
            "message": "工作流执行完成"
        }
    
    def restart(self):
        """重启调试会话"""
        logger.info("🔄 重启调试会话")
        self.current_index = 0
        self.completed_nodes.clear()
        self.snapshots.clear()
        self.context = ExecutionContext()
        self.paused = False
        self.stop_requested = False
    
    def rollback_to_node(self, node_id: str) -> bool:
        """
        回退到指定节点
        
        Args:
            node_id: 节点ID
            
        Returns:
            是否成功回退
        """
        if node_id not in self.execution_order:
            logger.warning(f"⚠️  节点不存在: {node_id}")
            return False
        
        # 找到节点索引
        target_index = self.execution_order.index(node_id)
        
        if target_index >= self.current_index:
            logger.warning(f"⚠️  无法回退到未执行的节点: {node_id}")
            return False
        
        # 找到对应的快照
        snapshot_index = -1
        for i, snapshot in enumerate(self.snapshots):
            if snapshot.node_id == node_id:
                snapshot_index = i
                break
        
        if snapshot_index < 0:
            logger.warning(f"⚠️  未找到节点快照: {node_id}")
            return False
        
        # 恢复快照
        snapshot = self.snapshots[snapshot_index]
        self.context._variables = snapshot.context_variables.copy()
        self.context._node_results = snapshot.node_results.copy()
        
        # 更新状态
        self.current_index = target_index
        self.completed_nodes = self.completed_nodes[:target_index]
        self.snapshots = self.snapshots[:snapshot_index]
        
        logger.info(f"⏪ 已回退到节点: {node_id}")
        return True
    
    def save_session(self, filepath: str):
        """
        保存调试会话
        
        Args:
            filepath: 保存路径
        """
        session_data = {
            "workflow_data": self.workflow_data,
            "environment": self.environment,
            "current_index": self.current_index,
            "breakpoints": list(self.breakpoints),
            "completed_nodes": self.completed_nodes,
            "context_variables": self.context._variables,
            "context_node_results": self.context._node_results,
            "snapshots": [s.to_dict() for s in self.snapshots],
            "timestamp": datetime.now().isoformat()
        }
        
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"💾 调试会话已保存: {filepath}")
    
    @classmethod
    def load_session(cls, filepath: str) -> 'WorkflowDebugger':
        """
        加载调试会话
        
        Args:
            filepath: 会话文件路径
            
        Returns:
            调试器实例
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            session_data = json.load(f)
        
        # 创建调试器实例
        debugger = cls(
            workflow_data=session_data["workflow_data"],
            environment=session_data.get("environment")
        )
        
        # 恢复状态
        debugger.current_index = session_data["current_index"]
        debugger.breakpoints = set(session_data["breakpoints"])
        debugger.completed_nodes = session_data["completed_nodes"]
        debugger.context._variables = session_data["context_variables"]
        debugger.context._node_results = session_data["context_node_results"]
        
        # 恢复快照
        debugger.snapshots = []
        for snapshot_dict in session_data["snapshots"]:
            snapshot = DebugSnapshot(
                node_id=snapshot_dict["node_id"],
                timestamp=datetime.fromisoformat(snapshot_dict["timestamp"])
            )
            snapshot.context_variables = snapshot_dict["context_variables"]
            snapshot.node_results = snapshot_dict["node_results"]
            snapshot.predecessor_results = snapshot_dict["predecessor_results"]
            snapshot.node_output = snapshot_dict["node_output"]
            snapshot.node_config = snapshot_dict["node_config"]
            snapshot.error = snapshot_dict.get("error")
            debugger.snapshots.append(snapshot)
        
        logger.info(f"📂 调试会话已加载: {filepath}")
        logger.info(f"📊 当前进度: {debugger.current_index}/{len(debugger.execution_order)}")
        
        return debugger
    
    def print_status(self):
        """打印当前调试状态"""
        print("\n" + "="*60)
        print("🐛 调试器状态")
        print("="*60)
        print(f"📊 进度: {self.current_index}/{len(self.execution_order)}")
        print(f"✅ 已完成: {len(self.completed_nodes)} 个节点")
        print(f"🔴 断点: {len(self.breakpoints)} 个")
        
        if self.breakpoints:
            print(f"   {', '.join(self.breakpoints)}")
        
        current_node = self.get_current_node()
        if current_node:
            print(f"👉 当前节点: {current_node.id} ({current_node.type})")
        else:
            print("👉 当前节点: 无 (已完成)")
        
        next_node = self.get_next_node()
        if next_node:
            print(f"⏭️  下一个节点: {next_node.id} ({next_node.type})")
        
        print(f"📝 上下文变量: {len(self.context._variables)} 个")
        print(f"📦 节点结果: {len(self.context._node_results)} 个")
        print(f"📸 快照: {len(self.snapshots)} 个")
        print("="*60 + "\n")
    
    def print_variables(self):
        """打印所有变量"""
        print("\n" + "="*60)
        print("📝 上下文变量")
        print("="*60)
        
        if not self.context._variables:
            print("(空)")
        else:
            for name, value in self.context._variables.items():
                value_str = str(value)
                print(f"  {name}: {value_str}")
        
        print("="*60 + "\n")
    
    def print_node_results(self):
        """打印所有节点结果"""
        print("\n" + "="*60)
        print("📦 节点结果")
        print("="*60)
        
        if not self.context._node_results:
            print("(空)")
        else:
            for node_id, result in self.context._node_results.items():
                result_str = str(result)
                print(f"  {node_id}: {result_str}")
        
        print("="*60 + "\n")


class InteractiveDebugger:
    """
    交互式调试器 - 提供命令行界面
    """
    
    def __init__(self, workflow_data: Any, environment: str = None):
        self.debugger = WorkflowDebugger(workflow_data, environment)
        self.running = True
    
    def run(self):
        """运行交互式调试器"""
        print("\n" + "="*60)
        print("🐛 Aegis 工作流交互式调试器")
        print("="*60)
        print("输入 'help' 查看可用命令")
        print("="*60 + "\n")
        
        self.debugger.print_status()
        
        while self.running:
            try:
                command = input("debugger> ").strip()
                if not command:
                    continue
                
                self._execute_command(command)
                
            except KeyboardInterrupt:
                print("\n\n⚠️  按 Ctrl+C 再次退出，或输入 'quit' 退出")
                continue
            except Exception as e:
                print(f"❌ 错误: {str(e)}")
    
    def _execute_command(self, command: str):
        """执行命令"""
        parts = command.split()
        cmd = parts[0].lower()
        args = parts[1:]
        
        if cmd == "help" or cmd == "h":
            self._show_help()
        
        elif cmd == "step" or cmd == "s":
            result = self.debugger.step_over()
            self._print_result(result)
            self.debugger.print_status()
        
        elif cmd == "continue" or cmd == "c":
            result = self.debugger.continue_execution()
            self._print_result(result)
            self.debugger.print_status()
        
        elif cmd == "breakpoint" or cmd == "b":
            if not args:
                print("用法: breakpoint <node_id>")
            else:
                self.debugger.add_breakpoint(args[0])
        
        elif cmd == "remove" or cmd == "r":
            if not args:
                print("用法: remove <node_id>")
            else:
                self.debugger.remove_breakpoint(args[0])
        
        elif cmd == "breakpoints" or cmd == "bl":
            breakpoints = self.debugger.list_breakpoints()
            if breakpoints:
                print("\n🔴 断点列表:")
                for bp in breakpoints:
                    print(f"  - {bp}")
            else:
                print("\n⚪ 没有设置断点")
        
        elif cmd == "clear":
            self.debugger.clear_breakpoints()
        
        elif cmd == "status" or cmd == "st":
            self.debugger.print_status()
        
        elif cmd == "variables" or cmd == "v":
            self.debugger.print_variables()
        
        elif cmd == "results" or cmd == "res":
            self.debugger.print_node_results()
        
        elif cmd == "set":
            if len(args) < 2:
                print("用法: set <变量名> <值>")
            else:
                var_name = args[0]
                var_value = " ".join(args[1:])
                # 尝试解析为JSON
                try:
                    var_value = json.loads(var_value)
                except:
                    pass
                self.debugger.set_variable(var_name, var_value)
        
        elif cmd == "get":
            if not args:
                print("用法: get <变量名>")
            else:
                var_name = args[0]
                value = self.debugger.get_variable(var_name)
                print(f"\n{var_name} = {json.dumps(value, indent=2, ensure_ascii=False, default=str)}")
        
        elif cmd == "rollback" or cmd == "rb":
            if not args:
                print("用法: rollback <node_id>")
            else:
                self.debugger.rollback_to_node(args[0])
                self.debugger.print_status()
        
        elif cmd == "restart":
            self.debugger.restart()
            print("🔄 调试会话已重启")
            self.debugger.print_status()
        
        elif cmd == "save":
            if not args:
                print("用法: save <文件路径>")
            else:
                self.debugger.save_session(args[0])
        
        elif cmd == "snapshot" or cmd == "snap":
            if args and args[0].isdigit():
                index = int(args[0])
                snapshot = self.debugger.get_snapshot(index)
            else:
                snapshot = self.debugger.get_snapshot()
            
            if snapshot:
                print(json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=False, default=str))
            else:
                print("⚠️  没有可用的快照")
        
        elif cmd == "node" or cmd == "n":
            if not args:
                print("用法: node <node_id>")
            else:
                self.debugger.print_node_info(args[0])
        
        elif cmd == "update" or cmd == "u":
            if len(args) < 3:
                print("用法: update <node_id> <属性> <值>")
                print("示例: update api_call timeout 60")
                print("      update api_call url https://new-api.com")
            else:
                node_id = args[0]
                key = args[1]
                value = " ".join(args[2:])
                
                # 尝试解析为JSON
                try:
                    value = json.loads(value)
                except:
                    pass
                
                # 更新节点配置
                success = self.debugger.update_node(node_id, {"config": {key: value}})
                if success:
                    print(f"✅ 节点 {node_id} 的 {key} 已更新为: {value}")
        
        elif cmd == "update-config" or cmd == "uc":
            if len(args) < 2:
                print("用法: update-config <node_id> <JSON配置>")
                print("示例: update-config api_call '{\"timeout\": 60, \"retry\": 3}'")
            else:
                node_id = args[0]
                config_str = " ".join(args[1:])
                
                try:
                    config = json.loads(config_str)
                    success = self.debugger.update_node_config(node_id, config)
                    if success:
                        print(f"✅ 节点 {node_id} 的配置已更新")
                        self.debugger.print_node_info(node_id)
                except json.JSONDecodeError as e:
                    print(f"❌ JSON解析错误: {str(e)}")
        
        elif cmd == "update-type" or cmd == "ut":
            if len(args) < 2:
                print("用法: update-type <node_id> <新类型>")
                print("示例: update-type node1 http_request")
            else:
                node_id = args[0]
                node_type = args[1]
                success = self.debugger.update_node_type(node_id, node_type)
                if success:
                    print(f"✅ 节点 {node_id} 类型已更新为: {node_type}")
        
        elif cmd == "quit" or cmd == "q" or cmd == "exit":
            self.running = False
            print("👋 退出调试器")
        
        else:
            print(f"❌ 未知命令: {cmd}，输入 'help' 查看帮助")
    
    def _show_help(self):
        """显示帮助信息"""
        print("\n" + "="*60)
        print("📖 可用命令")
        print("="*60)
        print("执行控制:")
        print("  step, s              单步执行下一个节点")
        print("  continue, c          继续执行直到断点或完成")
        print("  restart              重启调试会话")
        print("  rollback, rb <node>  回退到指定节点")
        print()
        print("断点管理:")
        print("  breakpoint, b <node> 在节点处设置断点")
        print("  remove, r <node>     移除节点断点")
        print("  breakpoints, bl      列出所有断点")
        print("  clear                清除所有断点")
        print()
        print("状态查看:")
        print("  status, st           显示调试器状态")
        print("  variables, v         显示所有变量")
        print("  results, res         显示所有节点结果")
        print("  snapshot, snap [n]   显示快照（可选索引）")
        print()
        print("变量操作:")
        print("  set <name> <value>   设置变量")
        print("  get <name>           获取变量值")
        print()
        print("节点操作:")
        print("  node, n <node_id>    查看节点信息")
        print("  update, u <node> <key> <value>  更新节点配置项")
        print("  update-config, uc <node> <json> 批量更新节点配置")
        print("  update-type, ut <node> <type>   更新节点类型")
        print()
        print("会话管理:")
        print("  save <file>          保存调试会话")
        print()
        print("其他:")
        print("  help, h              显示此帮助")
        print("  quit, q, exit        退出调试器")
        print("="*60 + "\n")
    
    def _print_result(self, result: Dict[str, Any]):
        """打印执行结果"""
        status = result.get("status")
        
        if status == "success":
            print(f"\n✅ 节点执行成功: {result['node_id']}")
            if "output" in result:
                output_str = str(result["output"])
                print(f"   输出: {output_str}")
        
        elif status == "failed":
            print(f"\n❌ 节点执行失败: {result['node_id']}")
            print(f"   错误: {result.get('error', 'Unknown error')}")
        
        elif status == "skipped":
            print(f"\n⏭️  节点已跳过: {result['node_id']}")
        
        elif status == "paused":
            print(f"\n🛑 在断点处暂停: {result.get('node_id')}")
        
        elif status == "completed":
            print(f"\n✅ {result.get('message', '工作流执行完成')}")
        
        print()


if __name__ == "__main__":
    # 示例：交互式调试器
    workflow_data = {
        "nodes": [
            {
                "id": "node1",
                "type": "log_message",
                "data": {
                    "config": {
                        "message": "第一个节点"
                    }
                }
            },
            {
                "id": "node2",
                "type": "log_message",
                "data": {
                    "config": {
                        "message": "第二个节点: ${node1}"
                    }
                }
            },
            {
                "id": "node3",
                "type": "log_message",
                "data": {
                    "config": {
                        "message": "第三个节点: ${node2}"
                    }
                }
            }
        ],
        "edges": [
            {"id": "e1", "source": "node1", "target": "node2"},
            {"id": "e2", "source": "node2", "target": "node3"}
        ]
    }
    
    # 运行交互式调试器
    interactive = InteractiveDebugger(workflow_data)
    interactive.run()
