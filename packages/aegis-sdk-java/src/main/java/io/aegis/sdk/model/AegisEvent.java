package io.aegis.sdk.model;

import java.util.HashMap;
import java.util.Map;

/**
 * 跨语言标准 Aegis 事件实体，与 Python、Go 保持 100% 对齐
 */
public class AegisEvent {
    private String eventType;
    private String runId;
    private String caseId;
    private String reqId;
    private String risk;
    private String title;
    private String priority;
    private String feature;
    private String epic;
    private String stepName;
    private String status;
    private long durationMs;
    private Map<String, Object> evidence = new HashMap<>();
    private String error;
    private long timestamp = System.currentTimeMillis();

    public AegisEvent() {}

    public String getEventType() { return eventType; }
    public void setEventType(String eventType) { this.eventType = eventType; }

    public String getRunId() { return runId; }
    public void setRunId(String runId) { this.runId = runId; }

    public String getCaseId() { return caseId; }
    public void setCaseId(String caseId) { this.caseId = caseId; }

    public String getReqId() { return reqId; }
    public void setReqId(String reqId) { this.reqId = reqId; }

    public String getRisk() { return risk; }
    public void setRisk(String risk) { this.risk = risk; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public String getPriority() { return priority; }
    public void setPriority(String priority) { this.priority = priority; }

    public String getFeature() { return feature; }
    public void setFeature(String feature) { this.feature = feature; }

    public String getEpic() { return epic; }
    public void setEpic(String epic) { this.epic = epic; }

    public String getStepName() { return stepName; }
    public void setStepName(String stepName) { this.stepName = stepName; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public long getDurationMs() { return durationMs; }
    public void setDurationMs(long durationMs) { this.durationMs = durationMs; }

    public Map<String, Object> getEvidence() { return evidence; }
    public void setEvidence(Map<String, Object> evidence) { this.evidence = evidence; }

    public String getError() { return error; }
    public void setError(String error) { this.error = error; }

    public long getTimestamp() { return timestamp; }
    public void setTimestamp(long timestamp) { this.timestamp = timestamp; }

    /**
     * 轻量序列化为符合跨语言标准的 JSON 字符串 (零外部依赖)
     */
    public String toJson() {
        StringBuilder sb = new StringBuilder();
        sb.append("{");
        appendField(sb, "eventType", eventType, true);
        appendField(sb, "runId", runId, false);
        appendField(sb, "caseId", caseId, false);
        appendField(sb, "reqId", reqId, false);
        appendField(sb, "risk", risk, false);
        appendField(sb, "title", title, false);
        appendField(sb, "priority", priority, false);
        appendField(sb, "feature", feature, false);
        appendField(sb, "epic", epic, false);
        appendField(sb, "stepName", stepName, false);
        appendField(sb, "status", status, false);
        sb.append(",\"durationMs\":").append(durationMs);
        sb.append(",\"timestamp\":").append(timestamp);

        if (error != null) {
            appendField(sb, "error", error, false);
        }

        sb.append(",\"evidence\":{");
        if (evidence != null && !evidence.isEmpty()) {
            boolean first = true;
            for (Map.Entry<String, Object> entry : evidence.entrySet()) {
                if (!first) sb.append(",");
                sb.append("\"").append(escape(entry.getKey())).append("\":");
                Object val = entry.getValue();
                if (val instanceof Number || val instanceof Boolean) {
                    sb.append(val);
                } else {
                    sb.append("\"").append(escape(String.valueOf(val))).append("\"");
                }
                first = false;
            }
        }
        sb.append("}");

        sb.append("}");
        return sb.toString();
    }

    private void appendField(StringBuilder sb, String key, String value, boolean isFirst) {
        if (!isFirst) sb.append(",");
        sb.append("\"").append(key).append("\":");
        if (value == null) {
            sb.append("null");
        } else {
            sb.append("\"").append(escape(value)).append("\"");
        }
    }

    private String escape(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\b", "\\b")
                .replace("\f", "\\f")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }
}
