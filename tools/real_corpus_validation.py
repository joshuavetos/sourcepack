#!/usr/bin/env python3
"""Optional SourcePack real-corpus validation harness.

This harness intentionally does not hard-code the prior external Colab corpus,
because this repository does not contain the exact 10 public repo URLs and
scenario fixtures used there. Provide repos with --repo URL or a JSON list via
--repo-list. The script clones or reuses repositories, rebuilds SourcePack
baselines with the current checkout, runs README_EDIT, NEW_FILE, and IMPORT_FAIL,
and exits nonzero if calibrated expectations fail.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCENARIOS = ("README_EDIT", "NEW_FILE", "IMPORT_FAIL")


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def sourcepack_cmd() -> list[str]:
    return [sys.executable, "-m", "sourcepack.cli"]


def repo_name(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")


def load_repos(args: argparse.Namespace) -> list[str]:
    repos = list(args.repo or [])
    if args.repo_list:
        data = json.loads(Path(args.repo_list).read_text(encoding="utf-8"))
        if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
            raise SystemExit("--repo-list must contain a JSON list of repo URLs")
        repos.extend(data)
    return repos


def ensure_repo(url: str, root: Path) -> Path:
    target = root / repo_name(url)
    if target.exists():
        cp = run(["git", "fetch", "--all", "--prune"], target)
        if cp.returncode != 0:
            raise RuntimeError(cp.stderr.strip() or cp.stdout.strip())
    else:
        cp = run(["git", "clone", url, str(target)])
        if cp.returncode != 0:
            raise RuntimeError(cp.stderr.strip() or cp.stdout.strip())
    return target


def deep_clean(repo: Path) -> None:
    for cmd in (["git", "reset", "--hard"], ["git", "clean", "-ffdx"]):
        cp = run(cmd, repo)
        if cp.returncode != 0:
            raise RuntimeError(cp.stderr.strip() or cp.stdout.strip())


def choose_import(repo: Path) -> str:
    if (repo / "package.json").exists():
        return 'import definitely_missing_sourcepack_pkg from "definitely-missing-sourcepack-pkg";\n'
    return "import definitely_missing_sourcepack_pkg\n"


def apply_scenario(repo: Path, scenario: str) -> None:
    if scenario == "README_EDIT":
        readme = next((p for p in [repo / "README.md", repo / "readme.md"] if p.exists()), repo / "README.md")
        readme.write_text((readme.read_text(encoding="utf-8", errors="ignore") if readme.exists() else "") + "\nSourcePack validation edit.\n", encoding="utf-8")
    elif scenario == "NEW_FILE":
        (repo / "sourcepack_validation_new_file.txt").write_text("SourcePack validation new file.\n", encoding="utf-8")
    elif scenario == "IMPORT_FAIL":
        target = repo / ("sourcepack_validation_import.js" if (repo / "package.json").exists() else "sourcepack_validation_import.py")
        target.write_text(choose_import(repo), encoding="utf-8")
    else:
        raise ValueError(scenario)


def reason_codes(report: dict) -> set[str]:
    codes = {str(f.get("id")) for f in report.get("findings", []) if isinstance(f, dict) and f.get("id")}
    codes.update(str(f.get("id")) for f in report.get("uncertainties", []) if isinstance(f, dict) and f.get("id"))
    return codes


def accepted(scenario: str, report: dict) -> bool:
    verdict = report.get("verdict")
    codes = reason_codes(report)
    if scenario == "README_EDIT":
        return verdict == "PASS" or (verdict == "WARN" and "unsupported_ecosystem" in codes)
    if scenario == "NEW_FILE":
        return verdict == "WARN"
    if scenario == "IMPORT_FAIL":
        return verdict == "FAIL"
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Run optional calibrated SourcePack real-corpus validation against caller-provided public repos.")
    parser.add_argument("--repo", action="append", help="public git repo URL; repeat up to the desired corpus size")
    parser.add_argument("--repo-list", help="JSON file containing a list of public git repo URLs")
    parser.add_argument("--workdir", help="reuse this working directory instead of a temporary directory")
    args = parser.parse_args()
    repos = load_repos(args)
    if not repos:
        print("No corpus configured. Provide --repo URL or --repo-list JSON. The exact prior 10-repo Colab corpus is not stored in this repo.", file=sys.stderr)
        return 2
    work = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="sourcepack_real_corpus_"))
    work.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    ok = True
    for url in repos:
        repo = ensure_repo(url, work)
        for scenario in SCENARIOS:
            deep_clean(repo)
            base = run(sourcepack_cmd() + ["baseline", str(repo), "--refresh", "--quiet"], repo)
            if base.returncode != 0:
                rows.append({"repo": url, "scenario": scenario, "ok": False, "stderr": base.stderr.strip()})
                ok = False
                continue
            apply_scenario(repo, scenario)
            cp = run(sourcepack_cmd() + ["diff", str(repo), "--json"], repo)
            try:
                report = json.loads(cp.stdout)
            except json.JSONDecodeError:
                report = {"verdict": "ERROR", "stdout": cp.stdout, "stderr": cp.stderr}
            row = {"repo": url, "scenario": scenario, "verdict": report.get("verdict"), "reason_codes": sorted(reason_codes(report)), "report_path": report.get("report_path"), "ok": accepted(scenario, report)}
            rows.append(row)
            ok = ok and row["ok"]
    print(json.dumps(rows, indent=2))
    if not args.workdir:
        shutil.rmtree(work, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
