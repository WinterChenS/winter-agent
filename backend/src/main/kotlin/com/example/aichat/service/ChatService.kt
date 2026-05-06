package com.example.aichat.service

import com.example.aichat.client.AIClient
import org.springframework.stereotype.Service
import reactor.core.publisher.Flux

@Service
class ChatService(
    private val aiClient: AIClient
) {

    fun streamChat(message: String, conversationId: String?): Flux<String> {
        return aiClient.streamGenerate(message, conversationId)
            .map { response -> response.token }
    }
}
