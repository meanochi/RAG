"""Stage 3 — build the structured knowledge base from the md corpus.

Usage:  python extract.py

Writes rag/data/extracted_knowledge.json (decisions / rules / warnings / changes,
each with source refs and observed_at dates). The workflow's router uses this
file for list / latest / time-window questions.
"""
import asyncio

from ragapp import config, extraction, models


def main() -> None:
    config.require_env("COHERE_API_KEY")
    kb = asyncio.run(extraction.run(models.get_llm(temperature=0.0)))
    counts = {k: len(v) for k, v in kb["items"].items()}
    print(f"\nSaved {config.KNOWLEDGE_FILE}")
    print(f"Extracted items: {counts}")


if __name__ == "__main__":
    main()
