package com.example.aichat.service;

import com.example.aichat.client.AgentClient;
import com.example.aichat.dto.AgentRequest;
import com.example.aichat.dto.AgentResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClientRequestException;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import org.springframework.web.server.ResponseStatusException;
import reactor.core.publisher.Mono;

import java.net.ConnectException;
import java.util.List;

@Service
public class AgentService {

    private final AgentClient agentClient;
    private final Logger log = LoggerFactory.getLogger(AgentService.class);

    public AgentService(AgentClient agentClient) {
        this.agentClient = agentClient;
    }

    public Mono<List<AgentResponse>> listAll() {
        log.info("Listing all agents");
        return agentClient.listAll()
                .doOnSuccess(agents -> log.info("Listed {} agents", agents.size()))
                .onErrorResume(this::isConnectionError, this::serviceUnavailable)
                .onErrorResume(e -> e instanceof WebClientResponseException, this::handleUpstreamError)
                .doOnError(e -> logUnexpectedError("listAgents", e));
    }

    public Mono<AgentResponse> getById(String id) {
        log.info("Getting agent by id: {}", id);
        return agentClient.getById(id)
                .doOnSuccess(agent -> log.info("Found agent: {}", id))
                .onErrorResume(this::isConnectionError, this::serviceUnavailable)
                .onErrorResume(e -> e instanceof WebClientResponseException, this::handleUpstreamError)
                .doOnError(e -> logUnexpectedError("getAgent", e));
    }

    public Mono<AgentResponse> create(AgentRequest req) {
        log.info("Creating agent: {}", req.name());
        return agentClient.create(req)
                .doOnSuccess(agent -> log.info("Created agent: {} ({})", agent.name(), agent.id()))
                .onErrorResume(this::isConnectionError, this::serviceUnavailable)
                .onErrorResume(e -> e instanceof WebClientResponseException, this::handleUpstreamError)
                .doOnError(e -> logUnexpectedError("createAgent", e));
    }

    public Mono<AgentResponse> update(String id, AgentRequest req) {
        log.info("Updating agent: {}", id);
        return agentClient.update(id, req)
                .doOnSuccess(agent -> log.info("Updated agent: {}", id))
                .onErrorResume(this::isConnectionError, this::serviceUnavailable)
                .onErrorResume(e -> e instanceof WebClientResponseException, this::handleUpstreamError)
                .doOnError(e -> logUnexpectedError("updateAgent", e));
    }

    public Mono<Void> delete(String id) {
        log.info("Deleting agent: {}", id);
        return agentClient.delete(id)
                .doOnSuccess(unused -> log.info("Deleted agent: {}", id))
                .onErrorResume(this::isConnectionError, this::serviceUnavailable)
                .onErrorResume(e -> e instanceof WebClientResponseException, this::handleUpstreamError)
                .doOnError(e -> logUnexpectedError("deleteAgent", e));
    }

    public Mono<AgentResponse> enable(String id) {
        log.info("Enabling agent: {}", id);
        return agentClient.enable(id)
                .doOnSuccess(agent -> log.info("Enabled agent: {}", id))
                .onErrorResume(this::isConnectionError, this::serviceUnavailable)
                .onErrorResume(e -> e instanceof WebClientResponseException, this::handleUpstreamError)
                .doOnError(e -> logUnexpectedError("enableAgent", e));
    }

    public Mono<AgentResponse> disable(String id) {
        log.info("Disabling agent: {}", id);
        return agentClient.disable(id)
                .doOnSuccess(agent -> log.info("Disabled agent: {}", id))
                .onErrorResume(this::isConnectionError, this::serviceUnavailable)
                .onErrorResume(e -> e instanceof WebClientResponseException, this::handleUpstreamError)
                .doOnError(e -> logUnexpectedError("disableAgent", e));
    }

    public Mono<AgentResponse> clone(String id) {
        log.info("Cloning agent: {}", id);
        return agentClient.clone(id)
                .doOnSuccess(agent -> log.info("Cloned agent: {} ({})", agent.name(), agent.id()))
                .onErrorResume(this::isConnectionError, this::serviceUnavailable)
                .onErrorResume(e -> e instanceof WebClientResponseException, this::handleUpstreamError)
                .doOnError(e -> logUnexpectedError("cloneAgent", e));
    }

    private boolean isConnectionError(Throwable e) {
        return e instanceof WebClientRequestException || e instanceof ConnectException;
    }

    private <T> Mono<T> handleUpstreamError(Throwable e) {
        WebClientResponseException wcre = (WebClientResponseException) e;
        log.warn("Upstream service returned {}: {}", wcre.getStatusCode(), wcre.getResponseBodyAsString());
        return Mono.error(new ResponseStatusException(wcre.getStatusCode(), "上游服务返回错误"));
    }

    private <T> Mono<T> serviceUnavailable(Throwable e) {
        log.error("AI service unavailable: {}", e.getMessage());
        return Mono.error(new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "AI 服务不可用"));
    }

    private void logUnexpectedError(String operation, Throwable e) {
        if (!(e instanceof ResponseStatusException)) {
            log.error("Error during {}: {}", operation, e.getMessage(), e);
        }
    }
}
