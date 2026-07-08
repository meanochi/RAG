"""Stage 3, part 2 — querying the extracted knowledge base.

The store answers the question shapes semantic search is bad at:
full lists ("all the decisions"), recency ("the current rule"),
and hard time windows ("flagged in the last week").
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config
from .schema import StructuredQuerySpec

_TEXT_FIELDS = ("title", "summary", "rule", "notes", "area", "message", "description", "scope")


class StructuredStore:
    def __init__(self, path: Path | None = None):
        self.path = path or config.KNOWLEDGE_FILE
        self._kb: dict | None = None

    @property
    def available(self) -> bool:
        return self.path.exists()

    def _knowledge(self) -> dict:
        if self._kb is None:
            self._kb = json.loads(self.path.read_text(encoding="utf-8"))
        return self._kb

    def describe(self) -> str:
        """One-line summary for the router prompt / UI."""
        if not self.available:
            return "structured store not built"
        items = self._knowledge()["items"]
        return ", ".join(f"{k}: {len(v)}" for k, v in items.items())

    def query(self, spec: StructuredQuerySpec) -> list[dict]:
        items = self._knowledge()["items"]
        types = spec.item_types or list(items.keys())

        results: list[dict] = []
        for item_type in types:
            for item in items.get(item_type, []):
                results.append({"item_type": item_type, **item})

        if spec.date_from:
            results = [r for r in results if (r.get("observed_at") or "") >= spec.date_from[:10]]
        if spec.date_to:
            results = [r for r in results if (r.get("observed_at") or "9999") <= spec.date_to[:10]]

        if spec.tags:
            wanted = {t.lower() for t in spec.tags}
            results = [
                r for r in results
                if wanted & {t.lower() for t in r.get("tags", [])}
                or (r.get("scope") or "").lower() in wanted
                or (r.get("area") or "").lower() in wanted
            ]

        if spec.keywords:
            def matches(r: dict) -> bool:
                haystack = " ".join(str(r.get(f) or "") for f in _TEXT_FIELDS).lower()
                haystack += " " + " ".join(r.get("tags", [])).lower()
                return any(k.lower() in haystack for k in spec.keywords)

            results = [r for r in results if matches(r)]

        # newest first — when the user asks "what's current", the top item wins
        results.sort(key=lambda r: r.get("observed_at") or "", reverse=True)
        if spec.latest_only and results:
            results = results[: min(5, len(results))]
        return results[: spec.limit]
