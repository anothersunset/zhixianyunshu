package com.zhiqian.task;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class TaskExecutionServiceTest {
    @Test
    void formatsFailedStageIntoReadableErrorMessage() {
        assertThat(TaskExecutionService.failureMessage("05-critic"))
            .isEqualTo("pipeline failed at stage: 05-critic");
    }

    @Test
    void keepsNullErrorMessageForSuccessfulRuns() {
        assertThat(TaskExecutionService.failureMessage(null)).isNull();
    }
}
