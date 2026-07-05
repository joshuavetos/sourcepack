import json
from pathlib import Path

from sourcepack.judgment import PacketWriter, SourceScanner, dependency_inventory, load_manifest


def _packet(tmp_path: Path, files: dict[str, str]) -> Path:
    src = tmp_path / "src"
    out = tmp_path / "packet"
    for rel, content in files.items():
        path = src / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    scanner = SourceScanner(src, redact=False).scan()
    return PacketWriter(out, scanner).write_all()


def test_dependency_inventory_reads_python_requirements_and_pyproject(tmp_path):
    packet = _packet(
        tmp_path,
        {
            "requirements.txt": "requests>=2\nunknown-package==1\n",
            "pyproject.toml": "[project]\ndependencies = ['fastapi>=0.1', 'Pillow']\n",
        },
    )

    deps = dependency_inventory(load_manifest(packet), packet)

    assert {"requests", "fastapi", "pillow"} <= deps
    assert "unknown-package" not in deps


def test_dependency_inventory_reads_package_json_and_js_import_roots(tmp_path):
    package_json = json.dumps({"dependencies": {"react": "latest"}, "devDependencies": {"@types/node": "latest"}})
    packet = _packet(
        tmp_path,
        {
            "package.json": package_json,
            "app.js": "import React from 'react/jsx-runtime';\nconst local = require('./local');\nimport('@types/node/fs');\n",
            "README.md": "This README mentions flask and django in prose.\n",
        },
    )

    deps = dependency_inventory(load_manifest(packet), packet)

    assert "react" in deps
    assert "@types/node" not in deps
    assert "./local" not in deps
    assert "flask" not in deps
    assert "django" not in deps
