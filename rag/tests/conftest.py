"""Shared fixtures and fakes for the RAG test suite.

None of these tests call Cohere or Pinecone — the workflow's external touch
points (LLM completion, structured prediction, the vector index, and the
response synthesizer) are all replaced with small fakes so the suite runs
offline and fast.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from llama_index.core.schema import NodeWithScore, TextNode

from ragapp.structured_store import StructuredStore


class FakeCompletion:
    def __init__(self, text: str):
        self.text = text


class FakeLLM:
    """Stands in for the Cohere LLM wherever the workflow calls .acomplete()."""

    def __init__(self, complete_text: str = "שאילתה מורחבת"):
        self.complete_text = complete_text
        self.calls: list[str] = []

    async def acomplete(self, prompt: str) -> FakeCompletion:
        self.calls.append(prompt)
        return FakeCompletion(self.complete_text)


class FakeRetriever:
    def __init__(self, nodes: list[NodeWithScore]):
        self._nodes = nodes

    async def aretrieve(self, query: str) -> list[NodeWithScore]:
        return self._nodes


class FakeIndex:
    """Returns a scripted sequence of retrieval results, one per as_retriever() call.

    The last entry repeats for any calls beyond the scripted sequence, so tests
    that only care about the first call or two don't need to pad the list.
    """

    def __init__(self, node_sequence: list[list[NodeWithScore]]):
        self.node_sequence = node_sequence
        self.calls = 0
        self.top_k_seen: list[int] = []

    def as_retriever(self, similarity_top_k: int) -> FakeRetriever:
        self.top_k_seen.append(similarity_top_k)
        idx = min(self.calls, len(self.node_sequence) - 1)
        self.calls += 1
        return FakeRetriever(self.node_sequence[idx])


def make_node(text: str, score: float, tool: str = "kiro", file: str = "a.md") -> NodeWithScore:
    node = TextNode(text=text, metadata={"tool": tool, "file": file})
    return NodeWithScore(node=node, score=score)


@pytest.fixture
def knowledge_base_path(tmp_path: Path) -> Path:
    kb = {
        "schema_version": "1.0",
        "generated_at": "2026-07-01T00:00:00+00:00",
        "sources": [],
        "items": {
            "decisions": [
                {
                    "id": "dec-001",
                    "title": "בחירת DB",
                    "summary": "נבחר Cloudflare D1 עבור נתונים יחסיים.",
                    "tags": ["db", "architecture"],
                    "observed_at": "2026-06-05",
                    "source": {"tool": "cursor", "file": "notes/decisions-log.md", "anchor": None},
                },
                {
                    "id": "dec-002",
                    "title": "וריאנטים של תמונות",
                    "summary": "4 גדלי WebP נשמרים ב-R2.",
                    "tags": ["images"],
                    "observed_at": "2026-06-12",
                    "source": {"tool": "cursor", "file": "notes/decisions-log.md", "anchor": None},
                },
            ],
            "rules": [
                {
                    "id": "rule-001",
                    "rule": "כל מסך חייב RTL",
                    "scope": "ui",
                    "notes": "",
                    "observed_at": "2026-07-01",
                    "source": {"tool": "cursor", "file": "rules/rtl-and-language.md", "anchor": None},
                }
            ],
            "warnings": [
                {
                    "id": "warn-001",
                    "area": "AuthGate",
                    "message": "לא לגעת בסדר העלייה של הקונטקסטים.",
                    "severity": "high",
                    "observed_at": "2026-07-03",
                    "source": {"tool": "kiro", "file": "steering/sensitive-areas.md", "anchor": None},
                }
            ],
            "changes": [
                {
                    "id": "chg-001",
                    "area": "recipes.source_url",
                    "description": "עמודה חדשה נוספה למיגרציה 013.",
                    "change_type": "added",
                    "observed_at": "2026-07-02",
                    "source": {"tool": "kiro", "file": "specs/ai-recipe-import/tasks.md", "anchor": None},
                }
            ],
        },
    }
    path = tmp_path / "extracted_knowledge.json"
    path.write_text(json.dumps(kb, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def store(knowledge_base_path: Path) -> StructuredStore:
    return StructuredStore(knowledge_base_path)


@pytest.fixture
def empty_store(tmp_path: Path) -> StructuredStore:
    """A store whose backing file doesn't exist — .available is False."""
    return StructuredStore(tmp_path / "missing.json")
