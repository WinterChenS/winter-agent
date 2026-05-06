# 长期记忆

## 项目基本信息

- **项目名称**：ai-chat-backend
- **技术栈**：Java 21 + Spring Boot 3.4.5 + Maven + WebFlux（已从 Kotlin Gradle 迁移）
- **包路径**：com.example.aichat
- **端口**：8080
- **下游 AI 服务**：http://localhost:8000（可在 application.yml 中配置 aichat.ai-service-url）

## 架构

SSE 流式聊天后端，核心链路：ChatController → ChatService → AIClient → 下游 FastAPI AI 服务

## 模型层

使用 Java 21 record 代替 Kotlin data class：
- ChatRequest / ChatResponse（前端模型）
- GenerateRequest / GenerateResponse（AI 服务模型，含 @JsonProperty 映射）

## 构建

`mvn package -DskipTests` 打包，产物在 target/*.jar

## 用户偏好

- 偏好中文交流
- 先完成任务再汇报
- 增量测试工作流
- Ant Design 规范 UI
- 后端返回具体中文错误信息
