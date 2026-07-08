"""Stage 3, part 1 — structured data extraction from the md corpus.

Walks every tool's md files, asks the LLM to pull out decisions / rules /
warnings / changes, and assembles a single knowledge-base JSON that the
structured query path can answer from reliably (lists, "latest", time ranges).
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone

from llama_index.core.llms import LLM
from llama_index.core.prompts import PromptTemplate

from . import config, corpus
from .llm_utils import predict_structured
from .schema import ExtractedItems, SourceRef

EXTRACTION_PROMPT = PromptTemplate(
    """You are indexing internal documentation written by an agentic coding tool
(named "{tool}") for a software project. Extract structured items from the text.

Item types:
- decisions: technical decisions that were made (what was chosen and why).
- rules: standing instructions/conventions that must be followed.
- warnings: fragile or sensitive areas flagged as "be careful" / "do not touch" / "breaks silently".
- changes: concrete changes to the system (schema/API/config), e.g. a column or endpoint added or removed.

Guidelines:
- Extract only items genuinely present in the text. Empty lists are fine.
- summary/rule/message/description should be a short, self-contained sentence
  (in the language the text uses — keep Hebrew as Hebrew).
- If a date (like 2026-07-02) is attached to an item in the text, put it in
  observed_at as YYYY-MM-DD. Otherwise leave observed_at empty.
- Do not invent tags; use short lowercase topics like db, ui, security, images.

File: {file}

Text:
---------------------
{text}
---------------------
"""
)

_ID_PREFIX = {"decisions": "dec", "rules": "rule", "warnings": "warn", "changes": "chg"}
_MAX_SECTION_CHARS = 7000


def _split_sections(text: str) -> list[str]:
    """Split long files on top-level headings so each LLM call stays focused."""
    if len(text) <= _MAX_SECTION_CHARS:
        return [text]
    parts = re.split(r"(?m)^(?=#{1,2} )", text)
    sections, buf = [], ""
    for part in parts:
        if len(buf) + len(part) > _MAX_SECTION_CHARS and buf:
            sections.append(buf)
            buf = ""
        buf += part
    if buf.strip():
        sections.append(buf)
    return sections


def _nearest_anchor(section: str) -> str | None:
    match = re.search(r"(?m)^#{1,6} .+$", section)
    return match.group(0).strip() if match else None


async def extract_knowledge(llm: LLM) -> dict:
    """Run extraction over the whole corpus and return the knowledge-base dict."""
    files_by_tool = corpus.discover_files()
    items: dict[str, list[dict]] = {t: [] for t in _ID_PREFIX}
    sources: list[dict] = []
    counters = {t: 0 for t in _ID_PREFIX}

    for tool, files in files_by_tool.items():
        tool_files = []
        for path in files:
            rel = str(path.relative_to(config.PROJECT_ROOT))
            text = path.read_text(encoding="utf-8")
            mtime = datetime.fromtimestamp(
                path.stat().st_mtime, tz=timezone.utc
            ).isoformat(timespec="seconds")
            tool_files.append({"path": rel, "last_modified": mtime})
            print(f"  extracting {tool}: {rel}")

            for section in _split_sections(text):
                if not section.strip():
                    continue
                try:
                    extracted = await predict_structured(
                        llm, ExtractedItems, EXTRACTION_PROMPT,
                        tool=tool, file=rel, text=section,
                    )
                except Exception as err:  # keep going — one bad section shouldn't kill the run
                    print(f"    ! extraction failed for a section of {rel}: {err}")
                    continue

                anchor = _nearest_anchor(section)
                for item_type in _ID_PREFIX:
                    for item in getattr(extracted, item_type):
                        counters[item_type] += 1
                        item.id = f"{_ID_PREFIX[item_type]}-{counters[item_type]:03d}"
                        item.source = SourceRef(tool=tool, file=rel, anchor=anchor)
                        if not item.observed_at:
                            item.observed_at = mtime[:10]
                        items[item_type].append(item.model_dump())
        sources.append({"tool": tool, "files": tool_files})

    return {
        "schema_version": config.SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": sources,
        "items": items,
    }


def save_knowledge(kb: dict) -> None:
    config.KNOWLEDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.KNOWLEDGE_FILE.write_text(
        json.dumps(kb, ensure_ascii=False, indent=2), encoding="utf-8"
    )


async def run(llm: LLM) -> dict:
    kb = await extract_knowledge(llm)
    save_knowledge(kb)
    return kb


if __name__ == "__main__":
    from . import models

    config.require_env("COHERE_API_KEY")
    result = asyncio.run(run(models.get_llm()))
    counts = {k: len(v) for k, v in result["items"].items()}
    print(f"\nSaved {config.KNOWLEDGE_FILE}: {counts}")
