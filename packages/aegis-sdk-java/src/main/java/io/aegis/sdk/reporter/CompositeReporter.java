package io.aegis.sdk.reporter;

import io.aegis.sdk.model.AegisEvent;

import java.util.ArrayList;
import java.util.List;

public class CompositeReporter implements AegisReporter {
    private final List<AegisReporter> reporters = new ArrayList<>();

    public void addReporter(AegisReporter reporter) {
        if (reporter != null) {
            this.reporters.add(reporter);
        }
    }

    @Override
    public void report(AegisEvent event) {
        for (AegisReporter r : reporters) {
            try {
                r.report(event);
            } catch (Exception ignored) {}
        }
    }

    @Override
    public void close() {
        for (AegisReporter r : reporters) {
            try {
                r.close();
            } catch (Exception ignored) {}
        }
    }
}
