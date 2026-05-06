package com.example.aichat.model;

import com.fasterxml.jackson.annotation.JsonProperty;

public record GenerateRequest(
        String message,
        @JsonProperty("conversation_id") String conversationId,
        boolean stream
) {
    public GenerateRequest(String message, String conversationId) {
        this(message, conversationId, true);
    }
}
