"""Stage 1: corpus discovery must map each tool to its own files and attach
correct source metadata — this is what lets every answer cite "which tool,
which file".
"""
from pathlib import Path

from ragapp import corpus


def _write(path: Path, text: str = "# כותרת\n\nתוכן לדוגמה.\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_discover_files_maps_each_tool_to_its_own_patterns(tmp_path: Path):
    _write(tmp_path / "CLAUDE.md")
    _write(tmp_path / ".cursor" / "rules" / "design.md")
    _write(tmp_path / ".kiro" / "steering" / "tech.md")
    _write(tmp_path / "docs" / "blueprint.md")
    _write(tmp_path / "README.md")  # not owned by any tool — must be ignored

    found = corpus.discover_files(tmp_path)

    assert found["claude_code"] == [tmp_path / "CLAUDE.md"]
    assert found["cursor"] == [tmp_path / ".cursor" / "rules" / "design.md"]
    assert found["kiro"] == [tmp_path / ".kiro" / "steering" / "tech.md"]
    assert found["firebase_studio"] == [tmp_path / "docs" / "blueprint.md"]


def test_discover_files_omits_tools_with_no_files(tmp_path: Path):
    _write(tmp_path / "CLAUDE.md")
    found = corpus.discover_files(tmp_path)
    assert "kiro" not in found
    assert "cursor" not in found


def test_load_documents_attaches_source_metadata(tmp_path: Path):
    _write(tmp_path / ".kiro" / "steering" / "product.md", "# מוצר\n\nתיאור.\n")

    documents = corpus.load_documents(tmp_path)

    assert len(documents) == 1
    doc = documents[0]
    assert doc.metadata["tool"] == "kiro"
    assert doc.metadata["file"] == str(Path(".kiro") / "steering" / "product.md")
    assert doc.metadata["hash"].startswith("sha256:")
    assert "last_modified" in doc.metadata


def test_load_documents_excludes_bookkeeping_fields_from_embedding_and_llm(tmp_path: Path):
    _write(tmp_path / "CLAUDE.md")
    doc = corpus.load_documents(tmp_path)[0]
    assert "hash" in doc.excluded_embed_metadata_keys
    assert "hash" in doc.excluded_llm_metadata_keys
    assert "file_name" in doc.excluded_embed_metadata_keys
