from sourcepack import workbench


def test_workbench_surfaces_copyable_remediation_without_html_injection():
    ui = (workbench.STATIC_ROOT / "index.html").read_text(encoding="utf-8")

    assert "Agent correction instruction" in ui
    assert "Copy correction prompt" in ui
    assert "data.report?.remediation?.agent_prompt" in ui
    assert "navigator.clipboard.writeText" in ui
    assert "innerHTML" not in ui
    assert "textContent" in ui
