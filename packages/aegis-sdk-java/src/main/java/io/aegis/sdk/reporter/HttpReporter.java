package io.aegis.sdk.reporter;

import io.aegis.sdk.model.AegisEvent;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

/**
 * HTTP 实时推送上报器 (上报给 Local Companion 127.0.0.1:8989 或 Aegis Server)
 */
public class HttpReporter implements AegisReporter {
    private final String endpoint;
    private final String token;
    private final HttpClient httpClient;

    public HttpReporter(String targetUrl, String token) {
        String cleanUrl = targetUrl.endsWith("/") ? targetUrl.substring(0, targetUrl.length() - 1) : targetUrl;
        if (!cleanUrl.endsWith("/events") && !cleanUrl.endsWith("/api/v1/events")) {
            this.endpoint = cleanUrl + "/api/v1/events";
        } else {
            this.endpoint = cleanUrl;
        }
        this.token = token;
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofMillis(1500))
                .build();
    }

    @Override
    public void report(AegisEvent event) {
        try {
            HttpRequest.Builder builder = HttpRequest.newBuilder()
                    .uri(URI.create(this.endpoint))
                    .timeout(Duration.ofMillis(1500))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(event.toJson()));

            if (token != null && !token.isBlank()) {
                builder.header("Authorization", "Bearer " + token);
            }

            httpClient.sendAsync(builder.build(), HttpResponse.BodyHandlers.discarding());
        } catch (Exception ignored) {
            // Fail-safe: 本地不可达或网络中断不影响测试本身的执行结果
        }
    }
}
