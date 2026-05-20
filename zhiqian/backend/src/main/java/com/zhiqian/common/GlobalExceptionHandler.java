package com.zhiqian.common;

import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Result<Void>> badArg(IllegalArgumentException e) {
        return ResponseEntity.badRequest().body(Result.fail(400, e.getMessage()));
    }

    @ExceptionHandler(AccessDeniedException.class)
    public ResponseEntity<Result<Void>> denied(AccessDeniedException e) {
        return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Result.fail(403, "无权限"));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Result<Void>> error(Exception e) {
        log.error("unhandled error", e);
        return ResponseEntity.internalServerError().body(Result.fail(500, e.getMessage()));
    }
}
