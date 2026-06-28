package com.example.aichat.dto;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class AgentResponseTest {

    private static ObjectMapper objectMapper;

    @BeforeAll
    static void setUp() {
        objectMapper = new ObjectMapper();
        objectMapper.registerModule(new JavaTimeModule());
    }

    @Test
    void shouldCreateWithAllFields() {
        var now = LocalDateTime.now();
        var response = new AgentResponse(
                "abc123def456",
                "test-agent",
                "Test Agent",
                "A test agent description",
                "robot",
                "chat",
                "https://example.com/avatar.png",
                "You are a helpful test agent.",
                List.of("tool1", "tool2"),
                Map.of("temperature", 0.7),
                List.of("hello", "hi"),
                "sequential",
                1,
                true,
                List.of("tag1", "tag2"),
                Map.of("key", "value"),
                "admin",
                "admin",
                now,
                now,
                false,
                1
        );

        assertEquals("abc123def456", response.id());
        assertEquals("test-agent", response.name());
        assertEquals("Test Agent", response.displayName());
        assertEquals("A test agent description", response.description());
        assertEquals("robot", response.icon());
        assertEquals("chat", response.agentType());
        assertEquals("https://example.com/avatar.png", response.avatarUrl());
        assertEquals("You are a helpful test agent.", response.systemPrompt());
        assertEquals(List.of("tool1", "tool2"), response.tools());
        assertEquals(Map.of("temperature", 0.7), response.modelConfig());
        assertEquals(List.of("hello", "hi"), response.triggerKeywords());
        assertEquals("sequential", response.collaborationStrategy());
        assertEquals(1, response.priority());
        assertEquals(true, response.enabled());
        assertEquals(List.of("tag1", "tag2"), response.tags());
        assertEquals(Map.of("key", "value"), response.metadata());
        assertEquals("admin", response.createdBy());
        assertEquals("admin", response.updatedBy());
        assertEquals(now, response.createdAt());
        assertEquals(now, response.updatedAt());
        assertEquals(false, response.isBuiltin());
        assertEquals(1, response.version());
    }

    @Test
    void shouldSerializeToSnakeCaseJson() throws JsonProcessingException {
        var now = LocalDateTime.of(2026, 6, 28, 12, 0, 0);
        var response = new AgentResponse(
                "abc123", "test-agent", "Test Agent",
                "description", "robot", "chat",
                "https://example.com/avatar.png", "You are a helpful test agent.",
                List.of("tool1"), Map.of("temperature", 0.7),
                List.of("hello"), "sequential",
                1, true, List.of("tag1"), Map.of("key", "value"),
                "admin", "admin", now, now, false, 1
        );

        String json = objectMapper.writeValueAsString(response);

        assertTrue(json.contains("\"id\""));
        assertTrue(json.contains("\"name\""));
        assertTrue(json.contains("\"display_name\""));
        assertTrue(json.contains("\"description\""));
        assertTrue(json.contains("\"icon\""));
        assertTrue(json.contains("\"agent_type\""));
        assertTrue(json.contains("\"avatar_url\""));
        assertTrue(json.contains("\"system_prompt\""));
        assertTrue(json.contains("\"tools\""));
        assertTrue(json.contains("\"model_config\""));
        assertTrue(json.contains("\"trigger_keywords\""));
        assertTrue(json.contains("\"collaboration_strategy\""));
        assertTrue(json.contains("\"priority\""));
        assertTrue(json.contains("\"enabled\""));
        assertTrue(json.contains("\"tags\""));
        assertTrue(json.contains("\"metadata\""));
        assertTrue(json.contains("\"created_by\""));
        assertTrue(json.contains("\"updated_by\""));
        assertTrue(json.contains("\"created_at\""));
        assertTrue(json.contains("\"updated_at\""));
        assertTrue(json.contains("\"is_builtin\""));
        assertTrue(json.contains("\"version\""));
    }

    @Test
    void shouldDeserializeFromSnakeCaseJson() throws JsonProcessingException {
        String json = """
                {
                    "id": "abc123",
                    "name": "test-agent",
                    "display_name": "Test Agent",
                    "description": "A test agent",
                    "icon": "robot",
                    "agent_type": "chat",
                    "avatar_url": "https://example.com/avatar.png",
                    "system_prompt": "You are a helpful test agent.",
                    "tools": ["tool1"],
                    "model_config": {"temperature": 0.7},
                    "trigger_keywords": ["hello"],
                    "collaboration_strategy": "sequential",
                    "priority": 1,
                    "enabled": true,
                    "tags": ["tag1"],
                    "metadata": {"key": "value"},
                    "created_by": "admin",
                    "updated_by": "admin",
                    "created_at": "2026-06-28T12:00:00",
                    "updated_at": "2026-06-28T12:00:00",
                    "is_builtin": false,
                    "version": 1
                }
                """;

        AgentResponse response = objectMapper.readValue(json, AgentResponse.class);

        assertEquals("abc123", response.id());
        assertEquals("test-agent", response.name());
        assertEquals("Test Agent", response.displayName());
        assertEquals("A test agent", response.description());
        assertEquals("robot", response.icon());
        assertEquals("chat", response.agentType());
        assertEquals("https://example.com/avatar.png", response.avatarUrl());
        assertEquals("You are a helpful test agent.", response.systemPrompt());
        assertEquals(List.of("tool1"), response.tools());
        assertEquals(Map.of("temperature", 0.7), response.modelConfig());
        assertEquals(List.of("hello"), response.triggerKeywords());
        assertEquals("sequential", response.collaborationStrategy());
        assertEquals(1, response.priority());
        assertEquals(true, response.enabled());
        assertEquals(List.of("tag1"), response.tags());
        assertEquals(Map.of("key", "value"), response.metadata());
        assertEquals("admin", response.createdBy());
        assertEquals("admin", response.updatedBy());
        assertEquals(LocalDateTime.of(2026, 6, 28, 12, 0, 0), response.createdAt());
        assertEquals(LocalDateTime.of(2026, 6, 28, 12, 0, 0), response.updatedAt());
        assertEquals(false, response.isBuiltin());
        assertEquals(1, response.version());
    }
}
