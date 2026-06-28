package com.example.aichat.service;

import com.example.aichat.client.AgentClient;
import com.example.aichat.dto.AgentRequest;
import com.example.aichat.dto.AgentResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.web.reactive.function.client.WebClientRequestException;
import org.springframework.web.server.ResponseStatusException;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

import java.net.ConnectException;
import java.net.URI;
import java.time.LocalDateTime;
import java.util.List;

import org.springframework.http.HttpHeaders;

class AgentServiceTest {

    private StubAgentClient agentClient;
    private AgentService agentService;

    private final String agentId = "agent-123";
    private final AgentResponse sampleAgent = new AgentResponse(
            agentId, "test-agent", "Test Agent",
            "A test agent", "robot", "chat",
            "https://example.com/avatar.png", "You are a helpful test agent.",
            List.of("tool1"), null,
            List.of("hello"), "sequential",
            1, true, List.of("tag1"), null,
            "admin", null,
            LocalDateTime.now(), null,
            false, 1
    );

    @BeforeEach
    void setUp() {
        agentClient = new StubAgentClient();
        agentService = new AgentService(agentClient);
    }

    @Test
    void shouldListAllAgents() {
        agentClient.listAllResult = Mono.just(List.of(sampleAgent, agent2()));

        StepVerifier.create(agentService.listAll())
                .assertNext(agents -> {
                    assert agents.size() == 2;
                    assert agents.get(0).id().equals(agentId);
                    assert agents.get(1).id().equals("agent-456");
                })
                .verifyComplete();
    }

    @Test
    void shouldGetAgentById() {
        agentClient.getByIdResult = Mono.just(sampleAgent);

        StepVerifier.create(agentService.getById(agentId))
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
        agentClient.createResult = Mono.just(created);

        StepVerifier.create(agentService.create(req))
                .assertNext(agent -> {
                    assert agent.id().equals("new-id");
                })
                .verifyComplete();
    }

    @Test
    void shouldUpdateAgent() {
        var req = new AgentRequest(
                "updated-agent", "Updated Agent", null, null, null, null,
                "You are updated.", null, null, null, null, null, null, null, null
        );
        agentClient.updateResult = Mono.just(sampleAgent);

        StepVerifier.create(agentService.update(agentId, req))
                .assertNext(agent -> {
                    assert agent.id().equals(agentId);
                })
                .verifyComplete();
    }

    @Test
    void shouldDeleteAgent() {
        agentClient.deleteResult = Mono.empty();

        StepVerifier.create(agentService.delete(agentId))
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
        agentClient.enableResult = Mono.just(enabled);

        StepVerifier.create(agentService.enable(agentId))
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
        agentClient.disableResult = Mono.just(disabled);

        StepVerifier.create(agentService.disable(agentId))
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
        agentClient.cloneResult = Mono.just(cloned);

        StepVerifier.create(agentService.clone(agentId))
                .assertNext(agent -> {
                    assert agent.id().equals("cloned-id");
                })
                .verifyComplete();
    }

    @Test
    void shouldReturn503OnWebClientRequestException() {
        agentClient.listAllResult = Mono.error(
                new WebClientRequestException(
                        new RuntimeException("connection failed"),
                        HttpMethod.GET, URI.create("http://localhost"), new HttpHeaders()
                )
        );

        StepVerifier.create(agentService.listAll())
                .expectErrorSatisfies(err -> {
                    assert err instanceof ResponseStatusException;
                    var rse = (ResponseStatusException) err;
                    assert rse.getStatusCode().value() == 503;
                    assert rse.getReason().equals("AI 服务不可用");
                })
                .verify();
    }

    @Test
    void shouldReturn503OnConnectException() {
        agentClient.listAllResult = Mono.error(
                new ConnectException("Connection refused")
        );

        StepVerifier.create(agentService.listAll())
                .expectErrorSatisfies(err -> {
                    assert err instanceof ResponseStatusException;
                    var rse = (ResponseStatusException) err;
                    assert rse.getStatusCode().value() == 503;
                    assert rse.getReason().equals("AI 服务不可用");
                })
                .verify();
    }

    @Test
    void shouldPropagateOtherExceptions() {
        agentClient.listAllResult = Mono.error(
                new IllegalArgumentException("bad argument")
        );

        StepVerifier.create(agentService.listAll())
                .expectError(IllegalArgumentException.class)
                .verify();
    }

    private AgentResponse agent2() {
        return new AgentResponse(
                "agent-456", "test-agent-2", "Test Agent 2",
                null, null, null, null, null,
                null, null, null, null,
                null, null, null, null,
                null, null, null, null, null, null
        );
    }

    /**
     * Hand-written stub for AgentClient to avoid Mockito/ByteBuddy Java 25 incompatibility.
     */
    static class StubAgentClient extends AgentClient {
        Mono<List<AgentResponse>> listAllResult;
        Mono<AgentResponse> getByIdResult;
        Mono<AgentResponse> createResult;
        Mono<AgentResponse> updateResult;
        Mono<Void> deleteResult;
        Mono<AgentResponse> enableResult;
        Mono<AgentResponse> disableResult;
        Mono<AgentResponse> cloneResult;

        StubAgentClient() {
            super(null);
        }

        @Override
        public Mono<List<AgentResponse>> listAll() {
            return listAllResult;
        }

        @Override
        public Mono<AgentResponse> getById(String id) {
            return getByIdResult;
        }

        @Override
        public Mono<AgentResponse> create(AgentRequest req) {
            return createResult;
        }

        @Override
        public Mono<AgentResponse> update(String id, AgentRequest req) {
            return updateResult;
        }

        @Override
        public Mono<Void> delete(String id) {
            return deleteResult;
        }

        @Override
        public Mono<AgentResponse> enable(String id) {
            return enableResult;
        }

        @Override
        public Mono<AgentResponse> disable(String id) {
            return disableResult;
        }

        @Override
        public Mono<AgentResponse> clone(String id) {
            return cloneResult;
        }
    }
}
