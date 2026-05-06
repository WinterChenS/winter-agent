FROM gradle:8.5-jdk17 AS builder

WORKDIR /app

COPY build.gradle.kts settings.gradle.kts ./
COPY gradle/ ./gradle/
COPY src/ ./src/

RUN gradle bootJar --no-daemon

FROM eclipse-temurin:17-jre-alpine

WORKDIR /app

COPY --from=builder /app/build/libs/*.jar app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "app.jar"]
