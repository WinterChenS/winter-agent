package com.example.aichat.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

public record AgentResponse(
        String id,
        @JsonProperty("name") String name,
        @JsonProperty("display_name") String displayName,
        String description,
        String icon,
        @JsonProperty("agent_type") String agentType,
        @JsonProperty("avatar_url") String avatarUrl,
        @JsonProperty("system_prompt") String systemPrompt,
        List<String> tools,
        @JsonProperty("model_config") Map<String, Object> modelConfig,
        @JsonProperty("trigger_keywords") List<String> triggerKeywords,
        @JsonProperty("collaboration_strategy") String collaborationStrategy,
        Integer priority,
        Boolean enabled,
        List<String> tags,
        Map<String, Object> metadata,
        @JsonProperty("created_by") String createdBy,
        @JsonProperty("updated_by") String updatedBy,
        @JsonProperty("created_at") LocalDateTime createdAt,
        @JsonProperty("updated_at") LocalDateTime updatedAt,
        @JsonProperty("is_builtin") Boolean isBuiltin,
        Integer version
) {
}
