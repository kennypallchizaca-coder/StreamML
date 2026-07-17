# StreamML online deployment

This repository contains a production-capable single-node implementation. A
specific public installation is accepted only after its real OBS, phone,
network, MediaMTX, WebRTC, platform credentials and trusted TLS certificate pass
the go-live gate below.

## Prerequisites

- Docker Engine with Compose
- a public DNS name and trusted TLS certificate for online use
- UDP 8189 reachable by WebRTC clients, or a configured TURN service
- OBS WebSocket 5.x enabled only on localhost with authentication
- official StreamML release artifacts already present under `models/registry/`

## Production go-live gate

Do not use `deployment/.env.example` as a running configuration. Before a
public deployment, all of the following must be true:

- The target commit has a successful CI run and `python scripts/verify_release.py`
  reports `STREAMML RELEASE VERIFIED`.
- `python scripts/check_no_secrets.py --history` passes before the first push.
- `deployment/.env` is an untracked file with unique, random values for both
  `STREAMML_*_SECRET` values and the bootstrap password. Store its values in a
  secret manager or password manager, not in a chat, shell profile or commit.
- The TLS certificate covers the configured DNS name; ports TCP 80/443 and UDP
  8189 are reachable as required. Do not publish OBS port 4455, MediaMTX API,
  HLS or WHEP ports directly.
- The OBS computer has the `StreamML Live` and `StreamML Backup` scenes (or the
  configured equivalents), authenticated loopback-only OBS WebSocket, and a
  tested H.264/AAC output mode.
- The RTMP(S) destinations, if any, have been tested with non-production keys
  before their real keys are placed in the ignored deployment environment file.

On a Linux server, create the deployment file with restrictive permissions
before editing it:

```sh
install -m 600 /dev/null deployment/.env
```

Generate secrets with an approved secret manager. If one is not available,
Python can generate a URL-safe value locally; copy it directly into the
protected environment file and do not keep it in shell history.

The Compose deployment mounts `models/registry/` read-only. Versioned data and
feature contracts live under `src/streamml/config/` and are copied with the API
source. The deployment does not train, overwrite or regenerate model artifacts.

## Server deployment

1. Copy `deployment/.env.example` to `deployment/.env` outside version control.
2. Replace every `CHANGE_ME` and both TLS paths.
   `STREAMML_MEDIA_AUTH_SECRET` must be at least 32 URL-safe random characters;
   MediaMTX uses it as Basic authentication on the isolated callback URL.
3. Validate configuration without starting services:

   ```powershell
   docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml config
   ```

4. Build and start:

   ```powershell
   docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml up -d --build
   ```

5. Inspect health without printing environment values:

   ```powershell
   docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml ps
   ```

6. Confirm the API from inside the private Docker network:

   ```powershell
   docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml exec api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3).read().decode())"
   ```

The public entry point is nginx on HTTPS/WSS. The API database uses a persistent
Docker volume, while the MediaMTX control API and metrics listeners have no host
port. RTMP is bound to host loopback by default. The API returns a shared
`https://<host>/media/` base: WHEP/WHIP resources route to WebRTC and playlists
or segments route to HLS.

Media paths are opaque identifiers returned by the authenticated session API:

```text
stream-<32 lowercase hexadecimal characters>
```

MediaMTX delegates every publish/read decision to the API over an isolated
Docker network. The callback is not routed by nginx and every public media
request still needs a short-lived, session-scoped token; a path alone is never
authorization.

## Operations, backup and updates

Containers use restart policies, read-only filesystems where possible, bounded
temporary filesystems, `no-new-privileges` and the Docker `local` log driver
with 10 MiB × 5 rotation per service. Monitor `docker compose ps` and the
container health status; preserve logs outside Docker if retention longer than
that bound is required.

The API SQLite database is a single-node deployment store. Back it up before
an update and test restoration on a non-production host. The script uses the
SQLite Online Backup API, so the result includes committed WAL data consistently:

```powershell
./scripts/Backup-StreamML.ps1
```

Store the resulting file encrypted and outside the server. To verify a restore,
copy it to a non-production installation, start the API and require
`/health/ready` to report the expected schema version and a healthy database.
Do not overwrite a running production database.

For an update: back up the database, review image and dependency changes, run
the release and secret guards, then use `up -d --build`. Never run `down
--volumes` in production unless the database deletion is intentional and a
verified backup exists. Pinning `MEDIAMTX_IMAGE` to `1.19.2` is deliberate;
upgrade it only after replaying the media smoke tests below.

## Local StreamML Connector

The connector runs on the same computer as OBS; do not put it in Compose and do
not open OBS port 4455 on a router or public firewall.

```powershell
py -3.11 -m venv .venv-connector
.venv-connector\Scripts\python -m pip install -e apps/connector
$env:STREAMML_API_URL = "https://streamml.example.com"
$env:OBS_WEBSOCKET_HOST = "127.0.0.1"
$env:OBS_WEBSOCKET_PORT = "4455"
.venv-connector\Scripts\streamml-connector --pair
```

`--pair` reads the temporary code without terminal echo. The OBS password is
read from `OBS_WEBSOCKET_PASSWORD` when explicitly configured, otherwise through
a non-echoing prompt. The API token is stored only in the operating-system
keyring; there is no plaintext fallback.

After the first successful link, run without `--pair`:

```powershell
.venv-connector\Scripts\streamml-connector
```

The connector invokes OBS `GetStats` and `GetStreamStatus` for telemetry. It also
accepts only three authenticated control operations: update the StreamML profile,
select `StreamML Backup`, and restore `StreamML Live`. It never exposes a generic
OBS RPC endpoint and never starts or stops a stream. Create both scenes before
starting the connector, or override `STREAMML_LIVE_SCENE` and
`STREAMML_BACKUP_SCENE`.

The connector measures upload, download, latency, jitter and failed probes against
the authenticated API route every five seconds. `output_bitrate_kbps` remains an
OBS byte-counter derivative and is never relabeled as upload capacity. Configure
the probe interval and bounded payload with `STREAMML_NETWORK_PROBE_INTERVAL_SECONDS`
and `STREAMML_NETWORK_PROBE_BYTES`.

## Media publication

Prefer authenticated WHIP through the HTTPS `/media/` route when the installed
OBS version and codecs have been verified. RTMP remains available as a local
fallback on `rtmp://127.0.0.1:1935/<media-path>`.

MediaMTX does not transcode the live input. Confirm H.264 video and AAC audio in
OBS so they are compatible with the generated fallback file and target players.
The `media-worker` runs one supervised FFmpeg process for each named RTMP(S)
target declared in `STREAMML_RESTREAM_CONFIG_JSON`. It probes the live MediaMTX
path, sends `/fallback/fallback.mp4` while unavailable, and restores live input
after three successful probes. The OBS scene switch separately provides backup
for the internal MediaMTX/browser path.

Example without printing real keys in logs:

```text
STREAMML_RESTREAM_CONFIG_JSON={"stream-<id>":{"youtube":"rtmps://host/app/SECRET"}}
```

Restart `media-worker` after changing destinations. Validate WHEP/WebRTC, HLS,
the fallback transition and every external platform separately.

## Stop services

```powershell
docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml down
```

Do not add `--volumes` unless intentional deletion of the API session database
has been separately approved and backed up.

## Tests that still require real services

- OBS WebSocket authentication and localhost-only exposure
- connector recovery after OBS restart and Internet loss
- HTTPS telemetry and authenticated session WebSocket
- OBS publication to MediaMTX through WHIP and RTMP
- WHEP/WebRTC across an external network, ICE/TURN and HLS fallback
- phone to VDO.Ninja to OBS, including origin-checked `postMessage` events
- external validation of the HTTP probe against a calibrated network tool
- live profile changes with the selected OBS output mode and encoder
- automatic fallback and recovery with matching H.264/AAC codec parameters
- FFmpeg retransmission to each configured RTMP(S) platform
- certificate renewal, multi-user isolation and sustained-load behavior

Treat this list as the final production acceptance gate. A green unit/integration
suite proves the repository and isolated services; it cannot prove mobile radio
conditions, third-party RTMP ingestion or a real encoder's behavior.
