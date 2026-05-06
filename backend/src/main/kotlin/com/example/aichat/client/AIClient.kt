package com.example.aichat.client

import com.example.aichat.model.GenerateRequest
import com.example.aichat.model.GenerateResponse
import org.springframework.beans.factory.annotation.Value
import org.springframework.stereotype.Component
import org.springframework.web.reactive.function.client.WebClient
import reactor.core.publisher.Flux

@Component
class AIClient(
    private val webClient: WebClient,
    @Value("\${aichat.ai-service-url}") private val aiServiceUrl: String
) {

    fun streamGenerate(message: String, conversationId: String?): Flux<GenerateResponse> {
        val request = GenerateRequest(
            message = message,
            conversationId = conversationId,
            stream = true
        )

        return webClient.post()
            .uri("$aiServiceUrl/api/v1/generate/stream")
            .bodyValue(request)
            .retrieve()
            .bodyToFlux(GenerateResponse::class.java)
    }
}
