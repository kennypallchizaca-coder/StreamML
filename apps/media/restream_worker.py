"""Supervise live and fallback FFmpeg outputs for RTMP targets."""

from __future__ import annotations

import json
import logging
import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlparse


LOGGER = logging.getLogger("streamml_media")
PATH_PATTERN = re.compile(r"^stream-[0-9a-f]{32}$")


@dataclass(frozen=True, slots=True)
class RestreamTarget:
    path: str
    name: str
    url: str


def load_targets(raw: str) -> list[RestreamTarget]:
    """Parse path -> named RTMP URL mappings without ever logging URLs."""

    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("STREAMML_RESTREAM_CONFIG_JSON must be valid JSON.") from exc
    if not isinstance(value, dict):
        raise ValueError("Restream configuration must be an object.")
    targets: list[RestreamTarget] = []
    for path, destinations in value.items():
        if not isinstance(path, str) or not PATH_PATTERN.fullmatch(path):
            raise ValueError("Restream path must be an opaque StreamML stream id.")
        if not isinstance(destinations, dict) or not destinations:
            raise ValueError("Each restream path must contain named destinations.")
        for name, url in destinations.items():
            if not isinstance(name, str) or not 1 <= len(name) <= 64:
                raise ValueError("Destination names must contain 1 to 64 characters.")
            if not isinstance(url, str):
                raise ValueError("Destination URL must be a string.")
            parsed = urlparse(url)
            if parsed.scheme not in {"rtmp", "rtmps"} or not parsed.hostname:
                raise ValueError("Destinations must be absolute RTMP(S) URLs.")
            targets.append(RestreamTarget(path, name, url))
    return targets


def ffmpeg_command(
    target: RestreamTarget, *, rtmp_base: str, media_secret: str
) -> list[str]:
    if len(media_secret) < 32:
        raise ValueError("STREAMML_MEDIA_AUTH_SECRET must contain at least 32 characters.")
    base = rtmp_base.rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme != "rtmp" or not parsed.hostname:
        raise ValueError("STREAMML_INTERNAL_RTMP_BASE must be an absolute RTMP URL.")
    host = parsed.hostname
    port = f":{parsed.port}" if parsed.port else ""
    credentials = f"media-worker:{quote(media_secret, safe='')}@"
    source = f"rtmp://{credentials}{host}{port}/{target.path}"
    return [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "warning",
        "-rw_timeout", "15000000", "-i", source,
        "-map", "0:v:0", "-map", "0:a:0?", "-c", "copy",
        "-f", "flv", "-flvflags", "no_duration_filesize", target.url,
    ]


def fallback_command(target: RestreamTarget, fallback_file: str) -> list[str]:
    if not fallback_file.startswith("/"):
        raise ValueError("STREAMML_FALLBACK_FILE must be an absolute container path.")
    return [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "warning",
        "-re", "-stream_loop", "-1", "-i", fallback_file,
        "-map", "0:v:0", "-map", "0:a:0?", "-c", "copy",
        "-f", "flv", "-flvflags", "no_duration_filesize", target.url,
    ]


def source_url(path: str, *, rtmp_base: str, media_secret: str) -> str:
    if len(media_secret) < 32:
        raise ValueError("STREAMML_MEDIA_AUTH_SECRET must contain at least 32 characters.")
    base = rtmp_base.rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme != "rtmp" or not parsed.hostname:
        raise ValueError("STREAMML_INTERNAL_RTMP_BASE must be an absolute RTMP URL.")
    port = f":{parsed.port}" if parsed.port else ""
    credentials = f"media-worker:{quote(media_secret, safe='')}@"
    return f"rtmp://{credentials}{parsed.hostname}{port}/{path}"


class RestreamSupervisor:
    def __init__(
        self, targets: list[RestreamTarget], rtmp_base: str, media_secret: str,
        fallback_file: str = "/fallback/fallback.mp4",
    ) -> None:
        self.targets = targets
        self.rtmp_base = rtmp_base
        self.media_secret = media_secret
        self.fallback_file = fallback_file
        self.processes: dict[tuple[str, str], subprocess.Popen[bytes]] = {}
        self.modes: dict[tuple[str, str], str] = {}
        self.recovery_streaks: dict[tuple[str, str], int] = {}
        self.running = True

    def stop(self, *_args: Any) -> None:
        self.running = False

    def run(self) -> None:
        while self.running:
            self._reconcile()
            time.sleep(2)
        for process in self.processes.values():
            process.terminate()
        for process in self.processes.values():
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()

    def _reconcile(self) -> None:
        for target in self.targets:
            key = (target.path, target.name)
            process = self.processes.get(key)
            available = self._live_available(target.path)
            if available:
                self.recovery_streaks[key] = self.recovery_streaks.get(key, 0) + 1
            else:
                self.recovery_streaks[key] = 0
            desired_mode = "live" if self.recovery_streaks[key] >= 3 else "fallback"
            if process is not None and process.poll() is None and self.modes.get(key) == desired_mode:
                continue
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                LOGGER.warning("Restream %s/%s changing mode.", target.path, target.name)
            command = (
                ffmpeg_command(target, rtmp_base=self.rtmp_base, media_secret=self.media_secret)
                if desired_mode == "live"
                else fallback_command(target, self.fallback_file)
            )
            self.processes[key] = subprocess.Popen(command)
            self.modes[key] = desired_mode
            LOGGER.info("Restream %s/%s started in %s mode.", target.path, target.name, desired_mode)

    def _live_available(self, path: str) -> bool:
        source = source_url(path, rtmp_base=self.rtmp_base, media_secret=self.media_secret)
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error", "-rw_timeout", "2000000",
                    "-show_entries", "stream=codec_type", "-of", "csv=p=0", source,
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=4,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return False
        return result.returncode == 0


def main() -> int:
    logging.basicConfig(level=os.getenv("STREAMML_LOG_LEVEL", "INFO"))
    targets = load_targets(os.getenv("STREAMML_RESTREAM_CONFIG_JSON", "{}"))
    supervisor = RestreamSupervisor(
        targets,
        os.getenv("STREAMML_INTERNAL_RTMP_BASE", "rtmp://mediamtx:1935"),
        os.getenv("STREAMML_MEDIA_AUTH_SECRET", ""),
        os.getenv("STREAMML_FALLBACK_FILE", "/fallback/fallback.mp4"),
    )
    signal.signal(signal.SIGTERM, supervisor.stop)
    signal.signal(signal.SIGINT, supervisor.stop)
    if not targets:
        LOGGER.info("No external RTMP destinations are configured; worker is idle.")
    supervisor.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
