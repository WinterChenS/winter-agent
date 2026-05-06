package com.example.aichat.model;

import com.fasterxml.jackson.annotation.JsonProperty;

public record GenerateResponse(
        String token,
        @JsonProperty("conversation_id") String conversationId
) {
}
