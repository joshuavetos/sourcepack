from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("$", " ".join(cmd), flush=True)
    cp = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(cp.stdout, end="")
    if check and cp.returncode != 0:
        raise SystemExit(cp.returncode)
    return cp


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="sourcepack_release_smoke_") as td:
        work = Path(td)
        dist = work / "dist"
        dist.mkdir()
        run([sys.executable, "-m", "build", "--outdir", str(dist), str(ROOT)], ROOT)
        wheels = sorted(dist.glob("sourcepack-*.whl"))
        sdists = sorted(dist.glob("sourcepack-*.tar.gz"))
        if not wheels:
            raise SystemExit("no SourcePack wheel was built")
        if not sdists:
            raise SystemExit("no SourcePack sdist was built")

        def smoke_artifact(artifact: Path, name: str) -> None:
            env = work / f"venv_{name}"
            venv.EnvBuilder(with_pip=True).create(env)
            exe = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            sourcepack = env / ("Scripts/sourcepack.exe" if os.name == "nt" else "bin/sourcepack")
            run([str(exe), "-m", "pip", "install", str(artifact)], work)
            run([str(exe), "-c", "import sourcepack; print(sourcepack.__version__)"], work)
            run([str(sourcepack), "--version"], work)
            run([str(sourcepack), "doctor"], work)
            run([str(sourcepack), "demo"], ROOT)

        smoke_artifact(wheels[-1], "wheel")
        smoke_artifact(sdists[-1], "sdist")

        sourcepack = work / "venv_wheel" / ("Scripts/sourcepack.exe" if os.name == "nt" else "bin/sourcepack")
        repo = work / "repo"
        repo.mkdir()
        run(["git", "init"], repo)
        run(["git", "config", "user.email", "smoke@example.invalid"], repo)
        run(["git", "config", "user.name", "SourcePack Smoke"], repo)
        (repo / "pyproject.toml").write_text('[project]\nname="smoke"\nversion="0"\ndependencies=[]\n', encoding="utf-8")
        (repo / "app.py").write_text("print('ok')\n", encoding="utf-8")
        run(["git", "add", "."], repo)
        run(["git", "commit", "-m", "initial"], repo)
        run([str(sourcepack), "init", ".", "--auto", "--no-hook"], repo)
        (repo / "app.py").write_text("import fastapi\nprint('ok')\n", encoding="utf-8")
        cp = run([str(sourcepack), "diff", "."], repo, check=False)
        if cp.returncode == 0:
            raise SystemExit("sourcepack diff unexpectedly passed unsupported dependency")
        if not (repo / ".sourcepack" / "reports" / "latest.json").exists():
            raise SystemExit("latest report was not written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
