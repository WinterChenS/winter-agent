from typing import TypedDict, List, Annotated
from langgraph.graph.message import add_messages


class State(TypedDict):
    messages: Annotated[List, add_messages]
    input: str
    output: str
