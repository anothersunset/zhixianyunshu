package com.zhiqian.common;

import lombok.AllArgsConstructor;
import lombok.Data;

import java.time.Instant;

@Data
@AllArgsConstructor
public class Result<T> {
    private int code;
    private String message;
    private T data;
    private Instant timestamp;

    public static <T> Result<T> ok(T data) {
        return new Result<>(0, "ok", data, Instant.now());
    }

    public static <T> Result<T> fail(int code, String message) {
        return new Result<>(code, message, null, Instant.now());
    }
}
