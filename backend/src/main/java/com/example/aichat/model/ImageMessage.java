package com.example.aichat.model;

/**
 * Unified image message type for SSE chart/image responses.
 * All images follow the path: matplotlib → PNG → MinIO → url → <img>
 */
public record ImageMessage(
        String type,
        String title,
        String url,
        Integer width,
        Integer height
) {
    public ImageMessage() {
        this("image", "", "", 1600, 900);
    }
}
