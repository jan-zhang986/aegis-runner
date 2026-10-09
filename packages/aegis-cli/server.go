package main

import (
	"encoding/json"
	"io"
	"net/http"
)

type Server struct {
	hub *Hub
	pm  *ProcessManager
}

func NewServer(hub *Hub, pm *ProcessManager) *Server {
	return &Server{
		hub: hub,
		pm:  pm,
	}
}

// corsMiddleware 允许 Web 前端 (如 http://localhost:5173) 跨域调用本地服务
func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")

		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusOK)
			return
		}

		next.ServeHTTP(w, r)
	})
}

// SetupRoutes 注册端点路由
func (s *Server) SetupRoutes() http.Handler {
	mux := http.NewServeMux()

	// 1. 根目录与健康探针
	mux.HandleFunc("/health", s.handleHealth)
	mux.HandleFunc("/", s.handleRoot)

	// 2. SDK 事件接收端点 (Python/Java/Go SDK 上报入口)
	mux.HandleFunc("/api/v1/events", s.handleEvents)

	// 3. 本地进程控制端点 (前端点击运行/停止)
	mux.HandleFunc("/api/v1/run", s.handleRun)
	mux.HandleFunc("/api/v1/stop", s.handleStop)

	// 4. 双通道实时推流 (WebSocket & SSE)
	mux.HandleFunc("/ws", s.hub.HandleWebSocket)
	mux.HandleFunc("/api/v1/stream", s.hub.HandleSSE)

	return corsMiddleware(mux)
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]any{
		"status":  "ok",
		"service": "Aegis Local Companion",
		"version": "1.1.0",
	})
}

func (s *Server) handleRoot(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Write([]byte(`<!DOCTYPE html>
<html>
<head><title>Aegis Local Companion</title><meta charset="utf-8"></head>
<body style="font-family:system-ui;margin:40px;background:#0d1117;color:#c9d1d9;">
  <h2 style="color:#58a6ff;">🚀 Aegis Local Companion (本地执行伴侣)</h2>
  <p>状态: <span style="color:#3fb950;font-weight:bold;">运行中 (Active on 127.0.0.1:8989)</span></p>
  <ul>
    <li>WebSocket 通道: <code>ws://127.0.0.1:8989/ws</code></li>
    <li>SSE 备用通道: <code>http://127.0.0.1:8989/api/v1/stream</code></li>
    <li>SDK 事件接收器: <code>POST http://127.0.0.1:8989/api/v1/events</code></li>
    <li>本地任务驱动器: <code>POST http://127.0.0.1:8989/api/v1/run</code></li>
  </ul>
  <p style="color:#8b949e;">支持本地有头 Playwright 弹窗调试、Python/Java/Go 极速本地调试与流式回显。</p>
</body>
</html>`))
}

func (s *Server) handleEvents(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	var eventPayload map[string]any
	if err := json.Unmarshal(body, &eventPayload); err != nil {
		http.Error(w, "Invalid JSON payload", http.StatusBadRequest)
		return
	}

	runID, _ := eventPayload["runId"].(string)

	// 实时广播给所有前端界面
	s.hub.Broadcast("event", eventPayload, runID)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "received"})
}

func (s *Server) handleRun(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req TaskRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	if err := s.pm.RunTask(req); err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusConflict)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]string{
		"status":  "started",
		"command": req.Command,
		"runId":   req.RunID,
	})
}

func (s *Server) handleStop(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	stopped := s.pm.StopActiveTask()
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]any{
		"stopped": stopped,
	})
}
