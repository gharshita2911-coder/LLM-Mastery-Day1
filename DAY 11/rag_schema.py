from typing import Literal

from pydantic import BaseModel

from pydantic import Field


class SourceChunk(BaseModel):

    chunkId: str = Field(...)

    snippet: str = Field(...)


class RAGStructuredOutput(BaseModel):

    answer: str = Field(...)

    confidence: Literal[
        "high",
        "medium",
        "low"
    ]

    sources: list[SourceChunk]