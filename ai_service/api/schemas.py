from pydantic import BaseModel


class GenerateRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    stream: bool = True

