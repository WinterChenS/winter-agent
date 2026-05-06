from langchain_openai import ChatOpenAI
from graph.state import State
from config import settings


async def llm_node(state: State):
    llm = ChatOpenAI(
        model=settings.model_name,
        temperature=settings.temperature,
        streaming=True,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )
    
    response = await llm.ainvoke(state["messages"])
    return {"output": response.content}
