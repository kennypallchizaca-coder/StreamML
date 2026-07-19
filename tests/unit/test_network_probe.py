from apps.connector.streamml_connector.network_probe import NetworkProbe
from apps.connector.streamml_connector.secrets import ConnectorCredentials


class FakeApi:
    def probe_latency(self, _credentials):
        return None

    def probe_download(self, _credentials, size):
        return size

    def probe_upload(self, _credentials, payload):
        return len(payload)


def test_network_probe_reports_compatible_metrics_without_obs_bitrate() -> None:
    times = iter((0.0, 0.050, 1.0, 1.2, 2.0, 2.4))
    probe = NetworkProbe(
        FakeApi(),
        ConnectorCredentials("secret", "connector", "session"),
        100_000,
        monotonic=lambda: next(times),
    )
    measured = probe.measure()
    assert measured is not None
    assert measured.source == "streamml_http_probe"
    assert measured.latency_ms == 50.0
    assert measured.download_mbps == 4.0
    assert measured.upload_mbps == 2.0
    assert measured.connection_capacity_mbps == measured.upload_mbps
    assert measured.packet_loss_percent == 0.0
