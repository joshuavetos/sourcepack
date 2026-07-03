import pytest
from sourcepack.judgment import render_ai_instructions

def test_render_ai_instructions_empty():
    result = render_ai_instructions({})

    assert "# AI Instructions for This SourcePack Packet" in result
    assert "## Supported Commands\n\n- None detected\n" in result
    assert "## Supported Capabilities\n\n- None detected\n" in result
    assert "## Confirmed Files\n\n\n## Required Answer Contract" in result
    assert result.endswith("## Claim Boundaries\n\n")

def test_render_ai_instructions_with_data():
    reality_map = {
        "supported_commands": ["npm test", "pytest"],
        "supported_capabilities": ["react", "web server"],
        "confirmed_files": ["src/main.py", "package.json"],
        "claim_boundaries": [
            "SourcePack did not execute the application.",
            "Absence of evidence means unknown, not impossible."
        ]
    }

    result = render_ai_instructions(reality_map)

    assert "## Supported Commands\n\n- `npm test`\n- `pytest`\n" in result
    assert "## Supported Capabilities\n\n- react\n- web server\n" in result
    assert "## Confirmed Files\n\n- `src/main.py`\n- `package.json`\n" in result
    assert "## Claim Boundaries\n\n- SourcePack did not execute the application.\n- Absence of evidence means unknown, not impossible.\n" in result

def test_render_ai_instructions_truncates_files():
    files = [f"file_{i}.py" for i in range(250)]
    reality_map = {
        "confirmed_files": files
    }

    result = render_ai_instructions(reality_map)

    # Check that first 200 are included
    for i in range(200):
        assert f"- `file_{i}.py`" in result

    # Check that 201+ are NOT included
    for i in range(200, 250):
        assert f"- `file_{i}.py`" not in result
