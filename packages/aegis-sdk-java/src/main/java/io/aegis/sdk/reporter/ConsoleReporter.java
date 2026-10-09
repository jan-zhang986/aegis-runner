package io.aegis.sdk.reporter;

import io.aegis.sdk.model.AegisEvent;

/**
 * 本地彩色控制台打屏上报器
 */
public class ConsoleReporter implements AegisReporter {

    @Override
    public void report(AegisEvent event) {
        String type = event.getEventType();
        if ("CASE_START".equals(type)) {
            String risk = event.getRisk() != null ? " [风险: " + event.getRisk() + "]" : "";
            System.out.println("\n🚀 [Aegis Case Start] " + event.getCaseId() + ": " + event.getTitle() + risk);
        } else if ("CASE_END".equals(type)) {
            boolean passed = "PASSED".equals(event.getStatus());
            String icon = passed ? "✅" : "❌";
            System.out.println(icon + " [Aegis Case End] " + event.getCaseId() + " => " + event.getStatus() + " (" + event.getDurationMs() + "ms)");
        } else if ("STEP_START".equals(type)) {
            System.out.print("   ▶ " + event.getStepName() + " ... ");
        } else if ("STEP_END".equals(type)) {
            boolean passed = "PASSED".equals(event.getStatus());
            String evidenceStr = (event.getEvidence() != null && !event.getEvidence().isEmpty()) ? " | 证据: " + event.getEvidence() : "";
            if (passed) {
                System.out.println("\u001B[32m✓ PASSED\u001B[0m (" + event.getDurationMs() + "ms)" + evidenceStr);
            } else {
                System.out.println("\u001B[31m✗ FAILED\u001B[0m (" + event.getDurationMs() + "ms) Error: " + event.getError());
            }
        }
    }
}
