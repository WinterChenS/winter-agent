package com.example.aichat.model

import com.fasterxml.jackson.annotation.JsonProperty

data class ChatRequest(
    val message: String,
    @JsonProperty("conversationId") val conversationId: String? = null
)

data class ChatResponse(
    val content: String,
    @JsonProperty("conversationId") val conversationId: String? = null
)

data class GenerateRequest(
    val message: String,
    @JsonProperty("conversation_id") val conversationId: String? = null,
    val stream: Boolean = true
)

data class GenerateResponse(
    val token: String,
    @JsonProperty("conversation_id") val conversationId: String? = null
)
