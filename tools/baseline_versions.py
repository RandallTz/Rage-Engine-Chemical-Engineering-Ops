"""Print the F0 reproducible-baseline version list (multiphysics-roadmap.md, F0).

Run from the repository root: python tools/baseline_versions.py
Reads only; prints the source commit, interpreter and package versions and the
published protocol version constants of the Python services.
"""
import importlib.metadata as md
import platform
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ["numpy", "scipy", "thermo", "chemicals", "fluids", "pint", "pydantic",
            "fastapi", "uvicorn", "httpx", "matplotlib", "plotly", "openpyxl", "python-ternary"]
CONSTANTS = ["core/catalogo.py", "core/modelo/lector.py", "core/resultados/formato.py",
             "backend/motor_diagramas.py", "backend/motor_ensamblaje.py", "backend/motor_ensamblaje_v2.py",
             "backend/motor_termodinamica.py", "backend/multicomponent_diagrams.py"]


def run(*cmd):
    try:
        return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


dirty = run("git", "status", "--porcelain")
print(f"commit {run('git', 'rev-parse', 'HEAD')} ({len(dirty.splitlines())} uncommitted entries)")
print(f"python {platform.python_version()}; node {run('node', '--version')}")
for name in PACKAGES:
    try:
        print(f"{name} {md.version(name)}")
    except md.PackageNotFoundError:
        print(f"{name} not installed")
for rel in CONSTANTS:
    text = (ROOT / rel).read_text(encoding="utf-8")
    for match in re.finditer(r"^(VERSION|REVISION) *= *(\d+)", text, re.M):
        print(f"{rel} {match.group(1)} = {match.group(2)}")
