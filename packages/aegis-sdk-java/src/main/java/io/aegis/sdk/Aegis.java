package io.aegis.sdk;

import io.aegis.sdk.model.AegisEvent;
import io.aegis.sdk.reporter.AegisReporter;
import io.aegis.sdk.reporter.CompositeReporter;
import io.aegis.sdk.reporter.ConsoleReporter;
import io.aegis.sdk.reporter.HttpReporter;

import java.util.HashMap;
import java.util.Map;

/**
 * Aegis Java SDK 统一入口
 */
public final class Aegis {
    private static final CompositeReporter COMPOSITE_REPORTER = new CompositeReporter();
    private static final ThreadLocal<Map<String, String>> CURRENT_CASE_CTX = new ThreadLocal<>();
    private static final ThreadLocal<Map<String, Object>> CURRENT_STEP_EVIDENCE = new ThreadLocal<>();
    private static volatile String globalRunId = "RUN-" + (System.currentTimeMillis() / 1000);

    static {
        // 默认注册本地彩色控制台输出
        COMPOSITE_REPORTER.addReporter(new ConsoleReporter());

        // 读取环境变量自动注册 Local Companion / Server 上报
        String serverUrl = System.getenv("AEGIS_SERVER_URL");
        if (serverUrl == null || serverUrl.isBlank()) {
            serverUrl = "http://127.0.0.1:8989"; // 默认连接本地伴侣端
        }
        String token = System.getenv("AEGIS_TOKEN");
        COMPOSITE_REPORTER.addReporter(new HttpReporter(serverUrl, token));
    }

    private Aegis() {}

    public static void setRunId(String runId) {
        globalRunId = runId;
    }

    public static String getRunId() {
        return globalRunId;
    }

    public static void addReporter(AegisReporter reporter) {
        COMPOSITE_REPORTER.addReporter(reporter);
    }

    public static void setCurrentCase(Map<String, String> meta) {
        CURRENT_CASE_CTX.set(meta);
    }

    public static Map<String, String> getCurrentCase() {
        return CURRENT_CASE_CTX.get();
    }

    public static void clearCurrentCase() {
        CURRENT_CASE_CTX.remove();
        CURRENT_STEP_EVIDENCE.remove();
    }

    public static void emitEvent(AegisEvent event) {
        COMPOSITE_REPORTER.report(event);
    }

    /**
     * 在当前步骤内动态附加测试证据 (如接口响应字段、数据库记录)
     */
    public static void attachEvidence(String key, Object value) {
        Map<String, Object> evidence = CURRENT_STEP_EVIDENCE.get();
        if (evidence != null) {
            evidence.put(key, value);
        }
    }

    /**
     * 步骤上下文封装: Aegis.step("步骤说明", () -> { ... });
     */
    public static void step(String stepName, StepRunnable action) {
        step(stepName, null, action);
    }

    /**
     * 带初始证据的步骤上下文封装
     */
    public static void step(String stepName, Map<String, Object> initialEvidence, StepRunnable action) {
        Map<String, Object> evidence = new HashMap<>();
        if (initialEvidence != null) {
            evidence.putAll(initialEvidence);
        }
        CURRENT_STEP_EVIDENCE.set(evidence);

        Map<String, String> caseMeta = getCurrentCase();
        long startTime = System.currentTimeMillis();

        // 触发 STEP_START 事件
        AegisEvent startEvent = buildEvent("STEP_START", caseMeta);
        startEvent.setStepName(stepName);
        startEvent.setStatus("RUNNING");
        startEvent.setEvidence(new HashMap<>(evidence));
        emitEvent(startEvent);

        Throwable error = null;
        try {
            action.run();
        } catch (Throwable t) {
            error = t;
        } finally {
            long durationMs = System.currentTimeMillis() - startTime;
            Map<String, Object> finalEvidence = CURRENT_STEP_EVIDENCE.get();
            CURRENT_STEP_EVIDENCE.remove();

            AegisEvent endEvent = buildEvent("STEP_END", caseMeta);
            endEvent.setStepName(stepName);
            endEvent.setDurationMs(durationMs);
            endEvent.setEvidence(finalEvidence != null ? finalEvidence : new HashMap<>());

            if (error != null) {
                endEvent.setStatus("FAILED");
                endEvent.setError(error.getMessage() != null ? error.getMessage() : error.toString());
                emitEvent(endEvent);
                sneakyThrow(error);
            } else {
                endEvent.setStatus("PASSED");
                emitEvent(endEvent);
            }
        }
    }

    public static AegisEvent buildEvent(String eventType, Map<String, String> caseMeta) {
        AegisEvent event = new AegisEvent();
        event.setEventType(eventType);
        event.setRunId(globalRunId);
        if (caseMeta != null) {
            event.setCaseId(caseMeta.get("id"));
            event.setReqId(caseMeta.get("req"));
            event.setRisk(caseMeta.get("risk"));
            event.setTitle(caseMeta.get("title"));
            event.setPriority(caseMeta.get("priority"));
            event.setFeature(caseMeta.get("feature"));
            event.setEpic(caseMeta.get("epic"));
        }
        return event;
    }

    @SuppressWarnings("unchecked")
    private static <E extends Throwable> void sneakyThrow(Throwable e) throws E {
        throw (E) e;
    }
}
