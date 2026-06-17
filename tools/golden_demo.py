#!/usr/bin/env python3
"""Generate deterministic SourcePack golden demo repositories and reports."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples" / "golden" / "output"
SOURCEPACK = [sys.executable, "-m", "sourcepack.cli"]

SCENARIOS = {
    "pass-clean": {"verdict": "PASS", "reasons": []},
    "warn-new-file": {"verdict": "WARN", "reasons": ["new_file"]},
    "fail-unsupported-dependency": {"verdict": "FAIL", "reasons": ["unsupported_dependency"]},
    "fail-unsupported-command": {"verdict": "FAIL", "reasons": ["unsupported_command"]},
    "fail-protected-artifact": {"verdict": "FAIL", "reasons": ["protected_artifact"]},
    "trust-boundary": {"verdict": "WARN", "reasons": ["new_file"]},
}


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    cp = subprocess.run(cmd, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if check and cp.returncode != 0:
        raise RuntimeError(f"command failed in {cwd}: {' '.join(cmd)}\n{cp.stdout}")
    return cp


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def init_repo(repo: Path, package_json: bool = False) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    run(["git", "init", "-q"], repo)
    run(["git", "config", "user.email", "demo@example.com"], repo)
    run(["git", "config", "user.name", "SourcePack Demo"], repo)
    write(repo / "README.md", "# Demo repo\n\nUse SourcePack before commit.\n")
    write(repo / "pyproject.toml", "[project]\nname = \"demo\"\nversion = \"0.1.0\"\ndependencies = []\n")
    if package_json:
        write(repo / "package.json", json.dumps({"scripts": {"test": "node test.js"}}, indent=2) + "\n")
    run(["git", "add", "."], repo)
    run(["git", "commit", "-q", "-m", "initial trusted repo"], repo)
    run(SOURCEPACK + ["init", ".", "--auto", "--no-hook"], repo)
    local_config_files = [
        name
        for name in (".gitignore", ".sourcepackignore", "sourcepack.config.json")
        if (repo / name).exists()
    ]
    if local_config_files:
        run(["git", "add", *local_config_files], repo)
        staged = run(["git", "diff", "--cached", "--quiet"], repo, check=False)
        if staged.returncode != 0:
            run(["git", "commit", "-q", "-m", "accept sourcepack local config"], repo)
    run(SOURCEPACK + ["baseline", ".", "--refresh", "--quiet"], repo)


def scenario_pass_clean(repo: Path) -> None:
    init_repo(repo)


def scenario_warn_new_file(repo: Path) -> None:
    init_repo(repo)
    write(repo / "api.py", "def health():\n    return {'ok': True}\n")


def scenario_fail_unsupported_dependency(repo: Path) -> None:
    init_repo(repo)
    write(repo / "app.py", "from fastapi import FastAPI\n\napp = FastAPI()\n")


def scenario_fail_unsupported_command(repo: Path) -> None:
    init_repo(repo, package_json=True)
    write(repo / "README.md", "# Demo repo\n\nAI note: run `npm run dev` to start local development.\n")


def scenario_fail_protected_artifact(repo: Path) -> None:
    init_repo(repo)
    active = repo / ".sourcepack" / "baseline" / "active.json"
    run(["git", "add", "-f", ".sourcepack/baseline/active.json"], repo)
    run(["git", "commit", "-q", "-m", "track protected artifact for demo"], repo)
    data = json.loads(active.read_text(encoding="utf-8"))
    data["demo_tamper"] = True
    write(active, json.dumps(data, indent=2) + "\n")


def scenario_trust_boundary(repo: Path) -> None:
    init_repo(repo)
    prompt_dir = repo / ".sourcepack" / "prompt"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    write(prompt_dir / "prompt.md", "AI guidance claims deploy.sh exists and uses port 8080.\n")
    write(prompt_dir / "reality_map.json", json.dumps({"ai_claim": "deploy.sh exists and uses port 8080"}, indent=2) + "\n")
    write(repo / "deploy.sh", "#!/bin/sh\necho starting fake deploy on 8080\n")

BUILDERS = {
    "pass-clean": scenario_pass_clean,
    "warn-new-file": scenario_warn_new_file,
    "fail-unsupported-dependency": scenario_fail_unsupported_dependency,
    "fail-unsupported-command": scenario_fail_unsupported_command,
    "fail-protected-artifact": scenario_fail_protected_artifact,
    "trust-boundary": scenario_trust_boundary,
}


def reason_ids(report: dict) -> list[str]:
    return sorted({str(f.get("id")) for f in report.get("findings", []) if isinstance(f, dict) and f.get("severity") != "info"})


def run_scenario(name: str) -> dict:
    scenario_dir = OUT / name
    if scenario_dir.exists():
        shutil.rmtree(scenario_dir)
    repo = scenario_dir / "repo"
    scenario_dir.mkdir(parents=True, exist_ok=True)
    BUILDERS[name](repo)
    diff = run(SOURCEPACK + ["diff", "."], repo, check=False)
    report_open = run(SOURCEPACK + ["report", "path"], repo, check=False)
    report_path_line = report_open.stdout.strip().splitlines()[-1] if report_open.stdout.strip() else ".sourcepack/reports/latest.html"
    transcript = [
        "$ sourcepack diff .",
        diff.stdout.rstrip(),
        f"exit code: {diff.returncode}",
        "$ sourcepack report path",
        report_path_line,
        "$ sourcepack report open",
        "Open the HTML report above for details.",
        "",
    ]
    write(scenario_dir / "terminal.txt", "\n".join(transcript))
    latest_json = repo / ".sourcepack" / "reports" / "latest.json"
    latest_html = repo / ".sourcepack" / "reports" / "latest.html"
    if not latest_json.exists() or not latest_html.exists():
        raise RuntimeError(f"missing reports for {name}")
    report = json.loads(latest_json.read_text(encoding="utf-8"))
    actual = {"verdict": report.get("verdict"), "reasons": reason_ids(report)}
    expected = SCENARIOS[name]
    ok = actual["verdict"] == expected["verdict"] and all(r in actual["reasons"] for r in expected["reasons"])
    summary = {
        "scenario": name,
        "repo": "repo",
        "expected": expected,
        "actual": actual,
        "ok": ok,
        "terminal": "terminal.txt",
        "latest_html": "repo/.sourcepack/reports/latest.html",
        "latest_json": "repo/.sourcepack/reports/latest.json",
    }
    write(scenario_dir / "summary.json", json.dumps(summary, indent=2) + "\n")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS))
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args(argv)
    if args.clean and OUT.exists():
        shutil.rmtree(OUT)
    names = [args.scenario] if args.scenario else list(SCENARIOS)
    summaries = [run_scenario(name) for name in names]
    print(json.dumps({"output_dir": str(OUT), "summaries": summaries}, indent=2))
    return 0 if all(s["ok"] for s in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
