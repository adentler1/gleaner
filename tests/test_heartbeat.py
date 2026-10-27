from unittest.mock import MagicMock, patch

from gleaner.health import heartbeat


def test_ping_success():
    resp = MagicMock(status_code=200)
    with patch("gleaner.health.heartbeat.requests.get", return_value=resp):
        assert heartbeat.ping("https://hc.example/ping/abc") is True


def test_ping_http_error_is_false():
    resp = MagicMock(status_code=500)
    with patch("gleaner.health.heartbeat.requests.get", return_value=resp):
        assert heartbeat.ping("https://hc.example/ping/abc") is False


def test_ping_network_error_is_false():
    with patch("gleaner.health.heartbeat.requests.get", side_effect=ConnectionError("down")):
        assert heartbeat.ping("https://hc.example/ping/abc") is False
