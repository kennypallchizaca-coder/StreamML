from io import BytesIO

import pytest

from apps.media.restream_worker import (
    RestreamSupervisor,
    RestreamTarget,
    fallback_command,
    ffmpeg_command,
    load_targets,
    source_url,
)


PATH = "stream-0123456789abcdef0123456789abcdef"


def test_restream_config_and_ffmpeg_command() -> None:
    targets = load_targets('{"' + PATH + '":{"youtube":"rtmps://example.test/live/secret-key"}}')
    assert targets == [RestreamTarget(PATH, "youtube", "rtmps://example.test/live/secret-key")]
    command = ffmpeg_command(targets[0], rtmp_base="rtmp://mediamtx:1935", media_secret="x" * 32)
    assert command[0] == "ffmpeg"
    assert "-c" in command and "copy" in command
    assert command[-1] == "rtmps://example.test/live/secret-key"
    source = source_url(PATH, rtmp_base="rtmp://mediamtx:1935", media_secret="x" * 32)
    assert source == f"rtmp://mediamtx:1935/{PATH}?user=media-worker&pass={'x' * 32}"
    assert "@mediamtx" not in source
    fallback = fallback_command(targets[0], "/fallback/fallback.mp4")
    assert "-stream_loop" in fallback
    assert fallback[-1] == targets[0].url


def test_restream_rejects_non_rtmp_or_non_streamml_paths() -> None:
    with pytest.raises(ValueError):
        load_targets('{"camera":{"bad":"https://example.test"}}')


def test_supervisor_uses_fallback_then_restores_after_stable_probes(monkeypatch) -> None:
    commands: list[list[str]] = []

    class FakeProcess:
        def __init__(self, command):
            commands.append(command)
            self.running = True

        def poll(self):
            return None if self.running else 0

        def terminate(self):
            self.running = False

        def wait(self, timeout=None):
            return 0

        def kill(self):
            self.running = False

    target = RestreamTarget(PATH, "youtube", "rtmps://example.test/live/key")
    supervisor = RestreamSupervisor([target], "rtmp://mediamtx:1935", "x" * 32)
    live = False
    monkeypatch.setattr("apps.media.restream_worker.subprocess.Popen", FakeProcess)
    monkeypatch.setattr(supervisor, "_live_available", lambda _path: live)

    supervisor._reconcile()
    assert supervisor.modes[(PATH, "youtube")] == "fallback"
    assert "-stream_loop" in commands[-1]

    live = True
    supervisor._reconcile()
    supervisor._reconcile()
    assert supervisor.modes[(PATH, "youtube")] == "fallback"
    supervisor._reconcile()
    assert supervisor.modes[(PATH, "youtube")] == "live"
    assert "-rw_timeout" in commands[-1]


def test_live_probe_uses_mediamtx_control_api(monkeypatch) -> None:
    requested: list[tuple[str, int]] = []

    class FakeResponse(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    def fake_urlopen(url: str, timeout: int):
        requested.append((url, timeout))
        return FakeResponse(b'{"ready":true,"available":true,"online":true}')

    monkeypatch.setattr("apps.media.restream_worker.urlopen", fake_urlopen)
    supervisor = RestreamSupervisor([], "rtmp://mediamtx:1935", "x" * 32)

    assert supervisor._live_available(PATH) is True
    assert requested == [(f"http://mediamtx:9997/v3/paths/get/{PATH}", 2)]


def test_live_probe_rejects_incomplete_path_state(monkeypatch) -> None:
    monkeypatch.setattr(
        "apps.media.restream_worker.urlopen",
        lambda *_args, **_kwargs: BytesIO(b'{"ready":true,"available":true,"online":false}'),
    )
    supervisor = RestreamSupervisor([], "rtmp://mediamtx:1935", "x" * 32)

    assert supervisor._live_available(PATH) is False
