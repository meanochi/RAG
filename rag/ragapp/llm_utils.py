"""Small helpers around the LLM: robust structured prediction with a JSON fallback."""
from __future__ import annotations

import json
from typing import Type, TypeVar

from llama_index.core.llms import LLM
from llama_index.core.prompts import PromptTemplate
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def _extract_json_blob(text: str) -> str:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"No JSON object in LLM output: {text[:200]!r}")
    return text[start : end + 1]


async def predict_structured(
    llm: LLM, output_cls: Type[T], prompt: PromptTemplate, **prompt_args
) -> T:
    """Try native structured prediction (tool calling); fall back to JSON-in-text."""
    try:
        return await llm.astructured_predict(output_cls, prompt, **prompt_args)
    except Exception:
        schema = json.dumps(output_cls.model_json_schema(), ensure_ascii=False)
        raw = await llm.acomplete(
            prompt.format(**prompt_args)
            + "\n\nReturn ONLY a valid JSON object matching this schema, no prose:\n"
            + schema
        )
        return output_cls.model_validate_json(_extract_json_blob(raw.text))
