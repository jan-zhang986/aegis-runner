package io.aegis.sdk.reporter;

import io.aegis.sdk.model.AegisEvent;

/**
 * 上报器接口
 */
public interface AegisReporter {
    void report(AegisEvent event);
    default void close() {}
}
