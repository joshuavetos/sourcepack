"""Rendered Workbench coverage using the real local server and checked-in client.

Install with ``pip install -e '.[browser-test]'`` and ``playwright install chromium``.
These tests deliberately use Playwright directly instead of a pytest plugin so server,
browser, context, and temporary-repository lifetimes remain explicit.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from contextlib import contextmanager
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from sourcepack import workbench
from sourcepack.command_center import build_command_center_snapshot
from sourcepack.workbench import WorkbenchHandler, WorkbenchServer


TOKEN = "browser-test-session-token"
VIEWPORTS = ((1440, 1000), (900, 900), (620, 900), (360, 800))


def _report(verdict: str, *, prompt: str | None = None, hostile: bool = False) -> dict:
    marker = '<img id="injected-node" src=x onerror="window.pwned=true">' if hostile else "package evidence"
    report = {
        "schema_version": "traffic_report.v1",
        "verdict": verdict,
        "findings": [],
        "blockers": [{"id": "unsupported_dependency", "message": marker, "evidence": marker}] if verdict == "FAIL" else [],
        "warnings": [{"id": "review_warning", "message": marker, "evidence": marker}] if verdict == "WARN" else [],
        "evidence_items": [{"evidence_id": "package", "summary": marker}],
        "raw_patch_judgment": {},
    }
    if prompt is not None:
        report["remediation"] = {"agent_prompt": prompt, "items": [{"summary": "Use repository-supported APIs."}]}
    return report


def _snapshot(repo: Path, *, report=None, report_error=None, baseline="missing") -> dict:
    return build_command_center_snapshot(
        repo,
        baseline_reader=lambda _: {"state": baseline, "ok": baseline in {"present", "stale"}},
        policy_reader=lambda _: {"resolution_status": "PASS"},
        git_reader=lambda _: {"branch": "browser-tests", "head": "abc123"},
        status_reader=lambda _: {"ok": True, "status": {"automatic_mode_enabled": False}},
        report_reader=lambda _: (report, report_error),
    )


@contextmanager
def _server(repo: Path, monkeypatch, payload: dict | None = None):
    if payload is not None:
        monkeypatch.setattr(workbench, "command_center_payload", lambda _: payload)
    server = WorkbenchServer(("127.0.0.1", 0), WorkbenchHandler, repo, TOKEN)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as manager:
        launch_options = {"headless": True}
        if not Path(manager.chromium.executable_path).is_file() and shutil.which("google-chrome"):
            launch_options["channel"] = "chrome"
        instance = manager.chromium.launch(**launch_options)
        yield instance
        instance.close()


def _open(browser, base: str, *, viewport=(1280, 900), token=TOKEN):
    context = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]}, permissions=["clipboard-read", "clipboard-write"])
    page = context.new_page()
    console_errors: list[str] = []
    requests: list[str] = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: console_errors.append(str(error)))
    page.on("request", lambda request: requests.append(request.url))
    page.goto(f"{base}/?token={token}", wait_until="networkidle")
    return context, page, console_errors, requests


@pytest.mark.parametrize(
    ("name", "report", "report_error", "title", "label", "action_visible", "copy_visible", "message"),
    [
        ("pass", _report("PASS"), None, "Change Passed", "PASS", True, False, "Latest verdict: PASS"),
        ("warn", _report("WARN", prompt="Correct the warning."), None, "Review Warning", "WARN", False, True, "Latest verdict: WARN"),
        ("fail", _report("FAIL"), None, "Change Blocked", "FAIL", False, False, "Latest verdict: FAIL"),
        ("no-report", None, None, "No Report Available", "UNAVAILABLE", True, False, "Latest verdict: unavailable"),
        ("malformed", None, {"error": {"code": "artifact_malformed", "message": "The canonical report is malformed."}}, "No Report Available", "UNAVAILABLE", False, False, "malformed"),
        ("unsupported", {"verdict": "MAYBE", "findings": [{"message": "claim must stay raw"}], "evidence_items": [{"summary": "unsupported claim"}]}, None, "Unsupported Report", "UNSUPPORTED", False, False, "unsupported"),
    ],
)
def test_canonical_and_degraded_report_states(browser, tmp_path, monkeypatch, name, report, report_error, title, label, action_visible, copy_visible, message):
    snapshot = _snapshot(tmp_path, report=report, report_error=report_error)
    with _server(tmp_path, monkeypatch, {"ok": True, "status": "success", "snapshot": snapshot}) as base:
        context, page, errors, _ = _open(browser, base)
        try:
            assert page.locator("#verdict-title").inner_text() == title.upper(), name
            assert page.locator("#fact-verdict").inner_text() == label
            assert message in page.locator("body").inner_text().lower() if message in {"malformed", "unsupported"} else message in page.locator("#explanation").inner_text()
            assert page.locator("#run-review").is_visible() is action_visible
            assert page.locator("#copy-prompt").is_visible() is copy_visible
            if not copy_visible:
                assert page.locator("#copy-prompt").is_disabled()
            assert page.locator("#raw-report").inner_text()
            if name == "unsupported":
                assert "claim must stay raw" not in page.locator("#evidence-list").inner_text()
                assert "unsupported claim" not in page.locator("#evidence-list").inner_text()
            assert errors == []
        finally:
            context.close()


@pytest.mark.parametrize("baseline", ["missing", "stale", "corrupt"])
def test_baseline_degraded_states_are_explicit(browser, tmp_path, monkeypatch, baseline):
    snapshot = _snapshot(tmp_path, report=_report("PASS"), baseline=baseline)
    with _server(tmp_path, monkeypatch, {"ok": True, "status": "success", "snapshot": snapshot}) as base:
        context, page, errors, _ = _open(browser, base)
        try:
            assert f"Baseline state: {baseline}" in page.locator("#command-center-activity").inner_text()
            capability = page.locator("#command-center-capabilities").inner_text()
            assert f"baseline state: {baseline}" in capability
            assert errors == []
        finally:
            context.close()


def test_authenticated_startup_single_snapshot_and_reload(browser, tmp_path, monkeypatch):
    snapshot = _snapshot(tmp_path, report=_report("PASS"))
    with _server(tmp_path, monkeypatch, {"ok": True, "status": "success", "snapshot": snapshot}) as base:
        context, page, errors, requests = _open(browser, base)
        try:
            assert page.url == f"{base}/"
            assert page.title() == "SourcePack Workbench"
            assert page.evaluate("sessionStorage.getItem('sourcepackToken')") == TOKEN
            assert sum(url.endswith("/command-center-aggregate.js") for url in requests) == 1
            assert sum("/api/command-center/v1/snapshot" in url for url in requests) == 1
            assert not any("/api/dashboard/" in url or url.endswith("/api/latest") or url.endswith("/api/status") for url in requests)
            page.reload(wait_until="networkidle")
            assert page.locator("#fact-verdict").inner_text() == "PASS"
            assert "token=" not in page.url
            assert errors == []
        finally:
            context.close()


def test_auth_failures_and_safe_snapshot_failure(browser, tmp_path, monkeypatch):
    failure = {"ok": False, "status": "error", "error": {"code": "command_center_snapshot_failed", "message": '<script id="error-script">window.pwned=true</script>'}}
    with _server(tmp_path, monkeypatch, failure) as base:
        context, page, _, requests = _open(browser, base, token="wrong")
        try:
            assert page.locator("#verdict-title").inner_text() == "WORKBENCH ERROR"
            assert page.locator("#systems-raw").inner_text() == ""
            assert sum("/api/command-center/v1/snapshot" in url for url in requests) == 1
        finally:
            context.close()
        context, page, _, _ = _open(browser, base)
        try:
            assert page.locator("#verdict-title").inner_text() == "WORKBENCH ERROR"
            assert "<script" in page.locator("#explanation").inner_text()
            assert page.locator("#error-script").count() == 0
            assert page.evaluate("window.pwned") is None
            assert page.locator("#verdict-card").get_attribute("role") == "alert"
        finally:
            context.close()


def test_actions_technical_report_navigation_and_untrusted_text(browser, tmp_path, monkeypatch):
    hostile = '<img id="injected-node" src=x onerror="window.pwned=true">'
    snapshot = _snapshot(tmp_path, report=_report("FAIL", prompt=f"Fix safely: {hostile}", hostile=True))
    with _server(tmp_path, monkeypatch, {"ok": True, "status": "success", "snapshot": snapshot}) as base:
        context, page, errors, _ = _open(browser, base)
        try:
            page.locator("#copy-prompt").click()
            assert page.locator("#copy-status").inner_text() == "✓ Copied!"
            assert page.evaluate("navigator.clipboard.readText()") == f"Fix safely: {hostile}"
            assert page.locator("#injected-node").count() == 0
            assert page.evaluate("window.pwned") is None
            toggle = page.locator("#toggle-report")
            toggle.focus(); page.keyboard.press("Enter")
            assert toggle.get_attribute("aria-expanded") == "true"
            assert page.locator("#raw-report").is_visible()
            page.keyboard.press("Enter")
            assert toggle.get_attribute("aria-expanded") == "false"
            page.locator('nav a[href="#policy-studio"]').click()
            assert page.evaluate("location.hash") == "#policy-studio"
            assert errors == []
        finally:
            context.close()


def test_accessibility_semantics_and_keyboard_reachability(browser, tmp_path, monkeypatch):
    snapshot = _snapshot(tmp_path, report=_report("PASS"))
    with _server(tmp_path, monkeypatch, {"ok": True, "status": "success", "snapshot": snapshot}) as base:
        context, page, _, _ = _open(browser, base)
        try:
            audit = page.evaluate("""() => ({
              lang: document.documentElement.lang,
              viewport: !!document.querySelector('meta[name=viewport]'),
              headings: [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].map(h => Number(h.tagName[1])),
              h1: document.querySelectorAll('h1').length,
              duplicateIds: [...document.querySelectorAll('[id]')].map(n=>n.id).filter((id,i,a)=>a.indexOf(id)!==i),
              unnamed: [...document.querySelectorAll('button,a[href]')].filter(n => !(n.getAttribute('aria-label') || n.textContent.trim())).length,
              controls: [...document.querySelectorAll('button:not([hidden]),a[href]')].map(n => ({tab:n.tabIndex, disabled:n.disabled || false})),
              focusOutline: getComputedStyle(document.querySelector('#toggle-report'), ':focus-visible').outlineStyle
            })""")
            assert audit["lang"] == "en" and audit["viewport"] and audit["h1"] == 1
            assert audit["duplicateIds"] == [] and audit["unnamed"] == 0
            assert all(b - a <= 1 for a, b in zip(audit["headings"], audit["headings"][1:]))
            assert all(item["tab"] >= 0 for item in audit["controls"] if not item["disabled"])
            page.locator("#toggle-report").focus()
            assert page.evaluate("getComputedStyle(document.activeElement).outlineStyle") != "none"
            assert page.locator("#explanation").get_attribute("role") == "status"
            assert page.locator("#toggle-report").get_attribute("aria-controls") == "raw-report"
        finally:
            context.close()


@pytest.mark.parametrize("width,height", VIEWPORTS)
def test_responsive_layout_has_no_application_overflow(browser, tmp_path, monkeypatch, width, height):
    snapshot = _snapshot(tmp_path, report=_report("FAIL", prompt="x" * 5000))
    with _server(tmp_path, monkeypatch, {"ok": True, "status": "success", "snapshot": snapshot}) as base:
        context, page, _, _ = _open(browser, base, viewport=(width, height))
        try:
            metrics = page.evaluate("""() => ({
              documentOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
              clipped: [...document.querySelectorAll('main section, main .panel')].filter(n => n.getBoundingClientRect().right > innerWidth + 1).length,
              navVisible: !!document.querySelector('nav')?.getClientRects().length,
              actionVisible: !!document.querySelector('#copy-prompt')?.getClientRects().length,
              promptWrap: getComputedStyle(document.querySelector('#correction-prompt')).whiteSpace,
              rawOverflow: getComputedStyle(document.querySelector('#raw-report')).overflow
            })""")
            assert metrics == {"documentOverflow": 0, "clipped": 0, "navVisible": True, "actionVisible": True, "promptWrap": "pre-wrap", "rawOverflow": "auto"}, (width, height, metrics)
            page.locator("#copy-prompt").scroll_into_view_if_needed()
            assert page.locator("#copy-prompt").is_visible()
            assert page.locator("#explanation").is_visible()
        finally:
            context.close()


def test_real_bounded_review_updates_the_snapshot(browser, tmp_path, monkeypatch):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, stdout=subprocess.PIPE)
    (tmp_path / "README.md").write_text("browser review\n", encoding="utf-8")
    with _server(tmp_path, monkeypatch) as base:
        context, page, errors, requests = _open(browser, base)
        try:
            with page.expect_response(lambda response: response.url.endswith("/api/workbench/v1/review") and response.status == 200):
                page.locator("#run-review").click()
            page.wait_for_function("document.querySelector('#run-review').disabled === false || document.querySelector('#run-review').hidden === true")
            assert (tmp_path / ".sourcepack" / "reports" / "latest.json").is_file()
            review_requests = [url for url in requests if url.endswith("/api/workbench/v1/review")]
            assert len(review_requests) == 1
            assert errors == []
        finally:
            context.close()
