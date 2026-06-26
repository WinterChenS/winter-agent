from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


class GenerateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message: str
    conversation_id: Optional[str] = Field(None, alias="conversationId")
    agent_id: Optional[str] = Field(None, alias="agentId")
    message_id: Optional[str] = Field(None, alias="messageId")
    stream: bool = True

