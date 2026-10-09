package aegis

import (
	"bytes"
	"fmt"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"
)

// Reporter 事件上报器接口
type Reporter interface {
	Report(event *Event)
	Close()
}

// ConsoleReporter 控制台彩色输出上报器
type ConsoleReporter struct{}

func (r *ConsoleReporter) Report(e *Event) {
	switch e.EventType {
	case string(EventCaseStart):
		riskInfo := ""
		if e.Risk != "" {
			riskInfo = fmt.Sprintf(" [风险: %s]", e.Risk)
		}
		fmt.Printf("\n🚀 [Aegis Case Start] %s: %s%s\n", e.CaseID, e.Title, riskInfo)
	case string(EventCaseEnd):
		icon := "✅"
		if e.Status != "PASSED" {
			icon = "❌"
		}
		fmt.Printf("%s [Aegis Case End] %s => %s (%dms)\n", icon, e.CaseID, e.Status, e.DurationMs)
	case string(EventStepStart):
		fmt.Printf("   ▶ %s ... ", e.StepName)
	case string(EventStepEnd):
		evidenceStr := ""
		if len(e.Evidence) > 0 {
			evidenceStr = fmt.Sprintf(" | 证据: %v", e.Evidence)
		}
		if e.Status == "PASSED" {
			fmt.Printf("\033[32m✓ PASSED\033[0m (%dms)%s\n", e.DurationMs, evidenceStr)
		} else {
			fmt.Printf("\033[31m✗ FAILED\033[0m (%dms) Error: %s\n", e.DurationMs, e.Error)
		}
	}
}

func (r *ConsoleReporter) Close() {}

// HTTPReporter HTTP 实时推送上报器
type HTTPReporter struct {
	endpoint string
	token    string
	client   *http.Client
}

func NewHTTPReporter(targetURL, token string) *HTTPReporter {
	targetURL = strings.TrimRight(targetURL, "/")
	endpoint := targetURL
	if !strings.HasSuffix(endpoint, "/events") && !strings.HasSuffix(endpoint, "/api/v1/events") {
		endpoint = targetURL + "/api/v1/events"
	}
	return &HTTPReporter{
		endpoint: endpoint,
		token:    token,
		client: &http.Client{
			Timeout: 1500 * time.Millisecond,
		},
	}
}

func (r *HTTPReporter) Report(e *Event) {
	data, err := e.ToJSON()
	if err != nil {
		return
	}

	go func() {
		req, err := http.NewRequest(http.MethodPost, r.endpoint, bytes.NewBuffer(data))
		if err != nil {
			return
		}
		req.Header.Set("Content-Type", "application/json")
		if r.token != "" {
			req.Header.Set("Authorization", "Bearer "+r.token)
		}
		resp, err := r.client.Do(req)
		if err == nil && resp != nil {
			_ = resp.Body.Close()
		}
	}()
}

func (r *HTTPReporter) Close() {}

// CompositeReporter 复合分发器
type CompositeReporter struct {
	mu        sync.RWMutex
	reporters []Reporter
}

func NewCompositeReporter() *CompositeReporter {
	cr := &CompositeReporter{}
	cr.AddReporter(&ConsoleReporter{})

	serverURL := os.Getenv("AEGIS_SERVER_URL")
	if serverURL == "" {
		serverURL = "http://127.0.0.1:8989"
	}
	token := os.Getenv("AEGIS_TOKEN")
	cr.AddReporter(NewHTTPReporter(serverURL, token))
	return cr
}

func (c *CompositeReporter) AddReporter(r Reporter) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.reporters = append(c.reporters, r)
}

func (c *CompositeReporter) Report(e *Event) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	for _, r := range c.reporters {
		r.Report(e)
	}
}

func (c *CompositeReporter) Close() {
	c.mu.Lock()
	defer c.mu.Unlock()
	for _, r := range c.reporters {
		r.Close()
	}
}
