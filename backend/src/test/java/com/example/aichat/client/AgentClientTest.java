package com.example.aichat.client;

import com.example.aichat.dto.AgentRequest;
import com.example.aichat.dto.AgentResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

import java.util.List;

import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class AgentClientTest {

    @Mock
    private WebClient webClient;

    @Mock
    private WebClient.RequestHeadersUriSpec requestHeadersUriSpec;

    @Mock
    private WebClient.RequestHeadersSpec requestHeadersSpec;

    @Mock
    private WebClient.RequestBodyUriSpec requestBodyUriSpec;

    @Mock
    private WebClient.RequestBodySpec requestBodySpec;

    @Mock
    private WebClient.ResponseSpec responseSpec;

    private AgentClient agentClient;

    private final String agentId = "agent-123";
    private final AgentResponse sampleAgent = new AgentResponse(
            agentId, "test-agent", "Test Agent",
            "A test agent", "robot", "chat",
            "https://example.com/avatar.png", "You are a helpful test agent.",
            List.of("tool1"), null,
            List.of("hello"), "sequential",
            1, true, List.of("tag1"), null,
            "admin", null,
            "2026-06-28T12:00:00", null,
            false, 1
    );

    @BeforeEach
    void setUp() {
        agentClient = new AgentClient(webClient);
    }

    @Test
    void shouldListAllAgents() {
        var agent2 = new AgentResponse(
                "agent-456", "test-agent-2", "Test Agent 2",
                null, null, null,
                null, null,
                null, null, null, null,
                null, null, null, null,
                null, null, null, null, null, null
        );

        when(webClient.get()).thenReturn(requestHeadersUriSpec);
        when(requestHeadersUriSpec.uri("/api/v1/agents/")).thenReturn(requestHeadersSpec);
        when(requestHeadersSpec.retrieve()).thenReturn(responseSpec);
        when(responseSpec.bodyToFlux(AgentResponse.class)).thenReturn(Flux.just(sampleAgent, agent2));

        StepVerifier.create(agentClient.listAll())
                .assertNext(agents -> {
                    assert agents.size() == 2;
                    assert agents.get(0).id().equals(agentId);
                    assert agents.get(1).id().equals("agent-456");
                })
                .verifyComplete();
    }

    @Test
    void shouldGetAgentById() {
        when(webClient.get()).thenReturn(requestHeadersUriSpec);
        when(requestHeadersUriSpec.uri("/api/v1/agents/{id}", agentId)).thenReturn(requestHeadersSpec);
        when(requestHeadersSpec.retrieve()).thenReturn(responseSpec);
        when(responseSpec.bodyToMono(AgentResponse.class)).thenReturn(Mono.just(sampleAgent));

        StepVerifier.create(agentClient.getById(agentId))
                .assertNext(agent -> {
                    assert agent.id().equals(agentId);
                    assert agent.name().equals("test-agent");
                })
                .verifyComplete();
    }

    @Test
    void shouldCreateAgent() {
        var req = new AgentRequest(
                "new-agent", "New Agent", null, null, null, null,
                "You are a new agent.", null, null, null, null, null, null, null, null
        );
        var created = new AgentResponse(
                "new-id", "new-agent", "New Agent",
                null, null, null, null, "You are a new agent.",
                null, null, null, null,
                null, null, null, null,
                "admin", null, null, null, null, null
        );

        when(webClient.post()).thenReturn(requestBodyUriSpec);
        when(requestBodyUriSpec.uri("/api/v1/agents/")).thenReturn(requestBodySpec);
        when(requestBodySpec.bodyValue(req)).thenReturn(requestHeadersSpec);
        when(requestHeadersSpec.retrieve()).thenReturn(responseSpec);
        when(responseSpec.bodyToMono(AgentResponse.class)).thenReturn(Mono.just(created));

        StepVerifier.create(agentClient.create(req))
                .assertNext(agent -> {
                    assert agent.id().equals("new-id");
                    assert agent.name().equals("new-agent");
                })
                .verifyComplete();
    }

    @Test
    void shouldUpdateAgent() {
        var req = new AgentRequest(
                "updated-agent", "Updated Agent", null, null, null, null,
                "You are updated.", null, null, null, null, null, null, null, null
        );

        when(webClient.put()).thenReturn(requestBodyUriSpec);
        when(requestBodyUriSpec.uri("/api/v1/agents/{id}", agentId)).thenReturn(requestBodySpec);
        when(requestBodySpec.bodyValue(req)).thenReturn(requestHeadersSpec);
        when(requestHeadersSpec.retrieve()).thenReturn(responseSpec);
        when(responseSpec.bodyToMono(AgentResponse.class)).thenReturn(Mono.just(sampleAgent));

        StepVerifier.create(agentClient.update(agentId, req))
                .assertNext(agent -> {
                    assert agent.id().equals(agentId);
                })
                .verifyComplete();
    }

    @Test
    void shouldDeleteAgent() {
        when(webClient.delete()).thenReturn(requestHeadersUriSpec);
        when(requestHeadersUriSpec.uri("/api/v1/agents/{id}", agentId)).thenReturn(requestHeadersSpec);
        when(requestHeadersSpec.retrieve()).thenReturn(responseSpec);
        when(responseSpec.bodyToMono(Void.class)).thenReturn(Mono.empty());

        StepVerifier.create(agentClient.delete(agentId))
                .verifyComplete();
    }

    @Test
    void shouldEnableAgent() {
        var enabled = new AgentResponse(
                agentId, "test-agent", "Test Agent",
                null, null, null, null, null,
                null, null, null, null,
                null, true, null, null,
                "admin", "admin", null, null, null, null
        );

        when(webClient.post()).thenReturn(requestBodyUriSpec);
        when(requestBodyUriSpec.uri("/api/v1/agents/{id}/enable", agentId)).thenReturn(requestBodySpec);
        when(requestBodySpec.retrieve()).thenReturn(responseSpec);
        when(responseSpec.bodyToMono(AgentResponse.class)).thenReturn(Mono.just(enabled));

        StepVerifier.create(agentClient.enable(agentId))
                .assertNext(agent -> {
                    assert agent.enabled().equals(true);
                })
                .verifyComplete();
    }

    @Test
    void shouldDisableAgent() {
        var disabled = new AgentResponse(
                agentId, "test-agent", "Test Agent",
                null, null, null, null, null,
                null, null, null, null,
                null, false, null, null,
                "admin", "admin", null, null, null, null
        );

        when(webClient.post()).thenReturn(requestBodyUriSpec);
        when(requestBodyUriSpec.uri("/api/v1/agents/{id}/disable", agentId)).thenReturn(requestBodySpec);
        when(requestBodySpec.retrieve()).thenReturn(responseSpec);
        when(responseSpec.bodyToMono(AgentResponse.class)).thenReturn(Mono.just(disabled));

        StepVerifier.create(agentClient.disable(agentId))
                .assertNext(agent -> {
                    assert agent.enabled().equals(false);
                })
                .verifyComplete();
    }

    @Test
    void shouldCloneAgent() {
        var cloned = new AgentResponse(
                "cloned-id", "test-agent", "Test Agent (Copy)",
                null, null, null, null, null,
                null, null, null, null,
                null, null, null, null,
                "admin", null, null, null, null, null
        );

        when(webClient.post()).thenReturn(requestBodyUriSpec);
        when(requestBodyUriSpec.uri("/api/v1/agents/{id}/clone", agentId)).thenReturn(requestBodySpec);
        when(requestBodySpec.retrieve()).thenReturn(responseSpec);
        when(responseSpec.bodyToMono(AgentResponse.class)).thenReturn(Mono.just(cloned));

        StepVerifier.create(agentClient.clone(agentId))
                .assertNext(agent -> {
                    assert agent.id().equals("cloned-id");
                })
                .verifyComplete();
    }
}
