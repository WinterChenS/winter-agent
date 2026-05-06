package com.example.aichat.client;

import com.example.aichat.model.GenerateRequest;
import com.example.aichat.model.GenerateResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;

@Component
public class AIClient {

    private final WebClient webClient;
    private final String aiServiceUrl;

    public AIClient(WebClient webClient,
                    @Value("${aichat.ai-service-url}") String aiServiceUrl) {
        this.webClient = webClient;
        this.aiServiceUrl = aiServiceUrl;
    }

    public Flux<GenerateResponse> streamGenerate(String message, String conversationId) {
        GenerateRequest request = new GenerateRequest(message, conversationId);

        return webClient.post()
                .uri(aiServiceUrl + "/api/v1/generate/stream")
                .bodyValue(request)
                .retrieve()
                .bodyToFlux(GenerateResponse.class);
    }

    public reactor.core.publisher.Mono<String> getChatHistory(String conversationId) {
        return webClient.get()
                .uri(aiServiceUrl + "/api/v1/history/{conversationId}", conversationId)
                .retrieve()
                .bodyToMono(String.class);
    }
}
