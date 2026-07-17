"""Command-line runtime for the StreamML local connector."""

from __future__ import annotations

import argparse
import logging
import random
import re
import time
from typing import Any, Sequence

from .api_client import ApiClientError, StreamMLApiClient
from .config import ConfigurationError, ConnectorConfig, load_config
from .obs_client import ObsClient, ObsSnapshot
from .network_probe import NetworkMeasurement, NetworkProbe
from .secrets import (
    ConnectorCredentials,
    SecretStorageError,
    TokenStore,
    read_obs_password,
    read_pairing_code,
)


LOGGER = logging.getLogger("streamml_connector")


class _SecretRedactionFilter(logging.Filter):
    """Defense-in-depth redaction for accidental credential-like log text."""

    _patterns = (
        re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
        re.compile(r"(?i)((?:password|access_token|pairing_code|token)\s*[:=]\s*)[^\s,;]+"),
    )

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern in self._patterns:
            message = pattern.sub(r"\1[REDACTED]", message)
        record.msg = message
        record.args = ()
        return True


def _configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(_SecretRedactionFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    # obsws-python logs connection state; keep it at warning to avoid verbose
    # protocol details while retaining authentication/connectivity failures.
    logging.getLogger("obsws_python").setLevel(logging.WARNING)


def _telemetry_payload(
    config: ConnectorConfig,
    credentials: ConnectorCredentials,
    snapshot: ObsSnapshot,
    sequence: int,
    network: NetworkMeasurement | None = None,
) -> dict[str, Any]:
    metrics = snapshot.metrics()
    observed_at = str(metrics.pop("observed_at"))
    # These two values are represented by the API's explicit unsupported
    # contract, never as OBS-derived metrics.
    metrics.pop("latency_ms")
    metrics.pop("packet_loss_percent")
    session_id = credentials.session_id or config.session_id
    if session_id is None:
        raise SecretStorageError(
            "The pairing response did not provide a session id and STREAMML_SESSION_ID is unset."
        )
    payload = {
        "session_id": session_id,
        "sequence": sequence,
        "observed_at": observed_at,
        "source": "obs_websocket_5",
        "metrics": metrics,
        "unsupported": {
            "latency_ms": None,
            "packet_loss_percent": None,
            "upload_mbps": None,
            "download_mbps": None,
            "connection_capacity_mbps": None,
        },
    }
    if network is not None:
        payload["network"] = network.to_dict()
    return payload


def _send_disconnected(
    api: StreamMLApiClient,
    config: ConnectorConfig,
    credentials: ConnectorCredentials,
    sequence: int,
) -> None:
    try:
        api.send_telemetry(
            credentials,
            _telemetry_payload(config, credentials, ObsSnapshot.disconnected(), sequence),
        )
    except ApiClientError:
        LOGGER.warning("OBS is unavailable and the disconnected state could not reach the API.")


def run(*, pair: bool, once: bool, forget_token: bool) -> int:
    config = load_config()
    _configure_logging(config.log_level)
    store = TokenStore(config.keyring_service, config.api_base_url, config.connector_name)

    if forget_token:
        store.delete()
        LOGGER.info("Stored connector credentials removed from the operating-system keyring.")
        return 0

    api = StreamMLApiClient(config)
    obs_client = ObsClient(config)
    try:
        credentials = store.load()
        if pair:
            code = read_pairing_code(None)
            credentials = api.link(code)
            store.save(credentials)
            LOGGER.info("Connector linked; API token stored in the operating-system keyring.")
        if credentials is None:
            raise SecretStorageError("No connector token is stored. Run with --pair first.")

        # The API's pairing response is authoritative for session scope. A
        # configured session is only a compatibility fallback.
        if credentials.session_id is None and config.session_id is None:
            raise SecretStorageError(
                "The pairing response did not provide a session id and STREAMML_SESSION_ID is unset."
            )

        obs_password = read_obs_password()
        delay = config.reconnect_initial_seconds
        sequence = time.time_ns()
        network_probe = NetworkProbe(api, credentials, config.network_probe_bytes)
        last_network: NetworkMeasurement | None = None
        next_network_probe_at = 0.0

        while True:
            try:
                obs_client.connect(obs_password)
                LOGGER.info("Connected to local authenticated OBS WebSocket.")
                delay = config.reconnect_initial_seconds
                while True:
                    snapshot = obs_client.collect()
                    now = time.monotonic()
                    if now >= next_network_probe_at:
                        measured = network_probe.measure()
                        if measured is not None:
                            last_network = measured
                        next_network_probe_at = now + config.network_probe_interval_seconds
                    payload = _telemetry_payload(
                        config, credentials, snapshot, sequence, last_network
                    )
                    api.send_telemetry(credentials, payload)
                    command = api.next_command(credentials)
                    if command is not None:
                        try:
                            obs_client.apply_command(command)
                        except Exception as exc:
                            api.acknowledge_command(
                                credentials,
                                str(command["id"]),
                                success=False,
                                error_message=type(exc).__name__,
                            )
                            LOGGER.error("OBS rejected a StreamML control command (%s).", type(exc).__name__)
                        else:
                            api.acknowledge_command(
                                credentials, str(command["id"]), success=True
                            )
                            LOGGER.info("Applied StreamML control command %s.", command.get("command_type"))
                    sequence += 1
                    if once:
                        return 0
                    time.sleep(config.poll_interval_seconds)
            except KeyboardInterrupt:
                LOGGER.info("Connector stopped by the operator.")
                return 0
            except Exception as exc:  # reconnect boundary for OBS and API outages
                # Exception text is intentionally omitted because third-party
                # libraries can include URLs or protocol details in messages.
                LOGGER.warning("Connector cycle failed (%s); reconnecting.", type(exc).__name__)
                obs_client.disconnect()
                _send_disconnected(api, config, credentials, sequence)
                sequence += 1
                if once:
                    return 2
                wait_seconds = min(
                    config.reconnect_max_seconds,
                    delay * random.uniform(0.8, 1.2),
                )
                time.sleep(wait_seconds)
                delay = min(config.reconnect_max_seconds, delay * 2.0)
    finally:
        obs_client.disconnect()
        api.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="streamml-connector",
        description="Local OBS telemetry and authenticated StreamML control connector.",
    )
    parser.add_argument(
        "--pair",
        action="store_true",
        help="exchange a hidden, one-time linking code and save the token in the OS keyring",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="collect and send one sample, useful for an explicit connectivity check",
    )
    parser.add_argument(
        "--forget-token",
        action="store_true",
        help="remove the connector API token from the operating-system keyring",
    )
    return parser


def cli(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return run(pair=args.pair, once=args.once, forget_token=args.forget_token)
    except (ConfigurationError, SecretStorageError, ApiClientError) as exc:
        # These messages are authored locally and contain no secret values.
        logging.getLogger("streamml_connector").error("%s", exc)
        return 2
