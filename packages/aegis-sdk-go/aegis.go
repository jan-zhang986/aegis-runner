package aegis

import (
	"fmt"
	"sync"
	"testing"
	"time"
)

var (
	defaultReporter = NewCompositeReporter()
	globalRunID     = fmt.Sprintf("RUN-%d", time.Now().Unix())
)

// SetRunID 设置批次执行 RunID
func SetRunID(runID string) {
	globalRunID = runID
}

// AddReporter 注册自定义上报器
func AddReporter(r Reporter) {
	defaultReporter.AddReporter(r)
}

// Meta 用例元数据描述
type Meta struct {
	ID          string   `json:"id"`
	Req         string   `json:"req"`
	Title       string   `json:"title"`
	Risk        string   `json:"risk"`
	Priority    string   `json:"priority"`
	Feature     string   `json:"feature"`
	Epic        string   `json:"epic"`
	Tags        []string `json:"tags"`
	Description string   `json:"description"`
}

// Context 用例执行上下文，用于在测试函数中声明步骤与证据
type Context struct {
	t        *testing.T
	meta     Meta
	mu       sync.Mutex
	evidence map[string]any
}

// AttachEvidence 动态附加当前步骤的证据
func (c *Context) AttachEvidence(key string, val any) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.evidence == nil {
		c.evidence = make(map[string]any)
	}
	c.evidence[key] = val
}

// Step 执行测试步骤上下文
func (c *Context) Step(stepName string, fn func()) {
	c.StepWithEvidence(stepName, nil, fn)
}

// StepWithEvidence 执行带有初始证据的步骤上下文
func (c *Context) StepWithEvidence(stepName string, initialEvidence map[string]any, fn func()) {
	c.mu.Lock()
	c.evidence = make(map[string]any)
	if initialEvidence != nil {
		for k, v := range initialEvidence {
			c.evidence[k] = v
		}
	}
	c.mu.Unlock()

	startEv := NewEvent(EventStepStart)
	startEv.RunID = globalRunID
	startEv.CaseID = c.meta.ID
	startEv.ReqID = c.meta.Req
	startEv.Risk = c.meta.Risk
	startEv.Title = c.meta.Title
	startEv.Feature = c.meta.Feature
	startEv.Epic = c.meta.Epic
	startEv.StepName = stepName
	startEv.Status = "RUNNING"
	defaultReporter.Report(startEv)

	startTime := time.Now()
	var stepErr error

	defer func() {
		if r := recover(); r != nil {
			stepErr = fmt.Errorf("%v", r)
		}

		durationMs := time.Since(startTime).Milliseconds()
		endEv := NewEvent(EventStepEnd)
		endEv.RunID = globalRunID
		endEv.CaseID = c.meta.ID
		endEv.ReqID = c.meta.Req
		endEv.Risk = c.meta.Risk
		endEv.Title = c.meta.Title
		endEv.Feature = c.meta.Feature
		endEv.Epic = c.meta.Epic
		endEv.StepName = stepName
		endEv.DurationMs = durationMs

		c.mu.Lock()
		endEv.Evidence = c.evidence
		c.mu.Unlock()

		if stepErr != nil || c.t.Failed() {
			endEv.Status = "FAILED"
			if stepErr != nil {
				endEv.Error = stepErr.Error()
			} else {
				endEv.Error = "Step assertion failed"
			}
			defaultReporter.Report(endEv)
			if stepErr != nil {
				panic(stepErr) // 向上抛出保证测试框架捕获
			}
		} else {
			endEv.Status = "PASSED"
			defaultReporter.Report(endEv)
		}
	}()

	fn()
}

// Case 原生 Go 测试入口封装，与 testing.T 深度融合
func Case(t *testing.T, meta Meta, fn func(c *Context)) {
	if meta.Priority == "" {
		meta.Priority = "P1"
	}
	if meta.Title == "" {
		meta.Title = t.Name()
	}

	caseCtx := &Context{
		t:        t,
		meta:     meta,
		evidence: make(map[string]any),
	}

	// 触发 CASE_START
	startEv := NewEvent(EventCaseStart)
	startEv.RunID = globalRunID
	startEv.CaseID = meta.ID
	startEv.ReqID = meta.Req
	startEv.Risk = meta.Risk
	startEv.Title = meta.Title
	startEv.Priority = meta.Priority
	startEv.Feature = meta.Feature
	startEv.Epic = meta.Epic
	defaultReporter.Report(startEv)

	startTime := time.Now()

	defer func() {
		durationMs := time.Since(startTime).Milliseconds()
		endEv := NewEvent(EventCaseEnd)
		endEv.RunID = globalRunID
		endEv.CaseID = meta.ID
		endEv.ReqID = meta.Req
		endEv.Risk = meta.Risk
		endEv.Title = meta.Title
		endEv.Priority = meta.Priority
		endEv.Feature = meta.Feature
		endEv.Epic = meta.Epic
		endEv.DurationMs = durationMs

		if t.Failed() {
			endEv.Status = "FAILED"
		} else {
			endEv.Status = "PASSED"
		}
		defaultReporter.Report(endEv)
	}()

	fn(caseCtx)
}
