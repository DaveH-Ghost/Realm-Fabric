"""Request bodies for realm-studio API routes."""

from pydantic import BaseModel, Field


class CommandRequest(BaseModel):
    line: str = Field(min_length=1)


class ActiveAgentRequest(BaseModel):
    name_or_id: str = Field(min_length=1)


class TurnRequest(BaseModel):
    agent_id: str | None = None
    include_examples: bool | None = None


class EventRequest(BaseModel):
    text: str = Field(min_length=1)
