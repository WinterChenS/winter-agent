from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    model_name: str = "gpt-3.5-turbo"
    max_tokens: int = 1000
    temperature: float = 0.7

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
