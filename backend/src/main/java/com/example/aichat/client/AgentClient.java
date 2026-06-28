package com.example.aichat.client;

import com.example.aichat.dto.AgentRequest;
import com.example.aichat.dto.AgentResponse;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.List;

@Component
public class AgentClient {

    private final WebClient agentWebClient;

    public AgentClient(@Qualifier("agentWebClient") WebClient agentWebClient) {
        this.agentWebClient = agentWebClient;
    }

    public Mono<List<AgentResponse>> listAll() {
        return agentWebClient.get()
                .uri("/api/v1/agents/")
                .retrieve()
                .bodyToFlux(AgentResponse.class)
                .collectList();
    }

    public Mono<AgentResponse> getById(String id) {
        return agentWebClient.get()
                .uri("/api/v1/agents/{id}", id)
                .retrieve()
                .bodyToMono(AgentResponse.class);
    }

    public Mono<AgentResponse> create(AgentRequest req) {
        return agentWebClient.post()
                .uri("/api/v1/agents/")
                .bodyValue(req)
                .retrieve()
                .bodyToMono(AgentResponse.class);
    }

    public Mono<AgentResponse> update(String id, AgentRequest req) {
        return agentWebClient.put()
                .uri("/api/v1/agents/{id}", id)
                .bodyValue(req)
                .retrieve()
                .bodyToMono(AgentResponse.class);
    }

    public Mono<Void> delete(String id) {
        return agentWebClient.delete()
                .uri("/api/v1/agents/{id}", id)
                .retrieve()
                .bodyToMono(Void.class);
    }

    public Mono<AgentResponse> enable(String id) {
        return agentWebClient.post()
                .uri("/api/v1/agents/{id}/enable", id)
                .retrieve()
                .bodyToMono(AgentResponse.class);
    }

    public Mono<AgentResponse> disable(String id) {
        return agentWebClient.post()
                .uri("/api/v1/agents/{id}/disable", id)
                .retrieve()
                .bodyToMono(AgentResponse.class);
    }

    public Mono<AgentResponse> clone(String id) {
        return agentWebClient.post()
                .uri("/api/v1/agents/{id}/clone", id)
                .retrieve()
                .bodyToMono(AgentResponse.class);
    }
}
