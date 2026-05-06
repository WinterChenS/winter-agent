import os
import warnings
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# 屏蔽上游库(LangGraph)内部抛出的一些即将废弃但在当前版本完全无害的警告，保持控制台输出干净
warnings.filterwarnings("ignore", message=".*allowed_objects.*")

# 主动加载 .env 到操作系统环境变量，让 LangChain 核心代码能检测到全局环境变量配置
load_dotenv()


# 配置类，使用了 Pydantic 框架，方便项目直接从系统环境变量或 `.env` 配置文件读取信息
class Settings(BaseSettings):
    # ============ 基础的大模型配置 ============
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-3.5-turbo"
    max_tokens: int = 1000
    temperature: float = 0.7  # 模型回复的随机性度量，0.7是一个兼顾严谨与发散的适中值

    # ============ 数据库配置 ============
    postgres_uri: str = "postgresql://postgres:postgres@localhost:5432/aichat"

    # ============ LangSmith 可观测性配置 ============
    langchain_tracing_v2: str = "false"
    langchain_endpoint: str = "https://api.smith.langchain.com"
    langchain_api_key: str = ""
    langchain_project: str = "default"

    class Config:
        # 指明去当前执行根目录去寻找 '.env' 文件自动解析到上面这些变量里
        env_file = ".env"
        # 忽略多余的环境变量传入，避免程序因为无用配置报错
        extra = "ignore"


# 实例化配置对象，项目中其他文件只需 import settings 就能快速获取配置内容
settings = Settings()

# 核心：将 Pydantic 抓取到的可能来自各途径(如 IDEA 启动配置、.env)的 LangSmith 配置
# 强制写入操作系统的深层环境变量中，确保 LangChain 底层追踪器绝对能读取到。
langchain_key = os.environ.get("LANGCHAIN_API_KEY") or settings.langchain_api_key

if langchain_key:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"  # 只要配了 Key 就自动强制开启追踪
    os.environ["LANGCHAIN_ENDPOINT"] = os.environ.get("LANGCHAIN_ENDPOINT", settings.langchain_endpoint)
    os.environ["LANGCHAIN_API_KEY"] = langchain_key

    project_name = os.environ.get("LANGCHAIN_PROJECT") or settings.langchain_project
    os.environ["LANGCHAIN_PROJECT"] = project_name
    print(f"✅ LangSmith 追踪探针已启动！数据将上报至项目: {project_name}")
else:
    print("⚠️ 未检测到 LANGCHAIN_API_KEY，LangSmith 追踪功能已关闭。")
