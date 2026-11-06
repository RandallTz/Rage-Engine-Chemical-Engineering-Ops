"""Generate fresh app-flow publications for the live Results verifiers.

Requires an isolated backend at NEXT_PUBLIC_API_URL, as does the app verifier.
"""
import subprocess
from pathlib import Path


def test_generate_app_results():
    root = Path(__file__).resolve().parents[1]
    subprocess.run(
        ['node', str(root / 'frontend/verificar_demo02_app_flow.mjs'), '--results-only'],
        cwd=root,
        check=True,
    )
