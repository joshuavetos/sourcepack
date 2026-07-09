from __future__ import annotations

import contextlib
import io
import json

from sourcepack.cli import run_cli
from sourcepack.commands import fleet as fleet_command


def test_fleet_registered_through_top_level_cli(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_cli_fleet(args) -> int:
        seen["command"] = args.command
        seen["fleet_command"] = args.fleet_command
        seen["path"] = args.path
        seen["json"] = args.json
        return 0

    monkeypatch.setattr(fleet_command, "cli_fleet", fake_cli_fleet)

    code = run_cli(["fleet", "summarize", "reports-dir", "--json"])

    assert code == 0
    assert seen == {
        "command": "fleet",
        "fleet_command": "summarize",
        "path": "reports-dir",
        "json": True,
    }


def test_fleet_summarize_still_works_through_top_level_cli(monkeypatch) -> None:
    def fake_summarize_reports(path: str) -> dict[str, object]:
        assert path == "reports-dir"
        return {"schema_version": "sourcepack.fleet.summary.v1", "ok": True}

    monkeypatch.setattr(fleet_command, "summarize_reports", fake_summarize_reports)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = run_cli(["fleet", "summarize", "reports-dir", "--json"])

    assert code == 0
    assert json.loads(buf.getvalue()) == {
        "schema_version": "sourcepack.fleet.summary.v1",
        "ok": True,
    }


def test_report_path_registered_through_top_level_cli(tmp_path) -> None:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = run_cli(["report", "path", str(tmp_path)])

    assert code == 0
    assert buf.getvalue() == f"{tmp_path / '.sourcepack' / 'reports' / 'latest.html'}\n"


def test_report_open_registered_through_top_level_cli(tmp_path, monkeypatch) -> None:
    from sourcepack.commands import report as report_command
    from sourcepack.reports.json import traffic_report, write_user_report

    opened: list[str] = []
    write_user_report(tmp_path, traffic_report("PASS"), "x")
    monkeypatch.setattr(report_command.webbrowser, "open", lambda uri: opened.append(uri) or True)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = run_cli(["report", "open", str(tmp_path)])

    expected_html = tmp_path / ".sourcepack" / "reports" / "latest.html"
    assert code == 0
    assert opened == [expected_html.resolve().as_uri()]
    assert buf.getvalue() == f"Report HTML: {expected_html}\n"
