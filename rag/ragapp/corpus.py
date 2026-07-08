"""Discover and load the markdown docs each agentic coding tool keeps in the repo.

Every document carries metadata (tool, relative path, mtime, hash) so that
retrieval results can always be traced back to "which tool said this, where".
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from llama_index.core import Document, SimpleDirectoryReader

from . import config

# tool name -> glob patterns relative to the project root
TOOL_SOURCES: dict[str, list[str]] = {
    "claude_code": ["CLAUDE.md", ".claude/**/*.md"],
    "cursor": [".cursor/**/*.md"],
    "kiro": [".kiro/**/*.md"],
    "firebase_studio": ["docs/blueprint.md"],
}


def discover_files(root: Path | None = None) -> dict[str, list[Path]]:
    """Map each tool to the md files it owns (sorted, deduplicated)."""
    root = root or config.PROJECT_ROOT
    found: dict[str, list[Path]] = {}
    for tool, patterns in TOOL_SOURCES.items():
        files: set[Path] = set()
        for pattern in patterns:
            files.update(p for p in root.glob(pattern) if p.is_file())
        if files:
            found[tool] = sorted(files)
    return found


def _file_metadata(tool: str, root: Path):
    def build(path_str: str) -> dict:
        path = Path(path_str)
        raw = path.read_bytes()
        return {
            "tool": tool,
            "file": str(path.relative_to(root)),
            "file_name": path.name,
            "last_modified": datetime.fromtimestamp(
                path.stat().st_mtime, tz=timezone.utc
            ).isoformat(timespec="seconds"),
            "hash": "sha256:" + hashlib.sha256(raw).hexdigest()[:16],
        }

    return build


def load_documents(root: Path | None = None) -> list[Document]:
    """Load all tools' md files as LlamaIndex Documents with source metadata."""
    root = root or config.PROJECT_ROOT
    documents: list[Document] = []
    for tool, files in discover_files(root).items():
        reader = SimpleDirectoryReader(
            input_files=[str(f) for f in files],
            file_metadata=_file_metadata(tool, root),
        )
        documents.extend(reader.load_data())
    for doc in documents:
        # the hash is bookkeeping — keep it out of the embedding and the LLM prompt
        doc.excluded_embed_metadata_keys = ["hash", "file_name"]
        doc.excluded_llm_metadata_keys = ["hash", "file_name"]
    return documents
