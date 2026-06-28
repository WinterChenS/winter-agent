package com.example.aichat.dto;

import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import jakarta.validation.ValidatorFactory;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;

class AgentRequestTest {

    private static ValidatorFactory validatorFactory;
    private static Validator validator;

    @BeforeAll
    static void setUp() {
        validatorFactory = Validation.buildDefaultValidatorFactory();
        validator = validatorFactory.getValidator();
    }

    @AfterAll
    static void tearDown() {
        if (validatorFactory != null) {
            validatorFactory.close();
        }
    }

    @Test
    void shouldCreateWithAllFields() {
        var request = new AgentRequest(
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
                Map.of("key", "value")
        );

        assertEquals("test-agent", request.name());
        assertEquals("Test Agent", request.displayName());
        assertEquals("A test agent description", request.description());
        assertEquals("robot", request.icon());
        assertEquals("chat", request.agentType());
        assertEquals("https://example.com/avatar.png", request.avatarUrl());
        assertEquals("You are a helpful test agent.", request.systemPrompt());
        assertEquals(List.of("tool1", "tool2"), request.tools());
        assertEquals(Map.of("temperature", 0.7), request.modelConfig());
        assertEquals(List.of("hello", "hi"), request.triggerKeywords());
        assertEquals("sequential", request.collaborationStrategy());
        assertEquals(1, request.priority());
        assertEquals(true, request.enabled());
        assertEquals(List.of("tag1", "tag2"), request.tags());
        assertEquals(Map.of("key", "value"), request.metadata());
    }

    @Test
    void shouldCreateWithOnlyRequiredFields() {
        var request = new AgentRequest(
                "test-agent",
                "Test Agent",
                null,
                null,
                null,
                null,
                "You are a helpful test agent.",
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null
        );

        assertEquals("test-agent", request.name());
        assertEquals("Test Agent", request.displayName());
        assertNull(request.description());
        assertNull(request.icon());
        assertNull(request.agentType());
        assertNull(request.avatarUrl());
        assertEquals("You are a helpful test agent.", request.systemPrompt());
        assertNull(request.tools());
        assertNull(request.modelConfig());
        assertNull(request.triggerKeywords());
        assertNull(request.collaborationStrategy());
        assertNull(request.priority());
        assertNull(request.enabled());
        assertNull(request.tags());
        assertNull(request.metadata());
    }

    @Test
    void shouldFailValidationWhenNameIsBlank() {
        var request = new AgentRequest(
                "",
                "Test Agent",
                null, null, null, null,
                "You are a helpful test agent.",
                null, null, null, null, null, null, null, null
        );
        Set<ConstraintViolation<AgentRequest>> violations = validator.validate(request);
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream()
                .anyMatch(v -> v.getPropertyPath().toString().equals("name")));
    }

    @Test
    void shouldFailValidationWhenDisplayNameIsBlank() {
        var request = new AgentRequest(
                "test-agent",
                "",
                null, null, null, null,
                "You are a helpful test agent.",
                null, null, null, null, null, null, null, null
        );
        Set<ConstraintViolation<AgentRequest>> violations = validator.validate(request);
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream()
                .anyMatch(v -> v.getPropertyPath().toString().equals("displayName")));
    }

    @Test
    void shouldFailValidationWhenSystemPromptIsBlank() {
        var request = new AgentRequest(
                "test-agent",
                "Test Agent",
                null, null, null, null,
                "",
                null, null, null, null, null, null, null, null
        );
        Set<ConstraintViolation<AgentRequest>> violations = validator.validate(request);
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream()
                .anyMatch(v -> v.getPropertyPath().toString().equals("systemPrompt")));
    }

    @Test
    void shouldPassValidationWhenAllRequiredFieldsArePresent() {
        var request = new AgentRequest(
                "test-agent",
                "Test Agent",
                null, null, null, null,
                "You are a helpful test agent.",
                null, null, null, null, null, null, null, null
        );
        Set<ConstraintViolation<AgentRequest>> violations = validator.validate(request);
        assertTrue(violations.isEmpty());
    }
}
