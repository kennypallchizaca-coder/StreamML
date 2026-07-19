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
    assert source_url(PATH, rtmp_base="rtmp://mediamtx:1935", media_secret="x" * 32).endswith(PATH)
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
