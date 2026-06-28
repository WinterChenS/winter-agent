package com.example.aichat.config;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.support.WebExchangeBindException;

import java.util.HashMap;
import java.util.Map;

@ControllerAdvice
public class ValidationErrorHandler {

    @ExceptionHandler(WebExchangeBindException.class)
    public ResponseEntity<Map<String, Object>> handleValidation(WebExchangeBindException ex) {
        Map<String, Object> body = new HashMap<>();
        Map<String, String> errors = new HashMap<>();
        ex.getFieldErrors().forEach(fe -> errors.put(fe.getField(), fe.getDefaultMessage()));
        body.put("status", 422);
        body.put("error", "Validation failed");
        body.put("fields", errors);
        return ResponseEntity.status(422).body(body);
    }
}
