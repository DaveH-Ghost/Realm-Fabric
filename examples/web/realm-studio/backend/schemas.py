"""Request bodies for realm-studio API routes."""

from pydantic import BaseModel, Field


class CommandRequest(BaseModel):
    line: str = Field(min_length=1)


class ActiveAgentRequest(BaseModel):
    name_or_id: str = Field(min_length=1)


class ActiveAreaRequest(BaseModel):
    area_id: str = Field(min_length=1)


class TurnRequest(BaseModel):
    agent_id: str | None = None
    include_examples: bool | None = None


class EventRequest(BaseModel):
    text: str = Field(min_length=1)


class CreateAreaRequest(BaseModel):
    area_id: str = Field(min_length=1)
    description: str = ""
    width: int = Field(default=5, ge=1)
    height: int = Field(default=5, ge=1)


class EditAreaRequest(BaseModel):
    area_id: str = Field(min_length=1)
    description: str | None = None
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)


class DeleteAreaRequest(BaseModel):
    area_id: str = Field(min_length=1)


class PromptBlockItem(BaseModel):
    type: str = Field(min_length=1)
    name: str | None = None
    content: str | None = None


class PromptBlocksRequest(BaseModel):
    blocks: list[PromptBlockItem] = Field(min_length=1)
