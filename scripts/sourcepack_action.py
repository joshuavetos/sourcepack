#!/usr/bin/env python3
"""Thin GitHub Action wrapper for the existing SourcePack CLI."""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

COMMENT_MARKER = "<!-- sourcepack-action-comment:v1 -->"
MAX_COMMENT_FINDINGS = 20


def _truthy(value: str | bool | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _json_data(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _verdict_from_json(path: Path) -> str | None:
    verdict = _json_data(path).get("verdict")
    return verdict if isinstance(verdict, str) else None


def _traffic_light_from_json(path: Path) -> str | None:
    data = _json_data(path)
    for key in ("traffic_light", "trafficLight", "light"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    verdict = data.get("verdict")
    return verdict if isinstance(verdict, str) else None


def _append_step_summary(path: str | None, markdown: str) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as summary:
        summary.write(markdown)
        if not markdown.endswith("\n"):
            summary.write("\n")


def _artifact_list(report_dir: Path) -> list[str]:
    names = [
        "sourcepack.json",
        "sourcepack.md",
        "sourcepack.sarif.json",
        "sourcepack.stdout.txt",
        "sourcepack.stderr.txt",
        "sourcepack-command.txt",
        "sourcepack-command.json",
        "sourcepack-pr-comment.md",
        "sourcepack-pr-comment.txt",
    ]
    return [name for name in names if (report_dir / name).exists()]


def _list_of_dicts(data: dict[str, object], key: str) -> list[dict[str, Any]]:
    value = data.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(data: dict[str, object], *keys: str) -> list[str]:
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            return [str(item) for item in value]
    return []


def _finding_label(finding: dict[str, Any]) -> str:
    severity = str(finding.get("severity") or "info").upper()
    code = str(finding.get("id") or "unknown")
    path = finding.get("path")
    message = str(finding.get("message") or "")
    line = f"- **{severity} `{code}`**"
    if path:
        line += f" in `{path}`"
    if message:
        line += f": {message}"
    return line


def _render_pr_comment(
    json_report: Path,
    markdown_report: Path,
    command_log: Path,
    sarif_status: str,
    mode: str,
    fail_on_warn: bool,
) -> str:
    data = _json_data(json_report)
    verdict = str(data.get("verdict") or _verdict_from_json(json_report) or "UNKNOWN")
    traffic_light = str(_traffic_light_from_json(json_report) or verdict)

    findings = _list_of_dicts(data, "findings")
    blockers = _list_of_dicts(data, "blockers") or [item for item in findings if item.get("severity") == "error"]
    warnings = _list_of_dicts(data, "warnings") or [item for item in findings if item.get("severity") == "warn"]
    uncertainties = _list_of_dicts(data, "uncertainties")
    checked = _string_list(data, "checked", "checked_categories")
    not_checked = _string_list(data, "not_checked")

    lines = [
        COMMENT_MARKER,
        "## SourcePack result",
        "",
        f"**{traffic_light} / {verdict}**",
        "",
        f"- Mode: `{mode}`",
        f"- WARN fails in selected mode: `{str(fail_on_warn)}`",
        f"- Findings: `{len(findings)}` total, `{len(blockers)}` blocker(s), `{len(warnings)}` warning(s)",
        f"- SARIF passthrough: {sarif_status}",
    ]

    if command_log.exists():
        command = command_log.read_text(encoding="utf-8").strip()
        if command:
            lines.extend(["", "### Command", "", f"```text\n{command}\n```"])

    lines.extend(["", "### Findings", ""])
    if findings:
        for finding in findings[:MAX_COMMENT_FINDINGS]:
            lines.append(_finding_label(finding))
        if len(findings) > MAX_COMMENT_FINDINGS:
            hidden = len(findings) - MAX_COMMENT_FINDINGS
            lines.append(f"- ... {hidden} additional finding(s) omitted from PR comment; see uploaded artifacts.")
    else:
        lines.append("No SourcePack findings were reported.")

    if checked:
        lines.extend(["", "### Evidence checked", ""])
        lines.extend(f"- {item}" for item in checked)

    if not_checked:
        lines.extend(["", "### Not checked", ""])
        lines.extend(f"- {item}" for item in not_checked)

    if uncertainties:
        lines.extend(["", "### Uncertainties", ""])
        for finding in uncertainties[:MAX_COMMENT_FINDINGS]:
            lines.append(_finding_label(finding))

    lines.extend(
        [
            "",
            "SourcePack does not prove code correctness, security, runtime success, semantic validity, external API truth, dependency safety, or user intent.",
        ]
    )
    if markdown_report.exists():
        lines.extend(["", "Full markdown summary is available in the uploaded SourcePack report artifact."])

    return "\n".join(lines).rstrip() + "\n"


def _event_pull_request_number(event_path: str | None) -> int | None:
    if not event_path:
        return None
    try:
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    pull_request = event.get("pull_request")
    if isinstance(pull_request, dict):
        number = pull_request.get("number")
        return number if isinstance(number, int) else None

    number = event.get("number")
    return number if isinstance(number, int) else None


def _github_api_request(
    method: str,
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method=method)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(request, timeout=20) as response:
        response_body = response.read().decode("utf-8")

    if not response_body:
        return None
    return json.loads(response_body)


def _post_or_update_pr_comment(body: str) -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    repository = os.environ.get("GITHUB_REPOSITORY")
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    pr_number = _event_pull_request_number(os.environ.get("GITHUB_EVENT_PATH"))

    if not token:
        return "skipped: missing GITHUB_TOKEN or GH_TOKEN"
    if not repository:
        return "skipped: missing GITHUB_REPOSITORY"
    if pr_number is None:
        return "skipped: no pull_request number in GITHUB_EVENT_PATH"

    comments_url = f"{api_url}/repos/{repository}/issues/{pr_number}/comments"
    comments = _github_api_request("GET", comments_url, token)

    if isinstance(comments, list):
        for comment in comments:
            if not isinstance(comment, dict):
                continue
            existing_body = comment.get("body")
            comment_id = comment.get("id")
            if isinstance(existing_body, str) and COMMENT_MARKER in existing_body and isinstance(comment_id, int):
                _github_api_request(
                    "PATCH",
                    f"{api_url}/repos/{repository}/issues/comments/{comment_id}",
                    token,
                    {"body": body},
                )
                return f"updated: issue comment {comment_id}"

    created = _github_api_request("POST", comments_url, token, {"body": body})
    if isinstance(created, dict) and isinstance(created.get("id"), int):
        return f"created: issue comment {created['id']}"
    return "created: issue comment"


def _maybe_comment_pr(
    enabled: str,
    json_report: Path,
    markdown_report: Path,
    command_log: Path,
    comment_body: Path,
    comment_status: Path,
    sarif_status: str,
    mode: str,
    fail_on_warn: bool,
) -> None:
    if not _truthy(enabled):
        return

    body = _render_pr_comment(
        json_report=json_report,
        markdown_report=markdown_report,
        command_log=command_log,
        sarif_status=sarif_status,
        mode=mode,
        fail_on_warn=fail_on_warn,
    )
    _write(comment_body, body)

    try:
        status = _post_or_update_pr_comment(body)
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        status = f"failed: {exc}"

    _write(comment_status, status + "\n")
    print(f"SourcePack PR comment: {status}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SourcePack for GitHub Actions.")
    parser.add_argument("--mode", choices=["ci", "strict", "local"], default="ci")
    parser.add_argument("--baseline-path", default=".sourcepack/baseline")
    parser.add_argument("--report-dir", default="sourcepack-report")
    parser.add_argument("--json", default="true")
    parser.add_argument("--markdown", default="true")
    parser.add_argument("--sarif", default="true")
    parser.add_argument("--fail-on-warn", default="false")
    parser.add_argument("--comment-pr", default="false")
    parser.add_argument("--repo", default=".")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    baseline = (repo / args.baseline_path).resolve()
    report_dir = (repo / args.report_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    command_log = report_dir / "sourcepack-command.txt"
    command_json = report_dir / "sourcepack-command.json"
    stdout_log = report_dir / "sourcepack.stdout.txt"
    stderr_log = report_dir / "sourcepack.stderr.txt"
    json_report = report_dir / "sourcepack.json"
    markdown_report = report_dir / "sourcepack.md"
    sarif_report = report_dir / "sourcepack.sarif.json"
    comment_body = report_dir / "sourcepack-pr-comment.md"
    comment_status = report_dir / "sourcepack-pr-comment.txt"

    if not baseline.exists():
        message = (
            "SourcePack failed closed because trusted baseline state is missing.\n"
            f"Missing baseline path: {args.baseline_path}\n"
            "CI will not create or update trusted baseline state.\n"
            "Create or refresh the baseline locally or in a separate trusted maintainer-controlled setup workflow.\n"
            "This is a trust-boundary behavior, not a package crash.\n"
        )
        _write(command_log, "baseline preflight\n")
        _write(command_json, json.dumps({"command": ["baseline preflight"]}, indent=2) + "\n")
        _write(stdout_log, "")
        _write(stderr_log, message)
        _write(
            markdown_report,
            "# SourcePack Action summary\n\n"
            "- Verdict: FAIL\n"
            "- Traffic light: RED LIGHT\n"
            f"- Mode: {args.mode}\n"
            f"- WARN fails in selected mode: {args.mode in {'ci', 'strict'} or _truthy(args.fail_on_warn)}\n"
            f"- Report directory: {report_dir}\n"
            "- Artifacts: sourcepack.md, sourcepack.stderr.txt, sourcepack.stdout.txt, sourcepack-command.txt, sourcepack-command.json\n"
            "- Missing baseline: SourcePack failed closed because trusted baseline state is missing. "
            "CI will not create or update trusted baseline state. Create or refresh the baseline locally "
            "or in a separate trusted maintainer-controlled setup workflow. This is a trust-boundary behavior, not a package crash.\n",
        )
        _append_step_summary(os.environ.get("GITHUB_STEP_SUMMARY"), markdown_report.read_text(encoding="utf-8"))
        print(message, file=sys.stderr, end="")
        print(f"SourcePack report directory: {report_dir}")
        return 2

    sourcepack_executable = shutil.which("sourcepack")
    if not sourcepack_executable:
        message = "SourcePack executable not found on PATH.\n"
        _write(command_log, "sourcepack lookup failed\n")
        _write(command_json, json.dumps({"command": ["sourcepack lookup failed"]}, indent=2) + "\n")
        _write(stdout_log, "")
        _write(stderr_log, message)
        print(message, file=sys.stderr, end="")
        print(f"SourcePack report directory: {report_dir}")
        return 127

    command = [sourcepack_executable, "diff", str(repo)]
    if _truthy(args.json) or args.mode == "ci":
        command.append("--json")
    if args.mode == "ci":
        command.append("--ci")
    elif args.mode == "strict" or _truthy(args.fail_on_warn):
        command.append("--strict")

    _write(command_log, shlex.join(command) + "\n")
    _write(command_json, json.dumps({"command": command}, indent=2) + "\n")

    result = _run(command, repo)

    _write(stdout_log, result.stdout)
    _write(stderr_log, result.stderr)

    if _truthy(args.json):
        _write(json_report, result.stdout)

    latest_json = repo / ".sourcepack" / "reports" / "latest.json"
    if latest_json.exists():
        shutil.copyfile(latest_json, json_report)

    latest_sarif = repo / ".sourcepack" / "reports" / "latest.sarif.json"
    sarif_status = "disabled"
    if _truthy(args.sarif):
        if latest_sarif.exists():
            shutil.copyfile(latest_sarif, sarif_report)
            sarif_status = f"copied to {sarif_report}"
        else:
            sarif_status = "enabled, but no SourcePack SARIF report was present; continuing without SARIF artifact"

    if _truthy(args.markdown):
        verdict = _verdict_from_json(json_report) or "UNKNOWN"
        traffic_light = _traffic_light_from_json(json_report) or verdict
        artifacts = _artifact_list(report_dir)
        if "sourcepack.md" not in artifacts:
            artifacts.insert(1 if "sourcepack.json" in artifacts else 0, "sourcepack.md")
        _write(
            markdown_report,
            "# SourcePack Action summary\n\n"
            f"- Verdict: {verdict}\n"
            f"- Traffic light: {traffic_light}\n"
            f"- Mode: {args.mode}\n"
            f"- WARN fails in selected mode: {args.mode in {'ci', 'strict'} or _truthy(args.fail_on_warn)}\n"
            f"- Report directory: {report_dir}\n"
            f"- Artifacts: {', '.join(artifacts) if artifacts else 'none'}\n"
            f"- SARIF passthrough: {sarif_status}\n"
            f"- Command artifact: {command_log} contains the exact command arguments used.\n\n"
            "## Command\n\n"
            f"```text\n{shlex.join(command)}\n```\n\n"
            "## Output\n\n"
            f"```text\n{result.stdout}\n```\n",
        )

    _maybe_comment_pr(
        enabled=args.comment_pr,
        json_report=json_report,
        markdown_report=markdown_report,
        command_log=command_log,
        comment_body=comment_body,
        comment_status=comment_status,
        sarif_status=sarif_status,
        mode=args.mode,
        fail_on_warn=args.mode in {"ci", "strict"} or _truthy(args.fail_on_warn),
    )

    print(f"SourcePack report directory: {report_dir}")
    print(f"SourcePack artifacts: {', '.join(_artifact_list(report_dir))}")
    print(f"SourcePack SARIF passthrough: {sarif_status}")

    if markdown_report.exists():
        _append_step_summary(os.environ.get("GITHUB_STEP_SUMMARY"), markdown_report.read_text(encoding="utf-8"))

    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
