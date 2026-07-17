# StreamML online deployment

This deployment is an implementation baseline, not evidence that the system is
production-ready. Real OBS, phone, network, MediaMTX, WebRTC and TLS tests remain
mandatory before any production claim.

## Prerequisites

- Docker Engine with Compose
- a public DNS name and trusted TLS certificate for online use
- UDP 8189 reachable by WebRTC clients, or a configured TURN service
- OBS WebSocket 5.x enabled only on localhost with authentication
- official StreamML release artifacts already present under `models/registry/`

The Compose deployment mounts `models/registry/` read-only. Versioned data and
feature contracts live under `src/streamml/config/` and are copied with the API
source. The deployment does not train, overwrite or regenerate model artifacts.

## Server deployment

1. Copy `deployment/.env.example` to `deployment/.env` outside version control.
2. Replace every `CHANGE_ME` and both TLS paths.
   `STREAMML_MEDIA_AUTH_SECRET` must be at least 32 URL-safe random characters.
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

The connector only invokes OBS `GetStats` and `GetStreamStatus`. It never invokes
Set, Start, Stop or Toggle methods. `output_bitrate_kbps` is derived from changes
in OBS `outputBytes` and must not be relabeled as upload capacity. Latency and
packet loss remain `null` because OBS does not provide them.

## Media publication

Prefer authenticated WHIP through the HTTPS `/media/` route when the installed
OBS version and codecs have been verified. RTMP remains available as a local
fallback on `rtmp://127.0.0.1:1935/<media-path>`.

MediaMTX does not transcode. Confirm the actual OBS audio/video codecs in every
target browser. Validate WHEP/WebRTC first and HLS fallback separately.

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
- real latency, packet-loss and network-capacity measurement sources
- certificate renewal, multi-user isolation and sustained-load behavior
