"""Cross-platform single-instance guard for the local OBS connector."""

from __future__ import annotations

import os
from pathlib import Path


class ConnectorAlreadyRunning(RuntimeError):
    """Raised when another local StreamML connector owns the OBS lock."""


class ConnectorInstanceLock:
    def __init__(self) -> None:
        root = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "StreamML"
        self.path = root / "connector.lock"
        self._handle = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        try:
            handle.seek(0)
            if not handle.read(1):
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise ConnectorAlreadyRunning("Otro conector StreamML ya controla este OBS.") from exc
        self._handle = handle

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            self._handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None

    def __enter__(self) -> "ConnectorInstanceLock":
        self.acquire()
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.release()
