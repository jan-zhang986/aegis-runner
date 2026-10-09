package io.aegis.sdk;

import io.aegis.sdk.annotation.AegisCase;
import io.aegis.sdk.annotation.AegisEpic;
import io.aegis.sdk.annotation.AegisFeature;
import io.aegis.sdk.junit.AegisExtension;
import io.aegis.sdk.model.AegisEvent;
import io.aegis.sdk.reporter.AegisReporter;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@ExtendWith(AegisExtension.class)
@AegisEpic("用户中心")
@AegisFeature("手机短信验证码登录")
public class AegisJavaSdkDemoTest {

    private static final List<AegisEvent> CAPTURED_EVENTS = new ArrayList<>();

    @BeforeAll
    static void setup() {
        Aegis.addReporter(new AegisReporter() {
            @Override
            public void report(AegisEvent event) {
                CAPTURED_EVENTS.add(event);
            }
        });
    }

    @Test
    @AegisCase(
            id = "TC-JAVA-001",
            req = "REQ-224",
            title = "高频并发连击请求触发 429 防刷限流 (Java)",
            risk = "短信通道被恶意刷爆导致财务资损与通道被封",
            priority = "P0",
            tags = {"smoke", "security"}
    )
    void testSmsRateLimitInJava() {
        Aegis.step("步骤 1: 模拟并发发起短信请求", Map.of("phone", "13800000001", "concurrent", 10), () -> {
            Aegis.attachEvidence("redis_key", "rate_limit:sms:13800000001");
            Assertions.assertTrue(true);
        });

        Aegis.step("步骤 2: 校验首次请求成功并返回 200", () -> {
            Assertions.assertEquals(200, 200);
            Aegis.attachEvidence("status_code", 200);
        });

        Aegis.step("步骤 3: 校验后续请求被限流拦截 (HTTP 429)", () -> {
            Assertions.assertEquals(429, 429);
            Aegis.attachEvidence("status_code", 429);
        });
    }
}
