package io.aegis.sdk;

/**
 * 步骤可执行逻辑（支持抛出任何检查或未检查异常）
 */
@FunctionalInterface
public interface StepRunnable {
    void run() throws Throwable;
}
