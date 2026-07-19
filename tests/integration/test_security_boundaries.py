from pathlib import Path

from src.streamml.security.crypto import redact_mapping


ROOT = Path(__file__).resolve().parents[2]


def test_secret_fields_are_redacted():
    value = redact_mapping({"password": "secret", "nested": {"access_token": "token", "safe": 1}})
    assert value == {"password": "[REDACTED]", "nested": {"access_token": "[REDACTED]", "safe": 1}}


def test_connector_control_surface_contains_no_stream_start_stop_or_toggle():
    source = (ROOT / "apps" / "connector" / "streamml_connector" / "obs_client.py").read_text(encoding="utf-8")
    forbidden = (".start_", ".stop_", ".toggle_", "start_stream", "stop_stream")
    assert all(token not in source.lower() for token in forbidden)
    assert "ALLOWED_REQUESTS" in source
    assert "SetProfileParameter" in source
    assert "SetCurrentProgramScene" in source


def test_models_and_training_artifacts_are_not_connector_dependencies():
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "apps" / "connector" / "streamml_connector").glob("*.py")
    )
    assert "models/registry" not in source
    assert "train_models" not in source
