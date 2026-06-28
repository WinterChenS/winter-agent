package com.example.aichat.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.codec.json.Jackson2JsonDecoder;
import org.springframework.http.codec.json.Jackson2JsonEncoder;
import org.springframework.security.core.context.ReactiveSecurityContextHolder;
import org.springframework.web.reactive.function.client.ClientRequest;
import org.springframework.web.reactive.function.client.WebClient;

@Configuration
public class WebFluxConfig {

    @Bean
    public WebClient webClient() {
        return WebClient.builder()
                .codecs(configurer ->
                        configurer.defaultCodecs().maxInMemorySize(16 * 1024 * 1024))
                .build();
    }

    @Bean
    public WebClient agentWebClient(@Value("${aichat.ai-service-url}") String baseUrl) {
        ObjectMapper mapper = new ObjectMapper();
        mapper.setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE);

        return WebClient.builder().baseUrl(baseUrl)
                .filter((request, next) ->
                        ReactiveSecurityContextHolder.getContext()
                                .map(ctx -> {
                                    String username = ctx.getAuthentication().getName();
                                    return ClientRequest.from(request)
                                            .header("X-User", username != null ? username : "system")
                                            .build();
                                })
                                .defaultIfEmpty(ClientRequest.from(request)
                                        .header("X-User", "system")
                                        .build())
                                .flatMap(next::exchange)
                )
                .codecs(c -> {
                    c.defaultCodecs().maxInMemorySize(16 * 1024 * 1024);
                    c.defaultCodecs().jackson2JsonEncoder(new Jackson2JsonEncoder(mapper));
                    c.defaultCodecs().jackson2JsonDecoder(new Jackson2JsonDecoder(mapper));
                })
                .build();
    }
}
