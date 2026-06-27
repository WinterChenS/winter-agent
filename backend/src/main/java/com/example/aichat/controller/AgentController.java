package com.example.aichat.controller;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

@RestController
@RequestMapping("/api/agents")
public class AgentController {

    private final WebClient webClient;
    private final String aiServiceUrl;

    public AgentController(WebClient webClient,
                           @Value("${aichat.ai-service-url}") String aiServiceUrl) {
        this.webClient = webClient;
        this.aiServiceUrl = aiServiceUrl;
    }

    @GetMapping
    public Mono<ResponseEntity<String>> listAgents() {
        return webClient.get()
                .uri(aiServiceUrl + "/api/v1/agents/")
                .retrieve()
                .bodyToMono(String.class)
                .map(ResponseEntity::ok);
    }

    @PostMapping
    public Mono<ResponseEntity<String>> createAgent(@RequestBody String body) {
        return webClient.post()
                .uri(aiServiceUrl + "/api/v1/agents/")
                .bodyValue(body)
                .retrieve()
                .bodyToMono(String.class)
                .map(ResponseEntity::ok);
    }

    @PutMapping("/{id}")
    public Mono<ResponseEntity<String>> updateAgent(@PathVariable String id, @RequestBody String body) {
        return webClient.put()
                .uri(aiServiceUrl + "/api/v1/agents/" + id)
                .bodyValue(body)
                .retrieve()
                .bodyToMono(String.class)
                .map(ResponseEntity::ok);
    }

    @DeleteMapping("/{id}")
    public Mono<ResponseEntity<String>> deleteAgent(@PathVariable String id) {
        return webClient.delete()
                .uri(aiServiceUrl + "/api/v1/agents/" + id)
                .retrieve()
                .bodyToMono(String.class)
                .map(ResponseEntity::ok);
    }
}
