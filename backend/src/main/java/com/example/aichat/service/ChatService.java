package com.example.aichat.service;

import com.example.aichat.client.AIClient;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;

@Service
public class ChatService {

    private final AIClient aiClient;

    public ChatService(AIClient aiClient) {
        this.aiClient = aiClient;
    }

    public Flux<String> streamChat(String message, String agentId,
                                    String conversationId, String messageId) {
        return aiClient.streamGenerate(message, agentId, conversationId, messageId);
    }

    public reactor.core.publisher.Mono<String> getChatHistory(String conversationId) {
        return aiClient.getChatHistory(conversationId);
    }
}
