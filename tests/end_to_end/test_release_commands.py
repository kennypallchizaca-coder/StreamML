from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def test_demo_and_verifier_complete() -> None:
    demo = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "demo_models.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "STREAMML DEMO COMPLETED" in demo.stdout
    verifier = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_release.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "STREAMML RELEASE VERIFIED" in verifier.stdout
