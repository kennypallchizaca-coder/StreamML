from pathlib import Path

from src.streamml.security.crypto import redact_mapping


ROOT = Path(__file__).resolve().parents[2]


def test_secret_fields_are_redacted():
    value = redact_mapping({"password": "secret", "nested": {"access_token": "token", "safe": 1}})
    assert value == {"password": "[REDACTED]", "nested": {"access_token": "[REDACTED]", "safe": 1}}


def test_agent_control_surface_cannot_start_stop_or_toggle_a_stream():
    source = (ROOT / "apps" / "connector" / "streamml_connector" / "obs_client.py").read_text(encoding="utf-8")
    agent_surface = source.split("    def apply_command", 1)[1].split("    def _apply_profile", 1)[0].lower()
    forbidden = (".start_", ".stop_", ".toggle_", "start_stream", "stop_stream")
    assert all(token not in agent_surface for token in forbidden)
    assert "ALLOWED_REQUESTS" in source
    assert "SetProfileParameter" in source
    assert "SetCurrentProgramScene" in source
    # OBS rejects a stream-service update while active. The connector may
    # briefly cycle output only inside the session-scoped RTMP synchronizer;
    # this is not exposed as a model or API control command.
    assert "def ensure_rtmp_service" in source


def test_models_and_training_artifacts_are_not_connector_dependencies():
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "apps" / "connector" / "streamml_connector").glob("*.py")
    )
    assert "models/registry" not in source
    assert "train_models" not in source
