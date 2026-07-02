from pathlib import Path


def test_ci_docs_truth():
    text = Path("docs/ci.md").read_text(encoding="utf-8")
    assert "sourcepack diff . --ci" in text
    assert "report artifact" in text.lower() and "sensitive" in text.lower()
    assert "Hosted CI result: unavailable from this environment" in text
    assert "docs/ci.md" in Path("README.md").read_text(encoding="utf-8")


def test_github_action_quickstart_materializes_pr_patch_from_merge_base():
    text = Path("docs/github-action-quickstart.md").read_text(encoding="utf-8")
    assert "ref: ${{ github.event.pull_request.base.sha }}" in text
    assert "git fetch --no-tags origin pull/${{ github.event.pull_request.number }}/head:sourcepack-pr-head" in text
    assert 'MERGE_BASE="$(git merge-base HEAD sourcepack-pr-head)"' in text
    assert 'git diff --binary "$MERGE_BASE" sourcepack-pr-head > /tmp/sourcepack-pr.patch' in text
    assert "git apply --index /tmp/sourcepack-pr.patch" in text
    assert "git diff --binary HEAD sourcepack-pr-head" not in text
    assert "git fetch --no-tags --depth=1 origin pull/" not in text


def test_github_action_quickstart_documents_push_no_diff_limit():
    text = Path("docs/github-action-quickstart.md").read_text(encoding="utf-8")
    assert "The `pull_request` path is the guardrail path." in text
    assert "a clean push checkout may have no diff for SourcePack to inspect" in text
