package aegis_test

import (
	"testing"

	"github.com/vanguard-platform/aegis-sdk-go"
)

type mockCollector struct {
	events []*aegis.Event
}

func (m *mockCollector) Report(e *aegis.Event) {
	m.events = append(m.events, e)
}

func (m *mockCollector) Close() {}

func TestSmsRateLimitInGo(t *testing.T) {
	collector := &mockCollector{}
	aegis.AddReporter(collector)

	meta := aegis.Meta{
		ID:       "TC-GO-001",
		Req:      "REQ-224",
		Title:    "高频并发连击请求触发 429 防刷限流 (Go)",
		Risk:     "短信轰炸导致资损与通道被打挂",
		Priority: "P0",
		Feature:  "手机短信验证码登录",
		Epic:     "用户中心",
		Tags:     []string{"smoke", "security"},
	}

	aegis.Case(t, meta, func(c *aegis.Context) {
		c.StepWithEvidence("步骤 1: 模拟 1 秒内发起 10 次短信下发", map[string]any{"concurrent": 10}, func() {
			c.AttachEvidence("redis_key", "rate_limit:sms:13800000001")
		})

		c.Step("步骤 2: 校验首次请求状态码为 HTTP 200", func() {
			c.AttachEvidence("status_code", 200)
		})

		c.Step("步骤 3: 校验后续请求被限流拦截 (HTTP 429)", func() {
			c.AttachEvidence("status_code", 429)
		})
	})

	// 校验捕获的事件
	if len(collector.events) == 0 {
		t.Fatalf("expected events to be captured, got 0")
	}

	hasCaseStart := false
	hasCaseEnd := false
	stepStartCount := 0
	stepEndCount := 0

	for _, e := range collector.events {
		switch e.EventType {
		case "CASE_START":
			hasCaseStart = true
			if e.CaseID != "TC-GO-001" || e.Risk != "短信轰炸导致资损与通道被打挂" {
				t.Errorf("unexpected CASE_START data: %+v", e)
			}
		case "CASE_END":
			hasCaseEnd = true
			if e.Status != "PASSED" {
				t.Errorf("expected CASE_END status PASSED, got %s", e.Status)
			}
		case "STEP_START":
			stepStartCount++
		case "STEP_END":
			stepEndCount++
			if e.StepName == "步骤 1: 模拟 1 秒内发起 10 次短信下发" {
				if e.Evidence["redis_key"] != "rate_limit:sms:13800000001" {
					t.Errorf("expected redis_key evidence, got %v", e.Evidence)
				}
			}
		}
	}

	if !hasCaseStart || !hasCaseEnd {
		t.Errorf("missing case start or end event")
	}
	if stepStartCount != 3 || stepEndCount != 3 {
		t.Errorf("expected 3 step starts and ends, got %d starts, %d ends", stepStartCount, stepEndCount)
	}
}
