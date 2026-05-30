package com.example.aichat.model;

import com.fasterxml.jackson.annotation.JsonAlias;
import com.fasterxml.jackson.annotation.JsonProperty;

public record GenerateResponse(
        String type,
        String token,
        String content,
        @JsonProperty("toolName") String toolName,
        String error,
        @JsonAlias({"conversationId", "conversation_id"}) String conversationId,
        @JsonProperty("steps") java.util.List<java.util.Map<String, Object>> steps,
        @JsonProperty("reason") java.util.Map<String, Object> reason
) {
}
