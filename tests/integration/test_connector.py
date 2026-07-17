from types import SimpleNamespace

from apps.connector.streamml_connector.config import ConnectorConfig
from apps.connector.streamml_connector.obs_client import ObsClient, ReadOnlyObsClient


class FakeObs:
    def __init__(self):
        self.calls = []

    def get_stats(self):
        self.calls.append("GetStats")
        return SimpleNamespace(
            active_fps=60.0,
            render_skipped_frames=1,
            render_total_frames=100,
        )

    def get_stream_status(self):
        self.calls.append("GetStreamStatus")
        return SimpleNamespace(
            output_active=True,
            output_reconnecting=False,
            output_skipped_frames=2,
            output_total_frames=100,
            output_congestion=0.0,
            output_bytes=2_000_000,
        )

    def disconnect(self):
        self.calls.append("disconnect")

    def set_profile_parameter(self, category, name, value):
        self.calls.append(("SetProfileParameter", category, name, value))

    def set_current_program_scene(self, name):
        self.calls.append(("SetCurrentProgramScene", name))


def test_obs_adapter_collects_telemetry_without_inventing_network_metrics():
    assert ReadOnlyObsClient is ObsClient
    fake = FakeObs()
    config = ConnectorConfig(
        api_base_url="https://streamml.test",
        obs_host="127.0.0.1",
        obs_port=4455,
        connector_name="test",
        session_id=None,
        poll_interval_seconds=1,
        request_timeout_seconds=5,
        reconnect_initial_seconds=1,
        reconnect_max_seconds=10,
        keyring_service="test",
        log_level="INFO",
    )
    times = iter((1.0, 3.0))
    client = ObsClient(config, client_factory=lambda **_kwargs: fake, monotonic=lambda: next(times))
    client.connect("not-logged")
    first = client.collect()
    fake.get_stream_status = lambda: SimpleNamespace(
        output_active=True, output_reconnecting=False, output_skipped_frames=2,
        output_total_frames=200, output_congestion=0.0, output_bytes=3_000_000,
    )
    second = client.collect()
    assert fake.calls[:2] == ["GetStats", "GetStreamStatus"]
    assert first.output_bitrate_kbps is None
    assert second.output_bitrate_kbps == 4000.0
    assert second.latency_ms is None
    assert second.packet_loss_percent is None
    assert ObsClient.ALLOWED_REQUESTS == {
        "GetStats", "GetStreamStatus", "SetProfileParameter", "SetCurrentProgramScene"
    }


def test_obs_adapter_applies_only_validated_profile_and_scene_commands():
    fake = FakeObs()
    config = ConnectorConfig(
        api_base_url="https://streamml.test", obs_host="127.0.0.1", obs_port=4455,
        connector_name="test", session_id=None, poll_interval_seconds=1,
        request_timeout_seconds=5, reconnect_initial_seconds=1, reconnect_max_seconds=10,
        keyring_service="test", log_level="INFO",
    )
    client = ObsClient(config, client_factory=lambda **_kwargs: fake)
    client.connect("not-logged")
    client.apply_command({
        "command_type": "set_profile",
        "payload": {
            "profile": "low",
            "spec": {
                "width": 854, "height": 480, "fps": 24,
                "video_bitrate_kbps": 1000, "audio_bitrate_kbps": 96,
            },
        },
    })
    client.apply_command({"command_type": "activate_backup", "payload": {}})
    client.apply_command({"command_type": "restore_live", "payload": {}})
    assert sum(call[0] == "SetProfileParameter" for call in fake.calls if isinstance(call, tuple)) == 5
    assert ("SetCurrentProgramScene", "StreamML Backup") in fake.calls
    assert ("SetCurrentProgramScene", "StreamML Live") in fake.calls
