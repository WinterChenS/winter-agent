package com.example.aichat.controller

import com.example.aichat.model.ChatRequest
import com.example.aichat.service.ChatService
import org.springframework.http.MediaType
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController
import reactor.core.publisher.Flux

@RestController
@RequestMapping("/api/chat")
class ChatController(
    private val chatService: ChatService
) {

    @PostMapping(value = ["/stream"], produces = ["text/event-stream"])
    fun streamChat(@RequestBody request: ChatRequest): Flux<String> {
        return chatService.streamChat(request.message, request.conversationId)
            .map { token ->
                val jsonContent = token.replace("\\", "\\\\")
                    .replace("\"", "\\\"")
                    .replace("\n", "\\n")
                "event:token\ndata:{\"content\":\"$jsonContent\"}\n\n"
            }
            .onErrorResume { error ->
                Flux.just("event:error\ndata:{\"error\":\"AI 服务繁忙，请稍后再试\"}\n\n")
            }
    }
}
