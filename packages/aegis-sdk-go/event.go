package aegis

import (
	"encoding/json"
	"time"
)

// EventType 定义 Aegis 事件类型
type EventType string

const (
	EventRunStart  EventType = "RUN_START"
	EventRunEnd    EventType = "RUN_END"
	EventCaseStart EventType = "CASE_START"
	EventCaseEnd   EventType = "CASE_END"
	EventStepStart EventType = "STEP_START"
	EventStepEnd   EventType = "STEP_END"
)

// Event 跨语言标准事件模型
type Event struct {
	EventType  string         `json:"eventType"`
	RunID      string         `json:"runId,omitempty"`
	CaseID     string         `json:"caseId,omitempty"`
	ReqID      string         `json:"reqId,omitempty"`
	Risk       string         `json:"risk,omitempty"`
	Title      string         `json:"title,omitempty"`
	Priority   string         `json:"priority,omitempty"`
	Feature    string         `json:"feature,omitempty"`
	Epic       string         `json:"epic,omitempty"`
	StepName   string         `json:"stepName,omitempty"`
	Status     string         `json:"status,omitempty"`
	DurationMs int64          `json:"durationMs"`
	Evidence   map[string]any `json:"evidence,omitempty"`
	Error      string         `json:"error,omitempty"`
	Timestamp  int64          `json:"timestamp"`
}

// NewEvent 创建带有当前时间戳的标准事件
func NewEvent(eventType EventType) *Event {
	return &Event{
		EventType: string(eventType),
		Evidence:  make(map[string]any),
		Timestamp: time.Now().UnixNano() / int64(time.Millisecond),
	}
}

// ToJSON 序列化为 JSON 字符串
func (e *Event) ToJSON() ([]byte, error) {
	return json.Marshal(e)
}
