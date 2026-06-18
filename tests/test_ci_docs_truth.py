from pathlib import Path


def test_ci_docs_truth():
    text = Path("docs/ci.md").read_text(encoding="utf-8")
    assert "sourcepack diff . --ci" in text
    assert "report artifact" in text.lower() and "sensitive" in text.lower()
    assert "Hosted CI result: unavailable from this environment" in text
    assert "docs/ci.md" in Path("README.md").read_text(encoding="utf-8")
