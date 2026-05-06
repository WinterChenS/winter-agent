from langchain_openai import ChatOpenAI
from graph.state import State
from config import settings


# 定义一个异步的大模型节点处理函数
# state 参数即为上面 state.py 中定义的“公共记事本”，其中包含了当前对话的历史上下文
async def llm_node(state: State):
    # 1. 初始化大模型客户端 (ChatOpenAI)
    # 这里的参数通过读取 config.py 中的环境变量来动态设置
    llm = ChatOpenAI(
        model=settings.model,                   # 模型名称 (比如 gpt-3.5-turbo 等)
        temperature=settings.temperature,       # temperature 控制输出多样性：越小越严谨，越大越有想象力
        streaming=True,                         # 开启流式输出功能 (即打字机效果)
        api_key=settings.api_key,               # 大模型的真实 API 密钥
        base_url=settings.base_url,             # API基础路径 (可以在代理环境或类 OpenAI 格式的服务中使用)
    )
    
    # 2. 调用大模型，把当前状态里按顺序累积的这些"messages"(历史消息)一并传给大语言模型
    # ainvoke 代表异步调用 (async invoke) 的意思
    response = await llm.ainvoke(state["messages"])

    # 3. 返回的数据将会被系统拿去更新 State(状态)
    # 按照我们在 state.py 中的 add_messages 配置合并规则，这里的 response 内容会自动补充进 messages 列表内部的末尾
    return {"messages": [response]}
