package com.example.aichat.model;

import com.fasterxml.jackson.annotation.JsonProperty;

public record ChatRequest(
        String message,
        @JsonProperty("agentId") String agentId,
        @JsonProperty("conversationId") String conversationId,
        @JsonProperty("messageId") String messageId
) {
}
