package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestLocalCompanionServer(t *testing.T) {
	hub := NewHub()
	pm := NewProcessManager(hub)
	server := NewServer(hub, pm)
	handler := server.SetupRoutes()

	// 1. 测试 Healthcheck 端点
	t.Run("Healthcheck", func(t *testing.T) {
		req := httptest.NewRequest(http.MethodGet, "/health", nil)
		rec := httptest.NewRecorder()

		handler.ServeHTTP(rec, req)

		if rec.Code != http.StatusOK {
			t.Fatalf("expected 200 OK, got %d", rec.Code)
		}

		var body map[string]any
		if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
			t.Fatalf("failed to decode response: %v", err)
		}
		if body["status"] != "ok" || body["service"] != "Aegis Local Companion" {
			t.Fatalf("unexpected health response: %v", body)
		}
	})

	// 2. 测试 SDK 事件接收 (POST /api/v1/events)
	t.Run("ReceiveEvents", func(t *testing.T) {
		eventData := map[string]any{
			"eventType":  "STEP_END",
			"runId":      "RUN-TEST-001",
			"caseId":     "TC-SMS-001",
			"reqId":      "REQ-224",
			"risk":       "短信通道被恶意刷爆导致资损",
			"stepName":   "步骤 1: 验证短信限流",
			"status":     "PASSED",
			"durationMs": 35,
			"evidence":   map[string]any{"status_code": 429},
		}
		payload, _ := json.Marshal(eventData)

		req := httptest.NewRequest(http.MethodPost, "/api/v1/events", bytes.NewBuffer(payload))
		req.Header.Set("Content-Type", "application/json")
		rec := httptest.NewRecorder()

		handler.ServeHTTP(rec, req)

		if rec.Code != http.StatusOK {
			t.Fatalf("expected 200 OK, got %d", rec.Code)
		}

		var resp map[string]string
		if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
			t.Fatalf("failed to decode response: %v", err)
		}
		if resp["status"] != "received" {
			t.Fatalf("expected status received, got %s", resp["status"])
		}
	})

	// 3. 测试本地进程任务触发 (POST /api/v1/run)
	t.Run("RunLocalTask", func(t *testing.T) {
		taskData := TaskRequest{
			RunnerType: "shell",
			Command:    "echo Hello-Aegis",
			RunID:      "RUN-TEST-001",
		}
		payload, _ := json.Marshal(taskData)

		req := httptest.NewRequest(http.MethodPost, "/api/v1/run", bytes.NewBuffer(payload))
		req.Header.Set("Content-Type", "application/json")
		rec := httptest.NewRecorder()

		handler.ServeHTTP(rec, req)

		if rec.Code != http.StatusOK {
			t.Fatalf("expected 200 OK, got %d", rec.Code)
		}

		var resp map[string]string
		if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
			t.Fatalf("failed to decode response: %v", err)
		}
		if resp["status"] != "started" {
			t.Fatalf("expected status started, got %s", resp["status"])
		}
	})
}
