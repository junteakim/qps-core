import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_public_release.py"
SPEC = importlib.util.spec_from_file_location("verify_public_release", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_release_gate_rejects_environment_files(tmp_path) -> None:
    secret = tmp_path / ".env.local"
    secret.write_text("TOKEN=synthetic\n", encoding="utf-8")

    issues = MODULE.verify_files(tmp_path, [secret])

    assert any("forbidden environment file" in issue for issue in issues)


def test_archive_mode_rejects_generated_directories(tmp_path) -> None:
    generated = tmp_path / "demo-output"
    generated.mkdir()
    (generated / "artifact.txt").write_text("synthetic", encoding="utf-8")

    _, issues, _ = MODULE.select_release_files(tmp_path, archive=True)

    assert any("generated directory in archive payload" in issue for issue in issues)
