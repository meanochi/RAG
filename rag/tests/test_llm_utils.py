"""predict_structured() must fall back to parsing JSON out of free-text when
the LLM doesn't support native structured/tool-calling output — Cohere models
vary in this support, so the fallback path is load-bearing, not decorative.
"""
import pytest

from ragapp.llm_utils import _extract_json_blob, predict_structured
from ragapp.schema import RouteDecision


def test_extract_json_blob_from_pure_json():
    assert _extract_json_blob('{"route": "semantic", "reason": "x"}') == (
        '{"route": "semantic", "reason": "x"}'
    )


def test_extract_json_blob_strips_surrounding_prose():
    text = 'Here is the answer:\n{"route": "structured", "reason": "list question"}\nDone.'
    assert _extract_json_blob(text) == '{"route": "structured", "reason": "list question"}'


def test_extract_json_blob_raises_without_json():
    with pytest.raises(ValueError):
        _extract_json_blob("no json here at all")


class _NoStructuredSupportLLM:
    """Simulates a model whose .astructured_predict raises (unsupported)."""

    async def astructured_predict(self, *_args, **_kwargs):
        raise NotImplementedError("this model doesn't support tool calling")

    async def acomplete(self, prompt: str):
        class _R:
            text = '{"route": "semantic", "reason": "fallback worked"}'

        return _R()


class _StructuredSupportLLM:
    async def astructured_predict(self, output_cls, prompt, **kwargs):
        return output_cls(route="structured", reason="native structured predict")


@pytest.mark.asyncio
async def test_predict_structured_uses_native_path_when_available():
    from llama_index.core.prompts import PromptTemplate

    result = await predict_structured(
        _StructuredSupportLLM(), RouteDecision, PromptTemplate("q: {q}"), q="x"
    )
    assert result.reason == "native structured predict"


@pytest.mark.asyncio
async def test_predict_structured_falls_back_to_json_parsing():
    from llama_index.core.prompts import PromptTemplate

    result = await predict_structured(
        _NoStructuredSupportLLM(), RouteDecision, PromptTemplate("q: {q}"), q="x"
    )
    assert result.route == "semantic"
    assert result.reason == "fallback worked"
