package io.aegis.sdk.junit;

import io.aegis.sdk.Aegis;
import io.aegis.sdk.annotation.AegisCase;
import io.aegis.sdk.annotation.AegisEpic;
import io.aegis.sdk.annotation.AegisFeature;
import io.aegis.sdk.model.AegisEvent;
import org.junit.jupiter.api.extension.*;

import java.lang.reflect.Method;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

/**
 * JUnit 5 官方扩展：自动无侵入拦截测试用例执行生命周期
 */
public class AegisExtension implements BeforeEachCallback, AfterEachCallback, TestExecutionExceptionHandler {

    private static final ExtensionContext.Namespace NAMESPACE = ExtensionContext.Namespace.create("io.aegis.sdk");

    @Override
    public void beforeEach(ExtensionContext context) {
        Optional<Method> testMethodOpt = context.getTestMethod();
        if (testMethodOpt.isEmpty()) {
            return;
        }

        Method testMethod = testMethodOpt.get();
        AegisCase caseAnno = testMethod.getAnnotation(AegisCase.class);

        Map<String, String> meta = new HashMap<>();
        if (caseAnno != null) {
            meta.put("id", caseAnno.id());
            meta.put("req", caseAnno.req());
            meta.put("title", caseAnno.title().isBlank() ? testMethod.getName() : caseAnno.title());
            meta.put("risk", caseAnno.risk());
            meta.put("priority", caseAnno.priority());
        } else {
            meta.put("id", context.getUniqueId());
            meta.put("title", testMethod.getName());
            meta.put("priority", "P2");
        }

        // 提取 Feature 与 Epic
        AegisFeature featureAnno = testMethod.getAnnotation(AegisFeature.class);
        if (featureAnno == null) {
            featureAnno = context.getRequiredTestClass().getAnnotation(AegisFeature.class);
        }
        if (featureAnno != null) {
            meta.put("feature", featureAnno.value());
        }

        AegisEpic epicAnno = testMethod.getAnnotation(AegisEpic.class);
        if (epicAnno == null) {
            epicAnno = context.getRequiredTestClass().getAnnotation(AegisEpic.class);
        }
        if (epicAnno != null) {
            meta.put("epic", epicAnno.value());
        }

        Aegis.setCurrentCase(meta);
        context.getStore(NAMESPACE).put("startTime", System.currentTimeMillis());

        // 发送 CASE_START 事件
        AegisEvent startEvent = Aegis.buildEvent("CASE_START", meta);
        Aegis.emitEvent(startEvent);
    }

    @Override
    public void afterEach(ExtensionContext context) {
        Boolean failed = context.getStore(NAMESPACE).get("failed", Boolean.class);
        if (failed == null || !failed) {
            completeCase(context, "PASSED", null);
        }
        Aegis.clearCurrentCase();
    }

    @Override
    public void handleTestExecutionException(ExtensionContext context, Throwable throwable) throws Throwable {
        context.getStore(NAMESPACE).put("failed", true);
        completeCase(context, "FAILED", throwable.getMessage() != null ? throwable.getMessage() : throwable.toString());
        throw throwable;
    }

    private void completeCase(ExtensionContext context, String status, String error) {
        Long startTime = context.getStore(NAMESPACE).get("startTime", Long.class);
        long duration = startTime != null ? (System.currentTimeMillis() - startTime) : 0;

        Map<String, String> meta = Aegis.getCurrentCase();
        AegisEvent endEvent = Aegis.buildEvent("CASE_END", meta);
        endEvent.setStatus(status);
        endEvent.setDurationMs(duration);
        endEvent.setError(error);

        Aegis.emitEvent(endEvent);
    }
}
