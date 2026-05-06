package com.example.aichat.controller;

import com.example.aichat.model.ChatRequest;
import com.example.aichat.service.ChatService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@RestController
@RequestMapping("/api/chat")
public class ChatController {

    private final ChatService chatService;

    public ChatController(ChatService chatService) {
        this.chatService = chatService;
    }

    @PostMapping(value = "/stream", produces = "text/event-stream")
    public Flux<String> streamChat(@RequestBody ChatRequest request) {
        return chatService.streamChat(request.message(), request.conversationId())
                .map(token -> {
                    String jsonContent = token
                            .replace("\\", "\\\\")
                            .replace("\"", "\\\"")
                            .replace("\n", "\\n");
                    return "{\"content\":\"" + jsonContent + "\"}";
                })
                .onErrorResume(error ->
                        Flux.just("{\"error\":\"AI 服务繁忙，请稍后再试\"}")
                );
    }

    @GetMapping(value = "/history/{conversationId}", produces = "application/json")
    public Mono<String> getChatHistory(@PathVariable String conversationId) {
        return chatService.getChatHistory(conversationId);
    }
}
