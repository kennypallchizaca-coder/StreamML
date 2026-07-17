from __future__ import annotations

from src.streamml.services.release import write_json, write_text_lf


def test_release_writers_use_utf8_lf_bytes_on_every_platform(tmp_path):
    text_path = tmp_path / "release.txt"
    json_path = tmp_path / "metadata.json"

    write_text_lf(text_path, "first\r\nsecond\rthird\n")
    write_json(json_path, {"status": "verified"})

    assert text_path.read_bytes() == b"first\nsecond\nthird\n"
    assert b"\r\n" not in json_path.read_bytes()
