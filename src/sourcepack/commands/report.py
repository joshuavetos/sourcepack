from __future__ import annotations

import json
import sys
import webbrowser
from pathlib import Path

from ..paths import ensure_sourcepack_dirs
from ..reports.html import render_report_html


def register(subparsers) -> None:
    report_cmd = subparsers.add_parser("report", help="work with local SourcePack reports")
    report_subs = report_cmd.add_subparsers(dest="report_command")
    report_open = report_subs.add_parser("open", help="open .sourcepack/reports/latest.html")
    report_open.add_argument("repo", nargs="?", default=".")
    report_path = report_subs.add_parser("path", help="print .sourcepack/reports/latest.html")
    report_path.add_argument("repo", nargs="?", default=".")


def _latest_report_html_path(repo: str | Path) -> Path:
    return ensure_sourcepack_dirs(repo)["latest_html"]


def cli_report_path(args) -> int:
    print(_latest_report_html_path(Path(args.repo).resolve()))
    return 0


def cli_report_open(args) -> int:
    repo = Path(args.repo).resolve()
    paths = ensure_sourcepack_dirs(repo)
    if not paths["latest_json"].exists():
        print(f"ERROR: no SourcePack report found at {paths['latest_json']}", file=sys.stderr)
        return 1
    try:
        report = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
        paths["latest_html"].write_text(render_report_html(report), encoding="utf-8")
    except Exception as exc:
        print(f"ERROR: could not prepare SourcePack HTML report at {paths['latest_html']}: {exc}", file=sys.stderr)
        return 1
    uri = paths["latest_html"].resolve().as_uri()
    opened = webbrowser.open(uri)
    print(f"Report HTML: {paths['latest_html']}")
    if not opened:
        print("Browser open was not confirmed; open the path above manually.")
    return 0


def cli_report(args) -> int:
    if args.report_command == "open":
        return cli_report_open(args)
    if args.report_command == "path":
        return cli_report_path(args)
    return 1
