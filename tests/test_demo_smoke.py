import json
from pathlib import Path

from sourcepack.reports.json import normalized_finding, traffic_report, write_user_report


def test_stranger_demo_smoke_catches_unsupported_repo_fact(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("print('tiny')\n", encoding="utf-8")
    report = traffic_report("FAIL", findings=[normalized_finding("unsupported_dependency", "error", "dependency", "dependency not declared", evidence="requests")])
    write_user_report(repo, report, stem="demo_smoke")
    latest = json.loads((repo / ".sourcepack" / "reports" / "latest.json").read_text(encoding="utf-8"))
    assert latest["schema_version"] == "traffic_report.v1"
    assert latest["verdict"] == "FAIL"
    assert latest["light"] == "RED LIGHT"
    findings = latest["findings"]
    assert len(findings) == 1
    assert findings[0]["id"] == "unsupported_dependency"
    assert findings[0]["evidence"] == "requests"
    assert findings[0]["finding_id"].startswith("spkf_")
    rerun = traffic_report("FAIL", findings=[normalized_finding("unsupported_dependency", "error", "dependency", "dependency not declared", evidence="requests")])
    assert findings[0]["finding_id"] == rerun["findings"][0]["finding_id"]
