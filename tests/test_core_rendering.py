from sourcepack.judgment import render_ai_instructions, render_prompt


def test_render_ai_instructions_includes_trust_boundaries_and_contract():
    reality = {
        "supported_commands": ["pytest"],
        "supported_capabilities": ["web server"],
        "confirmed_files": ["src/app.py"],
        "claim_boundaries": ["Absence of evidence means unknown, not impossible."],
    }

    rendered = render_ai_instructions(reality)

    assert "Do not invent files, commands, dependencies, frameworks, services, or capabilities." in rendered
    assert "- `pytest`" in rendered
    assert "- web server" in rendered
    assert "- `src/app.py`" in rendered
    assert "- Absence of evidence means unknown, not impossible." in rendered
    for section in ("Files to modify", "New files", "Dependency changes", "Commands to run", "Assumptions/unknowns", "Patch or code"):
        assert f"- {section}" in rendered


def test_render_ai_instructions_empty_fallbacks_are_explicit():
    rendered = render_ai_instructions({})

    assert "## Supported Commands\n\n- None detected" in rendered
    assert "## Supported Capabilities\n\n- None detected" in rendered


def test_render_prompt_includes_reality_summary_and_grounding_rules():
    prompt = render_prompt(
        "Add tests only.",
        "Use only verified evidence.",
        {
            "project_types": ["python"],
            "included_file_count": 3,
            "supported_commands": ["pytest"],
            "detected_dependencies": ["pytest"],
            "supported_capabilities": ["web server"],
            "claim_boundaries": ["SourcePack did not execute the application."],
        },
    )

    assert "Add tests only." in prompt
    assert "Use only verified evidence." in prompt
    assert "## Compact Reality Map Summary" in prompt
    assert "Project types: python" in prompt
    assert "Included files: 3" in prompt
    assert "- pytest" in prompt
    assert "- web server" in prompt
    assert "- SourcePack did not execute the application." in prompt
    assert "Do not invent files, dependencies, commands, services, or capabilities." in prompt
    assert "Absence of evidence means unknown, not impossible." in prompt
