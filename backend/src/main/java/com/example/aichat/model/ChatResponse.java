package com.example.aichat.model;

import com.fasterxml.jackson.annotation.JsonProperty;

public record ChatResponse(
        String content,
        @JsonProperty("conversationId") String conversationId
) {
}
