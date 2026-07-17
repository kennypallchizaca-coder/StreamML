"""Seekable HTTP range reader for extracting selected files from large ZIPs."""

from __future__ import annotations

import io
import urllib.request


class HTTPRangeReader(io.RawIOBase):
    """Expose a remote immutable object as a seekable binary stream.

    Every read is bounded by an HTTP Range request.  A server that ignores the
    range is rejected before its multi-gigabyte response can be consumed.
    """

    def __init__(self, url: str, size: int, *, timeout_seconds: float = 60) -> None:
        if not url.startswith("https://") or size <= 0:
            raise ValueError("A positive-size HTTPS object is required.")
        self.url = url
        self.size = int(size)
        self.timeout_seconds = timeout_seconds
        self.position = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            target = offset
        elif whence == io.SEEK_CUR:
            target = self.position + offset
        elif whence == io.SEEK_END:
            target = self.size + offset
        else:
            raise ValueError("Invalid seek mode.")
        if target < 0:
            raise ValueError("Cannot seek before start of remote object.")
        self.position = min(target, self.size)
        return self.position

    def read(self, size: int = -1) -> bytes:
        if self.position >= self.size:
            return b""
        end = self.size - 1 if size is None or size < 0 else min(
            self.size - 1, self.position + size - 1
        )
        request = urllib.request.Request(
            self.url,
            headers={
                "Range": f"bytes={self.position}-{end}",
                "User-Agent": "StreamML-source-fetcher/1.0",
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            if response.status != 206:
                raise OSError("Remote source did not honor the required byte range.")
            data = response.read(end - self.position + 1)
        expected = end - self.position + 1
        if len(data) != expected:
            raise OSError("Remote ZIP range was truncated.")
        self.position += len(data)
        return data
