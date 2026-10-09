package main

import (
	"bufio"
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"strings"
	"sync"
	"time"
)

// TaskRequest 前端发起的本地执行任务定义
type TaskRequest struct {
	RunnerType string            `json:"runnerType"` // "pytest" | "go" | "playwright" | "maven" | "shell"
	Command    string            `json:"command"`    // 具体命令参数，如 "pytest tests/api/auth -v"
	Cwd        string            `json:"cwd"`        // 执行工作目录
	Env        map[string]string `json:"env"`        // 自定义环境变量 (如 HEADED=true)
	RunID      string            `json:"runId"`      // 批次标识
}

// ProcessManager 本地进程管理器
type ProcessManager struct {
	mu        sync.Mutex
	activeCmd *exec.Cmd
	cancel    context.CancelFunc
	hub       *Hub
}

func NewProcessManager(hub *Hub) *ProcessManager {
	return &ProcessManager{
		hub: hub,
	}
}

// RunTask 启动本地测试进程并将日志流式广播回前端
func (pm *ProcessManager) RunTask(req TaskRequest) error {
	pm.mu.Lock()
	if pm.activeCmd != nil {
		pm.mu.Unlock()
		return errors.New("a task is already running; please stop it first")
	}

	ctx, cancel := context.WithCancel(context.Background())
	pm.cancel = cancel

	runID := req.RunID
	if runID == "" {
		runID = fmt.Sprintf("LOCAL-RUN-%d", time.Now().Unix())
	}

	// 解析命令行参数
	cmdParts := strings.Fields(req.Command)
	if len(cmdParts) == 0 {
		pm.mu.Unlock()
		cancel()
		return errors.New("empty command provided")
	}

	cmd := exec.CommandContext(ctx, cmdParts[0], cmdParts[1:]...)
	if req.Cwd != "" {
		cmd.Dir = req.Cwd
	}

	// 继承当前系统环境并注入 Aegis 本地通信变量
	cmd.Env = append(os.Environ(),
		fmt.Sprintf("AEGIS_SERVER_URL=http://127.0.0.1:8989"),
		fmt.Sprintf("AEGIS_RUN_ID=%s", runID),
	)
	for k, v := range req.Env {
		cmd.Env = append(cmd.Env, fmt.Sprintf("%s=%s", k, v))
	}

	stdoutPipe, err := cmd.StdoutPipe()
	if err != nil {
		pm.mu.Unlock()
		cancel()
		return err
	}

	stderrPipe, err := cmd.StderrPipe()
	if err != nil {
		pm.mu.Unlock()
		cancel()
		return err
	}

	if err := cmd.Start(); err != nil {
		pm.mu.Unlock()
		cancel()
		return fmt.Errorf("failed to start command: %w", err)
	}

	pm.activeCmd = cmd
	pm.mu.Unlock()

	pm.hub.Broadcast("system", fmt.Sprintf("🚀 Started local task: %s (PID: %d, RunID: %s)", req.Command, cmd.Process.Pid, runID), runID)

	// 流式读取 stdout 与 stderr
	var wg sync.WaitGroup
	wg.Add(2)

	go func() {
		defer wg.Done()
		streamOutput(stdoutPipe, "stdout", runID, pm.hub)
	}()

	go func() {
		defer wg.Done()
		streamOutput(stderrPipe, "stderr", runID, pm.hub)
	}()

	// 异步等待进程执行完毕并清理
	go func() {
		wg.Wait()
		waitErr := cmd.Wait()

		pm.mu.Lock()
		pm.activeCmd = nil
		pm.cancel = nil
		pm.mu.Unlock()

		if waitErr != nil {
			pm.hub.Broadcast("system", fmt.Sprintf("❌ Local execution finished with error: %v", waitErr), runID)
		} else {
			pm.hub.Broadcast("system", "✅ Local execution finished successfully (Exit Code: 0)", runID)
		}
	}()

	return nil
}

// StopActiveTask 终止当前正在执行的本地进程
func (pm *ProcessManager) StopActiveTask() bool {
	pm.mu.Lock()
	defer pm.mu.Unlock()

	if pm.cancel != nil {
		pm.cancel()
		if pm.activeCmd != nil && pm.activeCmd.Process != nil {
			_ = pm.activeCmd.Process.Kill()
		}
		pm.activeCmd = nil
		pm.cancel = nil
		pm.hub.Broadcast("system", "⏹ Active task stopped by user", "")
		return true
	}
	return false
}

// streamOutput 将管道内容逐行推流至 WebSocket/SSE
func streamOutput(pipe io.Reader, streamType string, runID string, hub *Hub) {
	scanner := bufio.NewScanner(pipe)
	for scanner.Scan() {
		text := scanner.Text()
		hub.Broadcast(streamType, text, runID)
	}
}
