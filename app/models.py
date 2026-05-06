from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    session_id: str | None = None
    messages: list[ChatMessage] = Field(min_length=1)
    use_search: Literal["auto", "on", "off"] = "auto"
    max_tokens: int | None = None
    temperature: float = 0.7


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
