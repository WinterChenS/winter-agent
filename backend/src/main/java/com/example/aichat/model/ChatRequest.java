package com.example.aichat.model;

import com.fasterxml.jackson.annotation.JsonProperty;

public record ChatRequest(
        String message,
        @JsonProperty("conversationId") String conversationId
) {
}
