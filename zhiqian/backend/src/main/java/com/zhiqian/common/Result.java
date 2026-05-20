package com.zhiqian.common;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Data;

@Data
@JsonInclude(JsonInclude.Include.NON_NULL)
public class Result<T> {
	private int code;
	private String message;
	private T data;
	private long timestamp = System.currentTimeMillis();

	public static <T> Result<T> ok(T data) {
		Result<T> r = new Result<>();
		r.code = 0;
		r.message = "ok";
		r.data = data;
		return r;
	}

	public static <T> Result<T> error(int code, String message) {
		Result<T> r = new Result<>();
		r.code = code;
		r.message = message;
		return r;
	}
}
