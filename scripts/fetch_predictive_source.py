"""Fetch only long, selected sessions from the official 3.4 GB Figshare ZIP."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import random
import shutil
import sys
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.streamml.data.remote_zip import HTTPRangeReader


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _article(api_url: str, archive_name: str) -> dict:
    request = urllib.request.Request(api_url, headers={"User-Agent": "StreamML-source-fetcher/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        article = json.load(response)
    try:
        return next(item for item in article["files"] if item["name"] == archive_name)
    except (KeyError, StopIteration) as exc:
        raise RuntimeError(f"Official archive {archive_name!r} was not found.") from exc


def _select_sessions(overview: bytes, config: dict) -> tuple[list[str], dict[str, int]]:
    rows = list(csv.DictReader(io.StringIO(overview.decode("utf-8-sig"))))
    minimum = float(config["selection"]["minimum_total_playtime_seconds"])
    groups: dict[str, list[str]] = {
        "constant_bandwidth": [], "one_to_ten_changes": [], "more_than_ten_changes": []
    }
    for row in rows:
        if float(row["total_playtime"]) < minimum:
            continue
        changes = int(float(row["bw_changes"]))
        group = (
            "constant_bandwidth" if changes == 0
            else "one_to_ten_changes" if changes <= 10
            else "more_than_ten_changes"
        )
        groups[group].append(row["path:"])
    rng = random.Random(int(config["random_state"]))
    selected: list[str] = []
    counts: dict[str, int] = {}
    for group, required in config["selection"]["strata"].items():
        candidates = sorted(groups[group])
        if len(candidates) < int(required):
            raise RuntimeError(
                f"Only {len(candidates)} long sessions are available for {group}; {required} required. "
                f"Available counts: { {name: len(items) for name, items in groups.items()} }"
            )
        chosen = sorted(rng.sample(candidates, int(required)))
        selected.extend(chosen)
        counts[group] = len(chosen)
    return sorted(selected), counts


def main() -> None:
    config_path = ROOT / "src" / "streamml" / "config" / "dataset_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    source = config["source"]
    remote = _article(source["api_url"], source["archive_name"])
    reader = HTTPRangeReader(remote["download_url"], int(remote["size"]))
    raw_root = ROOT / config["paths"]["raw_root"]
    raw_root.mkdir(parents=True, exist_ok=True)

    files_downloaded: list[dict] = []
    with zipfile.ZipFile(reader) as archive:
        prefix = "mobile_yt_dataset/"
        overview_member = prefix + "material/data_overview.csv"
        overview = archive.read(overview_member)
        selected, counts = _select_sessions(overview, config)
        members = [
            overview_member,
            prefix + "material/video_catalog.csv",
            prefix + "material/readme.txt",
        ]
        for session in selected:
            for filename in config["selection"]["files_per_session"]:
                members.append(prefix + f"dataset/{session}/{filename}")

        for index, member in enumerate(members, start=1):
            if member.startswith(prefix + "dataset/"):
                _, _, session, filename = member.split("/", 3)
                destination = raw_root / "sessions" / session / filename
            else:
                destination = raw_root / "material" / Path(member).name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source_file, destination.open("wb") as target:
                shutil.copyfileobj(source_file, target)
            info = archive.getinfo(member)
            files_downloaded.append({
                "path": destination.relative_to(ROOT).as_posix(),
                "size_bytes": destination.stat().st_size,
                "sha256": _sha256(destination),
                "archive_member": member,
                "compressed_size_bytes": info.compress_size,
            })
            if index % 25 == 0 or index == len(members):
                print(f"Extracted {index}/{len(members)} selected files", flush=True)

    manifest_path = ROOT / config["paths"]["source_manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["downloaded_at_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["archive"].update({
        "name": remote["name"], "size_bytes": int(remote["size"]),
        "official_md5": remote.get("supplied_md5"), "full_archive_downloaded": False,
        "pcap_downloaded": False,
    })
    manifest["selection"] = {
        "random_state": int(config["random_state"]),
        "criterion": (
            f"total_playtime >= {config['selection']['minimum_total_playtime_seconds']} s; "
            "stratified deterministic sample; no outcome variables used"
        ),
        "selected_sessions": selected,
        "stratum_counts": counts,
    }
    manifest["files_downloaded"] = files_downloaded
    manifest["local_extracted_size_bytes"] = sum(item["size_bytes"] for item in files_downloaded)
    manifest["transformation_applied"] = (
        "Bandwidth settings are forward-applied and converted from kbit/s to Mbps. "
        "Historical 600 s windows and strictly subsequent 600 s horizons are generated."
    )
    temporary = manifest_path.with_suffix(".json.tmp")
    temporary.write_bytes((json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    temporary.replace(manifest_path)
    print(json.dumps({"selected_sessions": len(selected), "strata": counts}, indent=2))


if __name__ == "__main__":
    main()
