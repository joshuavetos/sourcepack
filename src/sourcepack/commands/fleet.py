from __future__ import annotations

import json

from sourcepack.fleet import render_human_summary, summarize_reports


def register(subparsers) -> None:
    fleet_cmd = subparsers.add_parser(
        "fleet",
        help="summarize SourcePack reports across repos or report archives",
    )
    fleet_subs = fleet_cmd.add_subparsers(dest="fleet_command")
    fleet_summarize = fleet_subs.add_parser(
        "summarize",
        help="summarize a directory or file of SourcePack JSON reports",
    )
    fleet_summarize.add_argument("path")
    fleet_summarize.add_argument("--json", action="store_true")


def cli_fleet(args) -> int:
    if args.fleet_command == "summarize":
        summary = summarize_reports(args.path)
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(render_human_summary(summary), end="")
        return 0
    return 1
