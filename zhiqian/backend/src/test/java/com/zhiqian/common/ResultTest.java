package com.zhiqian.common;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * v2-step-17: Result 通用返回体单元测试。
 */
class ResultTest {

    @Test
    void okWithData() {
        Result<String> r = Result.ok("hello");
        assertEquals(0, r.getCode());
        assertEquals("hello", r.getData());
        assertNotNull(r.getMessage());
    }

    @Test
    void okWithNull() {
        Result<Object> r = Result.ok(null);
        assertEquals(0, r.getCode());
        assertNull(r.getData());
    }

    @Test
    void failCarriesCodeAndMessage() {
        Result<Void> r = Result.fail(500, "oops");
        assertEquals(500, r.getCode());
        assertEquals("oops", r.getMessage());
        assertNull(r.getData());
    }

    @Test
    void failWithDifferentCodes() {
        Result<Void> r400 = Result.fail(400, "bad request");
        Result<Void> r404 = Result.fail(404, "not found");
        assertEquals(400, r400.getCode());
        assertEquals(404, r404.getCode());
        assertNotEquals(r400.getCode(), r404.getCode());
    }
}
