package com.example.aichat.controller;

import com.example.aichat.model.ChatRequest;
import com.example.aichat.model.GenerateResponse;
import com.example.aichat.service.ChatService;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
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
    private final ObjectMapper objectMapper = new ObjectMapper();

    public ChatController(ChatService chatService) {
        this.chatService = chatService;
    }

    @PostMapping(value = "/stream", produces = "text/event-stream")
    public Flux<String> streamChat(@RequestBody ChatRequest request) {
        return chatService.streamChat(request.message(), request.conversationId())
                .map(this::toPayloadJson)
                .onErrorResume(error -> Flux.just("{\"type\":\"error\",\"error\":\"AI 服务繁忙，请稍后再试\"}"));
    }

    private String toPayloadJson(GenerateResponse response) {
        Map<String, Object> payload = new LinkedHashMap<>();

        if (response.type() != null) {
            payload.put("type", response.type());
        }
        if (response.token() != null) {
            payload.put("token", response.token());
        }
        if (response.content() != null) {
            payload.put("content", response.content());
        }
        if (response.toolName() != null) {
            payload.put("toolName", response.toolName());
        }
        if (response.conversationId() != null) {
            payload.put("conversationId", response.conversationId());
        }
        if (response.error() != null) {
            payload.put("error", response.error());
        }
        if (response.steps() != null && !response.steps().isEmpty()) {
            payload.put("steps", response.steps());
        }
        if (response.reason() != null) {
            payload.put("reason", response.reason());
        }

        if (payload.isEmpty()) {
            return "{}";
        }

        try {
            // 使用 Jackson 进行完整的 JSON 序列化
            return objectMapper.writeValueAsString(payload);
        } catch (Exception e) {
            // Fallback to manual JSON building if ObjectMapper fails
            return buildJsonManually(payload);
        }
    }

    @SuppressWarnings("unchecked")
    private String buildJsonManually(Map<String, Object> payload) {
        StringBuilder json = new StringBuilder("{");
        int index = 0;
        for (Map.Entry<String, Object> entry : payload.entrySet()) {
            if (index++ > 0) {
                json.append(',');
            }
            json.append('"').append(entry.getKey()).append("\":");

            Object value = entry.getValue();
            if (value == null) {
                json.append("null");
            } else if (value instanceof String) {
                json.append('"').append(escape((String) value)).append('"');
            } else if (value instanceof Number) {
                json.append(value);
            } else if (value instanceof Boolean) {
                json.append(value);
            } else if (value instanceof List) {
                // Serialize list as JSON array
                json.append(serializeList((List<?>) value));
            } else {
                json.append('"').append(escape(value.toString())).append('"');
            }
        }
        json.append('}');
        return json.toString();
    }

    private String serializeList(List<?> list) {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < list.size(); i++) {
            if (i > 0) sb.append(",");
            Object item = list.get(i);
            if (item instanceof Map) {
                sb.append(serializeMap((Map<?, ?>) item));
            } else if (item instanceof String) {
                sb.append('"').append(escape((String) item)).append('"');
            } else if (item instanceof Number || item instanceof Boolean) {
                sb.append(item);
            } else {
                sb.append('"').append(escape(item.toString())).append('"');
            }
        }
        sb.append("]");
        return sb.toString();
    }

    private String serializeMap(Map<?, ?> map) {
        StringBuilder sb = new StringBuilder("{");
        int index = 0;
        for (Map.Entry<?, ?> entry : map.entrySet()) {
            if (index++ > 0) sb.append(",");
            sb.append('"').append(escape(entry.getKey().toString())).append("\":");
            Object value = entry.getValue();
            if (value == null) {
                sb.append("null");
            } else if (value instanceof String) {
                sb.append('"').append(escape((String) value)).append('"');
            } else if (value instanceof Number || value instanceof Boolean) {
                sb.append(value);
            } else {
                sb.append('"').append(escape(value.toString())).append('"');
            }
        }
        sb.append("}");
        return sb.toString();
    }

    private String escape(String raw) {
        return raw
                .replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r");
    }

    @GetMapping(value = "/history/{conversationId}", produces = "application/json")
    public Mono<String> getChatHistory(@PathVariable String conversationId) {
        return chatService.getChatHistory(conversationId);
    }
}
