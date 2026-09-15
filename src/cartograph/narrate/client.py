"""LLM client abstraction.

A `Protocol` rather than a concrete class so the pipeline can be unit
tested with a fake client that returns canned structured output —
no API key or network access needed to verify the citation-enforcement
and caching logic, which is where the actual risk of bugs lives.
"""

from __future__ import annotations

import os
from typing import Protocol, TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)

DEFAULT_L0_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_L1_MODEL = "claude-sonnet-5"
DEFAULT_L2_MODEL = "claude-sonnet-5"


class NarrationClient(Protocol):
    def structured(self, system: str, user: str, schema: type[ModelT], model: str) -> ModelT: ...


class AnthropicNarrationClient:
    """Forces structured JSON output via a single required tool call.

    Temperature 0 and a caller-pinned model string, so the committed
    demo reports (milestone 6) are reproducible.
    """

    def __init__(self, api_key: str | None = None):
        import anthropic

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "No Anthropic API key found. Set ANTHROPIC_API_KEY or pass --api-key. "
                "Narration is BYO-key — this never uses a shared key."
            )
        self._client = anthropic.Anthropic(api_key=key)

    def structured(self, system: str, user: str, schema: type[ModelT], model: str) -> ModelT:
        tool_name = "emit_result"
        response = self._client.messages.create(
            model=model,
            max_tokens=2048,
            temperature=0,
            system=system,
            messages=[{"role": "user", "content": user}],
            tools=[
                {
                    "name": tool_name,
                    "description": "Emit the structured result.",
                    "input_schema": schema.model_json_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": tool_name},
        )
        for block in response.content:
            if block.type == "tool_use" and block.name == tool_name:
                return schema.model_validate(block.input)
        raise RuntimeError("Model did not return the required structured tool call.")
