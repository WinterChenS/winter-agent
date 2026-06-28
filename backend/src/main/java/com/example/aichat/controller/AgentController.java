package com.example.aichat.controller;

import com.example.aichat.dto.AgentRequest;
import com.example.aichat.dto.AgentResponse;
import com.example.aichat.service.AgentService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;

import java.util.List;

@RestController
@RequestMapping("/api/agents")
public class AgentController {

    private final AgentService agentService;

    public AgentController(AgentService agentService) {
        this.agentService = agentService;
    }

    @GetMapping
    public Mono<ResponseEntity<List<AgentResponse>>> listAgents() {
        return agentService.listAll()
                .map(ResponseEntity::ok);
    }

    @GetMapping("/{id}")
    public Mono<ResponseEntity<AgentResponse>> getAgent(@PathVariable String id) {
        return agentService.getById(id)
                .map(ResponseEntity::ok)
                .defaultIfEmpty(ResponseEntity.notFound().build());
    }

    @PostMapping
    public Mono<ResponseEntity<AgentResponse>> createAgent(@Valid @RequestBody AgentRequest req) {
        return agentService.create(req)
                .map(agent -> ResponseEntity.status(HttpStatus.CREATED).body(agent));
    }

    @PutMapping("/{id}")
    public Mono<ResponseEntity<AgentResponse>> updateAgent(@PathVariable String id,
                                                           @Valid @RequestBody AgentRequest req) {
        return agentService.update(id, req)
                .map(ResponseEntity::ok);
    }

    @DeleteMapping("/{id}")
    public Mono<ResponseEntity<Void>> deleteAgent(@PathVariable String id) {
        return agentService.delete(id)
                .then(Mono.just(ResponseEntity.noContent().build()));
    }

    @PostMapping("/{id}/enable")
    public Mono<ResponseEntity<AgentResponse>> enableAgent(@PathVariable String id) {
        return agentService.enable(id)
                .map(ResponseEntity::ok);
    }

    @PostMapping("/{id}/disable")
    public Mono<ResponseEntity<AgentResponse>> disableAgent(@PathVariable String id) {
        return agentService.disable(id)
                .map(ResponseEntity::ok);
    }

    @PostMapping("/{id}/clone")
    public Mono<ResponseEntity<AgentResponse>> cloneAgent(@PathVariable String id) {
        return agentService.clone(id)
                .map(ResponseEntity::ok);
    }
}
