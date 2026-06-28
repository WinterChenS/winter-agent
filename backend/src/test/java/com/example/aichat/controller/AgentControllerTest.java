package com.example.aichat.controller;

import com.example.aichat.client.AgentClient;
import com.example.aichat.dto.AgentRequest;
import com.example.aichat.dto.AgentResponse;
import com.example.aichat.service.AgentService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.reactive.server.WebTestClient;
import org.springframework.web.server.ResponseStatusException;
import reactor.core.publisher.Mono;

import java.time.LocalDateTime;
import java.util.List;

class AgentControllerTest {

    private StubAgentService agentService;
    private WebTestClient webTestClient;

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
        agentService = new StubAgentService();
        var controller = new AgentController(agentService);
        webTestClient = WebTestClient.bindToController(controller).build();
    }

    @Test
    void shouldListAllAgents() {
        agentService.listAllResult = Mono.just(List.of(sampleAgent));

        webTestClient.get().uri("/api/agents")
                .exchange()
                .expectStatus().isOk()
                .expectBody()
                .jsonPath("$[0].id").isEqualTo(agentId);
    }

    @Test
    void shouldGetAgentById() {
        agentService.getByIdResult = Mono.just(sampleAgent);

        webTestClient.get().uri("/api/agents/{id}", agentId)
                .exchange()
                .expectStatus().isOk()
                .expectBody()
                .jsonPath("$.id").isEqualTo(agentId);
    }

    @Test
    void shouldReturn404WhenAgentNotFound() {
        agentService.getByIdResult = Mono.empty();

        webTestClient.get().uri("/api/agents/{id}", "nonexistent")
                .exchange()
                .expectStatus().isNotFound();
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
        agentService.createResult = Mono.just(created);

        webTestClient.post().uri("/api/agents")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(req)
                .exchange()
                .expectStatus().isCreated()
                .expectBody()
                .jsonPath("$.id").isEqualTo("new-id");
    }

    @Test
    void shouldUpdateAgent() {
        var req = new AgentRequest(
                "updated-agent", "Updated Agent", null, null, null, null,
                "You are updated.", null, null, null, null, null, null, null, null
        );
        agentService.updateResult = Mono.just(sampleAgent);

        webTestClient.put().uri("/api/agents/{id}", agentId)
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(req)
                .exchange()
                .expectStatus().isOk()
                .expectBody()
                .jsonPath("$.id").isEqualTo(agentId);
    }

    @Test
    void shouldDeleteAgent() {
        agentService.deleteResult = Mono.empty();

        webTestClient.delete().uri("/api/agents/{id}", agentId)
                .exchange()
                .expectStatus().isNoContent();
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
        agentService.enableResult = Mono.just(enabled);

        webTestClient.post().uri("/api/agents/{id}/enable", agentId)
                .exchange()
                .expectStatus().isOk()
                .expectBody()
                .jsonPath("$.enabled").isEqualTo(true);
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
        agentService.disableResult = Mono.just(disabled);

        webTestClient.post().uri("/api/agents/{id}/disable", agentId)
                .exchange()
                .expectStatus().isOk()
                .expectBody()
                .jsonPath("$.enabled").isEqualTo(false);
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
        agentService.cloneResult = Mono.just(cloned);

        webTestClient.post().uri("/api/agents/{id}/clone", agentId)
                .exchange()
                .expectStatus().isOk()
                .expectBody()
                .jsonPath("$.id").isEqualTo("cloned-id");
    }

    @Test
    void shouldReturn503WhenServiceUnavailable() {
        agentService.listAllResult = Mono.error(
                new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "AI 服务不可用")
        );

        webTestClient.get().uri("/api/agents")
                .exchange()
                .expectStatus().isEqualTo(503);
    }

    static class StubAgentService extends AgentService {
        Mono<List<AgentResponse>> listAllResult;
        Mono<AgentResponse> getByIdResult;
        Mono<AgentResponse> createResult;
        Mono<AgentResponse> updateResult;
        Mono<Void> deleteResult;
        Mono<AgentResponse> enableResult;
        Mono<AgentResponse> disableResult;
        Mono<AgentResponse> cloneResult;

        StubAgentService() {
            super(new StubAgentClient());
        }

        @Override
        public Mono<List<AgentResponse>> listAll() { return listAllResult; }

        @Override
        public Mono<AgentResponse> getById(String id) { return getByIdResult; }

        @Override
        public Mono<AgentResponse> create(AgentRequest req) { return createResult; }

        @Override
        public Mono<AgentResponse> update(String id, AgentRequest req) { return updateResult; }

        @Override
        public Mono<Void> delete(String id) { return deleteResult; }

        @Override
        public Mono<AgentResponse> enable(String id) { return enableResult; }

        @Override
        public Mono<AgentResponse> disable(String id) { return disableResult; }

        @Override
        public Mono<AgentResponse> clone(String id) { return cloneResult; }
    }

    static class StubAgentClient extends AgentClient {
        StubAgentClient() { super(null); }

        @Override
        public Mono<List<AgentResponse>> listAll() { return null; }
        @Override
        public Mono<AgentResponse> getById(String id) { return null; }
        @Override
        public Mono<AgentResponse> create(AgentRequest req) { return null; }
        @Override
        public Mono<AgentResponse> update(String id, AgentRequest req) { return null; }
        @Override
        public Mono<Void> delete(String id) { return null; }
        @Override
        public Mono<AgentResponse> enable(String id) { return null; }
        @Override
        public Mono<AgentResponse> disable(String id) { return null; }
        @Override
        public Mono<AgentResponse> clone(String id) { return null; }
    }
}
