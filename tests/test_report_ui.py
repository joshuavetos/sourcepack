import json, subprocess, sys
from sourcepack.reports.html import render_report_html
from sourcepack.reports.json import traffic_report, write_user_report


def test_html_generated_for_verdicts_and_fields(tmp_path):
    for verdict in ["PASS", "WARN", "FAIL"]:
        html = render_report_html(traffic_report(verdict, findings=[{"id":"no_diff","severity":"info","category":"diff","message":"ok", "path":"README.md"}], checked_categories=["baseline"]))
        assert verdict in html and "Evidence found" in html and "Baseline and prompt trust" in html and "Execution evidence" in html


def test_report_path_and_json_clean(tmp_path):
    write_user_report(tmp_path, traffic_report("PASS"), "x")
    cp = subprocess.run([sys.executable,"-m","sourcepack.cli","report","path",str(tmp_path)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert cp.returncode == 0 and cp.stdout.strip().endswith("latest.html")
    json.dumps(traffic_report("PASS"))
