from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.base import APIModel

ReasoningEffort = Literal["low", "medium", "high"]


def _normalize_legacy_effort(value: object) -> object:
    if value == "automatic":
        return "medium"
    return value


class AssistantModelOption(APIModel):
    id: str
    label: str
    provider: str
    available: bool
    supported_efforts: list[ReasoningEffort] = Field(default_factory=list)
    unavailable_reason: str | None = None


class AssistantModelCatalog(APIModel):
    models: list[AssistantModelOption] = Field(default_factory=list)
    default_model_id: str | None = None
    chat_enabled: bool = False
    status_message: str | None = None


class AssistantChatRequest(APIModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None
    model_id: str = Field(min_length=1)
    effort: ReasoningEffort = "medium"
    project_id: str | None = None

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message cannot be blank")
        return stripped

    @field_validator("conversation_id", "project_id")
    @classmethod
    def validate_uuid(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            UUID(value)
        except ValueError as error:
            raise ValueError("id must be a valid UUID") from error
        return value


class AssistantMessageRead(APIModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    project_id: str | None = None
    project_name: str | None = None
    model_id: str | None = None
    effort: ReasoningEffort | None = None
    created_at: datetime

    @field_validator("effort", mode="before")
    @classmethod
    def normalize_effort(cls, value: object) -> object:
        return _normalize_legacy_effort(value)


class AssistantConversationSummary(APIModel):
    id: str
    title: str
    model_id: str
    effort: ReasoningEffort
    created_at: datetime
    updated_at: datetime

    @field_validator("effort", mode="before")
    @classmethod
    def normalize_effort(cls, value: object) -> object:
        return _normalize_legacy_effort(value)


class AssistantConversationRead(AssistantConversationSummary):
    messages: list[AssistantMessageRead] = Field(default_factory=list)
