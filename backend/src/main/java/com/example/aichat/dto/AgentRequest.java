package com.example.aichat.dto;

import jakarta.validation.constraints.NotBlank;

import java.util.List;
import java.util.Map;

public record AgentRequest(
        @NotBlank String name,
        @NotBlank String displayName,
        String description,
        String icon,
        String agentType,
        String avatarUrl,
        @NotBlank String systemPrompt,
        List<String> tools,
        Map<String, Object> modelConfig,
        List<String> triggerKeywords,
        String collaborationStrategy,
        Integer priority,
        Boolean enabled,
        List<String> tags,
        Map<String, Object> metadata
) {
}
