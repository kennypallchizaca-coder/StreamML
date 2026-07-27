from types import SimpleNamespace

from apps.connector.streamml_connector.api_client import ConnectorRuntimeSettings
from apps.connector.streamml_connector.config import ConnectorConfig
from apps.connector.streamml_connector.main import _apply_runtime_settings, _stored_credentials_or_current
from apps.connector.streamml_connector.obs_client import ObsClient, ReadOnlyObsClient
from apps.connector.streamml_connector.secrets import ConnectorCredentials
from src.streamml.security.crypto import sign_scoped_token


class FakeObs:
    def __init__(self):
        self.calls = []
        self.output_active = True

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
            output_active=self.output_active,
            output_reconnecting=False,
            output_skipped_frames=2,
            output_total_frames=100,
            output_congestion=0.0,
            output_bytes=2_000_000,
        )

    def get_scene_list(self):
        self.calls.append("GetSceneList")
        return SimpleNamespace(scenes=[{"sceneName": "StreamML Live"}, {"sceneName": "StreamML Backup"}])

    def get_scene_item_list(self, scene_name):
        self.calls.append(("GetSceneItemList", scene_name))
        return SimpleNamespace(
            scene_items=[
                {
                    "sourceName": "VDO",
                    "inputKind": "browser_source",
                }
            ]
        )

    def get_input_settings(self, name):
        self.calls.append(("GetInputSettings", name))
        return SimpleNamespace(input_settings={"url": "https://vdo.ninja/?view=direct"})

    def set_input_settings(self, name, settings, overlay):
        self.calls.append(("SetInputSettings", name, settings, overlay))

    def get_stream_service_settings(self):
        self.calls.append("GetStreamServiceSettings")
        return SimpleNamespace(stream_service_settings={})

    def set_stream_service_settings(self, service_type, settings):
        self.calls.append(("SetStreamServiceSettings", service_type, settings))

    def stop_stream(self):
        self.calls.append("StopStream")
        self.output_active = False

    def start_stream(self):
        self.calls.append("StartStream")
        self.output_active = True

    def disconnect(self):
        self.calls.append("disconnect")

    def set_profile_parameter(self, category, name, value):
        self.calls.append(("SetProfileParameter", category, name, value))

    def set_current_program_scene(self, name):
        self.calls.append(("SetCurrentProgramScene", name))


def test_connector_uses_a_new_pairing_without_a_process_restart():
    current = ConnectorCredentials(access_token="current-token", connector_id="old", session_id="old-session")
    updated = ConnectorCredentials(access_token="new-token", connector_id="new", session_id="new-session")

    class Store:
        def __init__(self, value):
            self.value = value

        def load(self):
            return self.value

    assert _stored_credentials_or_current(Store(updated), current) == updated
    assert _stored_credentials_or_current(Store(None), current) == current


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
        output_active=True,
        output_reconnecting=False,
        output_skipped_frames=2,
        output_total_frames=200,
        output_congestion=0.0,
        output_bytes=3_000_000,
    )
    second = client.collect()
    assert fake.calls[:2] == ["GetStats", "GetStreamStatus"]
    assert first.output_bitrate_kbps is None
    assert second.output_bitrate_kbps == 4000.0
    assert second.latency_ms is None
    assert second.packet_loss_percent is None
    assert ObsClient.ALLOWED_REQUESTS == {
        "GetStats",
        "GetStreamStatus",
        "GetSceneList",
        "GetSceneItemList",
        "GetInputSettings",
        "SetInputSettings",
        "SetProfileParameter",
        "GetStreamServiceSettings",
        "SetStreamServiceSettings",
        "StopStream",
        "StartStream",
        "SetCurrentProgramScene",
    }
    assert client.validate_scenes() == []


def test_obs_adapter_replaces_the_only_live_browser_source_with_the_secure_bridge():
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
    client = ObsClient(config, client_factory=lambda **_kwargs: fake)
    client.connect("not-logged")
    bridge = "http://127.0.0.1:5173/vdo-bridge/session-id?token=scoped"

    assert client.ensure_vdo_bridge(bridge) == "VDO"
    assert ("SetInputSettings", "VDO", {"url": bridge}, True) in fake.calls


def test_obs_adapter_applies_only_validated_profile_and_scene_commands():
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
    client = ObsClient(config, client_factory=lambda **_kwargs: fake)
    client.connect("not-logged")
    client.apply_command(
        {
            "command_type": "set_profile",
            "payload": {
                "profile": "low",
                "spec": {
                    "width": 854,
                    "height": 480,
                    "fps": 24,
                    "video_bitrate_kbps": 1000,
                    "audio_bitrate_kbps": 96,
                },
            },
        }
    )
    client.apply_command({"command_type": "activate_backup", "payload": {}})
    client.apply_command({"command_type": "restore_live", "payload": {}})
    assert client.ensure_rtmp_service("rtmp://127.0.0.1:1935", "stream-a?token=test") is True
    assert client.ensure_rtmp_service("rtmp://127.0.0.1:1935", "stream-a?token=test") is False
    assert sum(call[0] == "SetProfileParameter" for call in fake.calls if isinstance(call, tuple)) == 5
    assert ("SetCurrentProgramScene", "StreamML Backup") in fake.calls
    assert ("SetCurrentProgramScene", "StreamML Live") in fake.calls
    assert ("SetStreamServiceSettings", "rtmp_custom", {"server": "rtmp://127.0.0.1:1935", "key": "stream-a?token=test"}) in fake.calls
    assert "StopStream" in fake.calls
    assert "StartStream" in fake.calls
    stop_index = fake.calls.index("StopStream")
    set_index = fake.calls.index(
        ("SetStreamServiceSettings", "rtmp_custom", {"server": "rtmp://127.0.0.1:1935", "key": "stream-a?token=test"})
    )
    start_index = fake.calls.index("StartStream")
    assert stop_index < set_index < start_index


def test_runtime_settings_wait_for_an_authenticated_obs_connection():
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
    settings = ConnectorRuntimeSettings(
        live_scene="StreamML Live",
        backup_scene="StreamML Backup",
        network_probe_interval_seconds=10,
        network_probe_bytes=1024,
        rtmp_server="rtmp://127.0.0.1:1935",
        rtmp_stream_key="stream-a?token=test",
    )
    client = ObsClient(config, client_factory=lambda **_kwargs: fake)

    _apply_runtime_settings(client, settings)
    assert fake.calls == []

    client.connect("not-logged")
    _apply_runtime_settings(client, settings)
    assert ("SetStreamServiceSettings", "rtmp_custom", {"server": "rtmp://127.0.0.1:1935", "key": "stream-a?token=test"}) in fake.calls


def test_rtmp_service_does_not_restart_for_obs_trailing_slash_normalization():
    fake = FakeObs()
    fake.get_stream_service_settings = lambda: SimpleNamespace(
        stream_service_settings={
            "server": "rtmp://127.0.0.1:1935/",
            "key": "stream-a?token=test",
        }
    )
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
    client = ObsClient(config, client_factory=lambda **_kwargs: fake)
    client.connect("not-logged")

    assert client.ensure_rtmp_service("rtmp://127.0.0.1:1935", "stream-a?token=test") is False
    assert "StopStream" not in fake.calls
    assert "StartStream" not in fake.calls


def test_rtmp_service_keeps_a_fresh_publish_token_for_the_same_stream():
    fake = FakeObs()
    current_token = sign_scoped_token({"stream_id": "stream-a", "scope": "publish"}, "test-secret", ttl_seconds=600)
    replacement_token = sign_scoped_token({"stream_id": "stream-a", "scope": "publish"}, "test-secret", ttl_seconds=900)
    fake.get_stream_service_settings = lambda: SimpleNamespace(
        stream_service_settings={
            "server": "rtmp://127.0.0.1:1935/",
            "key": f"stream-a?token={current_token}",
        }
    )
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
    client = ObsClient(config, client_factory=lambda **_kwargs: fake)
    client.connect("not-logged")

    assert client.ensure_rtmp_service("rtmp://127.0.0.1:1935", f"stream-a?token={replacement_token}") is False
    assert "StopStream" not in fake.calls
    assert "StartStream" not in fake.calls
