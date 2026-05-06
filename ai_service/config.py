from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    model_name: str = "gpt-3.5-turbo"
    max_tokens: int = 1000
    temperature: float = 0.7
    
    # 用户自定义环境变量
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-3.5-turbo"

    class Config:
        env_file = ".env"
        extra = "ignore"

    def get_api_key(self) -> str:
        """优先使用 API_KEY，如果未设置则使用 LLM_API_KEY"""
        return self.api_key or self.llm_api_key
    
    def get_base_url(self) -> str:
        """优先使用 BASE_URL，如果未设置则使用 LLM_BASE_URL"""
        return self.base_url or self.llm_base_url
    
    def get_model(self) -> str:
        """优先使用 MODEL，如果未设置则使用 MODEL_NAME"""
        return self.model or self.model_name


settings = Settings()
