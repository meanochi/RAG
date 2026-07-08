"""Stage 2: the event-driven Workflow itself.

Every external touch point (the router's LLMSingleSelector, structured-query
prediction, the vector index, and the response synthesizer) is faked so these
tests exercise the actual step/event wiring — validation, routing, the
retrieve-with-retry loop, and the structured/semantic fallback — without
calling Cohere or Pinecone.
"""
from types import SimpleNamespace

import pytest

from ragapp import config
from ragapp.workflow import RagWorkflow

from .conftest import FakeIndex, FakeLLM, make_node


def make_fake_selector(index: int):
    class _FakeSelector:
        @classmethod
        def from_defaults(cls, llm=None):
            return cls()

        async def aselect(self, choices, query):
            return SimpleNamespace(selections=[SimpleNamespace(index=index)])

    return _FakeSelector


def make_fake_synthesizer(answer_text: str):
    class _FakeResponse:
        def __str__(self):
            return answer_text

    class _FakeSynthesizer:
        async def asynthesize(self, query, nodes):
            return _FakeResponse()

    def factory(**kwargs):
        return _FakeSynthesizer()

    return factory


def fake_predict_structured(spec):
    async def _predict(llm, output_cls, prompt, **kwargs):
        return spec

    return _predict


def raising_synthesizer_factory(**kwargs):
    raise AssertionError("get_response_synthesizer should not be called on this path")


# ---------------------------------------------------------------- validation


@pytest.mark.asyncio
async def test_empty_query_is_rejected_without_touching_llm_or_index(empty_store):
    wf = RagWorkflow(index=None, llm=None, store=empty_store)
    result = await wf.run(query="   ")
    assert result["route"] == "validation"
    assert "לפחות שתי אותיות" in result["answer"]


@pytest.mark.asyncio
async def test_overly_long_query_is_rejected(empty_store):
    wf = RagWorkflow(index=None, llm=None, store=empty_store)
    result = await wf.run(query="x" * (config.MAX_QUERY_CHARS + 1))
    assert result["route"] == "validation"
    assert "ארוכה מדי" in result["answer"]


# ---------------------------------------------------------------- routing


@pytest.mark.asyncio
async def test_routes_to_semantic_when_structured_store_not_built(monkeypatch, empty_store):
    fake_index = FakeIndex([[make_node("טקסט רלוונטי", score=0.8)]])
    monkeypatch.setattr(
        "ragapp.workflow.get_response_synthesizer", make_fake_synthesizer("תשובה סמנטית")
    )
    wf = RagWorkflow(index=fake_index, llm=FakeLLM(), store=empty_store)

    result = await wf.run(query="מה הצבע העיקרי?")

    assert "structured store not built" in result["route"]
    assert result["answer"] == "תשובה סמנטית"
    assert result["sources"][0]["tool"] == "kiro"


@pytest.mark.asyncio
async def test_router_picks_structured_route_and_answers_from_it(monkeypatch, store):
    from ragapp.schema import StructuredQuerySpec

    monkeypatch.setattr("ragapp.workflow.LLMSingleSelector", make_fake_selector(index=1))
    monkeypatch.setattr(
        "ragapp.workflow.predict_structured",
        fake_predict_structured(StructuredQuerySpec(item_types=["decisions"])),
    )
    llm = FakeLLM(complete_text="יש שתי החלטות טכניות מתועדות.")
    wf = RagWorkflow(index=None, llm=llm, store=store)

    result = await wf.run(query="תן לי רשימה של כל ההחלטות הטכניות")

    assert result["route"] == "structured"
    assert result["answer"] == "יש שתי החלטות טכניות מתועדות."
    assert {s["item"] for s in result["sources"]} == {"decisions/dec-001", "decisions/dec-002"}


@pytest.mark.asyncio
async def test_structured_route_falls_back_to_semantic_when_no_matches(monkeypatch, store):
    from ragapp.schema import StructuredQuerySpec

    monkeypatch.setattr("ragapp.workflow.LLMSingleSelector", make_fake_selector(index=1))
    monkeypatch.setattr(
        "ragapp.workflow.predict_structured",
        fake_predict_structured(StructuredQuerySpec(keywords=["מונח-שלא-קיים-במאגר"])),
    )
    monkeypatch.setattr(
        "ragapp.workflow.get_response_synthesizer", make_fake_synthesizer("נענה סמנטית בסוף")
    )
    fake_index = FakeIndex([[make_node("טקסט", score=0.9)]])
    wf = RagWorkflow(index=fake_index, llm=FakeLLM(), store=store)

    result = await wf.run(query="שאלה שלא קיימת במאגר המובנה")

    assert "fallback to semantic" in result["route"]
    assert result["answer"] == "נענה סמנטית בסוף"


@pytest.mark.asyncio
async def test_router_llm_failure_defaults_to_semantic(monkeypatch, store):
    class _BrokenSelector:
        @classmethod
        def from_defaults(cls, llm=None):
            raise RuntimeError("selector unavailable")

    monkeypatch.setattr("ragapp.workflow.LLMSingleSelector", _BrokenSelector)
    monkeypatch.setattr(
        "ragapp.workflow.get_response_synthesizer", make_fake_synthesizer("תשובה חלופית")
    )
    fake_index = FakeIndex([[make_node("טקסט", score=0.9)]])
    wf = RagWorkflow(index=fake_index, llm=FakeLLM(), store=store)

    result = await wf.run(query="שאלה כלשהי")

    assert result["route"] == "semantic"
    assert result["answer"] == "תשובה חלופית"


# ---------------------------------------------------------------- retrieval + retry


@pytest.mark.asyncio
async def test_low_confidence_triggers_one_broadened_retry_then_succeeds(monkeypatch, empty_store):
    fake_index = FakeIndex(
        [
            [make_node("תוצאה חלשה", score=0.1)],
            [make_node("תוצאה טובה", score=0.9)],
        ]
    )
    monkeypatch.setattr(
        "ragapp.workflow.get_response_synthesizer", make_fake_synthesizer("תשובה סופית")
    )
    wf = RagWorkflow(index=fake_index, llm=FakeLLM(complete_text="שאילתה מורחבת"), store=empty_store)

    result = await wf.run(query="שאלה מעורפלת")

    assert fake_index.calls == 2
    assert fake_index.top_k_seen == [config.TOP_K, config.RETRY_TOP_K]
    assert "⚠️" not in result["answer"]
    assert result["answer"] == "תשובה סופית"


@pytest.mark.asyncio
async def test_persistent_low_confidence_stops_after_max_retries_and_warns(monkeypatch, empty_store):
    fake_index = FakeIndex(
        [
            [make_node("חלש 1", score=0.1)],
            [make_node("חלש 2", score=0.15)],
        ]
    )
    monkeypatch.setattr(
        "ragapp.workflow.get_response_synthesizer", make_fake_synthesizer("תשובה עם הסתייגות")
    )
    wf = RagWorkflow(index=fake_index, llm=FakeLLM(), store=empty_store)

    result = await wf.run(query="שאלה קשה")

    assert fake_index.calls == config.MAX_RETRIES + 1
    assert "⚠️" in result["answer"]
    assert "תשובה עם הסתייגות" in result["answer"]


@pytest.mark.asyncio
async def test_empty_results_after_retry_short_circuits_without_calling_synthesizer(
    monkeypatch, empty_store
):
    monkeypatch.setattr(
        "ragapp.workflow.get_response_synthesizer", raising_synthesizer_factory
    )
    fake_index = FakeIndex([[], []])
    wf = RagWorkflow(index=fake_index, llm=FakeLLM(), store=empty_store)

    result = await wf.run(query="שאלה שאין עליה שום מידע")

    assert fake_index.calls == config.MAX_RETRIES + 1
    assert "לא נמצא בתיעוד" in result["answer"]
