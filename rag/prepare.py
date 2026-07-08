"""Stage 1 — data preparation: load ➜ chunk ➜ embed (Cohere) ➜ index (Pinecone).

Usage:  python prepare.py [--keep-existing]

By default the Pinecone namespace is wiped first so re-runs never leave stale
vectors from files that changed or were deleted.
"""
import argparse
from collections import Counter

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter

from ragapp import config, corpus, models


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="do not wipe the Pinecone namespace before ingesting",
    )
    args = parser.parse_args()

    config.require_env("COHERE_API_KEY", "PINECONE_API_KEY")

    # -- Loading ------------------------------------------------------
    documents = corpus.load_documents()
    if not documents:
        raise SystemExit("No markdown docs found — check TOOL_SOURCES in ragapp/corpus.py")
    by_tool = Counter(d.metadata["tool"] for d in documents)
    print(f"Loaded {len(documents)} documents: {dict(by_tool)}")

    # -- Chunking: split on markdown structure, then bound chunk size --
    md_nodes = MarkdownNodeParser().get_nodes_from_documents(documents)
    splitter = SentenceSplitter(
        chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP
    )
    nodes = splitter(md_nodes, show_progress=True)
    print(f"Chunked into {len(nodes)} nodes")

    # -- Embedding + Indexing into Pinecone ----------------------------
    vector_store = models.get_vector_store(create_if_missing=True)
    if not args.keep_existing:
        models.clear_namespace()
        print(f"Cleared namespace '{config.PINECONE_NAMESPACE}'")

    VectorStoreIndex(
        nodes=nodes,
        storage_context=StorageContext.from_defaults(vector_store=vector_store),
        embed_model=models.get_embed_model(input_type="search_document"),
        show_progress=True,
    )
    print(
        f"Done — {len(nodes)} vectors in Pinecone index "
        f"'{config.PINECONE_INDEX_NAME}' / namespace '{config.PINECONE_NAMESPACE}'"
    )


if __name__ == "__main__":
    main()
