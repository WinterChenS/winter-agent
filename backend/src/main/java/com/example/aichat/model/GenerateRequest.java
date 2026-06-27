package com.example.aichat.model;

import com.fasterxml.jackson.annotation.JsonProperty;

public record GenerateRequest(
        String message,
        @JsonProperty("agent_id") String agentId,
        @JsonProperty("conversation_id") String conversationId,
        @JsonProperty("message_id") String messageId,
        boolean stream
) {
    public GenerateRequest(String message, String agentId, String conversationId, String messageId) {
        this(message, agentId, conversationId, messageId, true);
    }
}
