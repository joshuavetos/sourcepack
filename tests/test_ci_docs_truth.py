from pathlib import Path


def test_ci_docs_truth():
    text = Path("docs/ci.md").read_text(encoding="utf-8")
    assert "sourcepack diff . --ci" in text
    assert "report artifact" in text.lower() and "sensitive" in text.lower()
    assert "Hosted CI result: unavailable from this environment" in text
    assert "docs/ci.md" in Path("README.md").read_text(encoding="utf-8")


def test_github_action_quickstart_materializes_pr_delta_with_mixed_reset():
    text = Path("docs/github-action-quickstart.md").read_text(encoding="utf-8")
    checkout = text.index("- name: Check out PR head")
    materialize = text.index("- name: Materialize PR delta as workspace changes")
    diff = text.index("- run: sourcepack diff . --ci")
    assert checkout < materialize < diff
    assert "ref: ${{ github.event.pull_request.head.sha }}" in text
    assert "fetch-depth: 0" in text
    assert "git fetch --no-tags origin ${{ github.event.pull_request.base.sha }}" in text
    assert "git diff --name-only -z --diff-filter=A ${{ github.event.pull_request.base.sha }} HEAD > /tmp/sourcepack-pr-added.z" in text
    assert "git reset --mixed ${{ github.event.pull_request.base.sha }}" in text
    assert "git add --intent-to-add -f --pathspec-from-file=/tmp/sourcepack-pr-added.z --pathspec-file-nul" in text
    assert "ref: ${{ github.event.pull_request.base.sha }}" not in text
    assert "git apply --index /tmp/sourcepack-pr.patch" not in text


def test_github_action_quickstart_explains_clean_pr_checkout_is_unsafe():
    text = Path("docs/github-action-quickstart.md").read_text(encoding="utf-8")
    assert "The `pull_request` trigger path is the actual PR guardrail path." in text
    assert "A clean PR checkout alone is structurally unsafe for local-diff validation" in text
    assert "no local workspace delta for `sourcepack diff . --ci` to inspect" in text
    assert "preserve PR additions that match `.gitignore` as tracked intent-to-add paths" in text
    assert "including force-added ignored files" in text
    assert "make the PR delta visible to SourcePack's diff engine as local workspace modifications" in text
    assert "Do not create, refresh, repair, or bless `.sourcepack/baseline/` inside pull-request CI." in text
    assert "A clean push checkout may contain no uncommitted diff matrix for SourcePack to inspect" in text
