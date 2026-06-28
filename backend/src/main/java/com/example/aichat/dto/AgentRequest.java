package com.example.aichat.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;

import java.util.List;
import java.util.Map;

public record AgentRequest(
        @NotBlank String name,
        @NotBlank @JsonProperty("display_name") String displayName,
        String description,
        String icon,
        @JsonProperty("agent_type") String agentType,
        @JsonProperty("avatar_url") String avatarUrl,
        @NotBlank @JsonProperty("system_prompt") String systemPrompt,
        List<String> tools,
        @JsonProperty("model_config") Map<String, Object> modelConfig,
        @JsonProperty("trigger_keywords") List<String> triggerKeywords,
        @JsonProperty("collaboration_strategy") String collaborationStrategy,
        Integer priority,
        Boolean enabled,
        List<String> tags,
        Map<String, Object> metadata
) {
}
