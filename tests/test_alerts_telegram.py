from unittest.mock import MagicMock, patch

import pytest

from gleaner import db
from gleaner.alerts import telegram


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.sqlite3")
    db.migrate(c)
    return c


def _response(status_code=200, ok=True, text="{}"):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.json.return_value = {"ok": ok}
    return resp


def test_send_alert_success_logs_delivered(conn):
    # item_id is None here: milestone 1a alerts are health-state alerts, not
    # tied to a specific item (that linkage arrives with scoring in 1b).
    with patch("gleaner.alerts.telegram.requests.post", return_value=_response()) as mock_post:
        delivered = telegram.send_alert(conn, bot_token="t", chat_id="c", message="hello")

    assert delivered is True
    assert mock_post.call_count == 1
    row = conn.execute("SELECT * FROM alerts").fetchone()
    assert row["delivered"] == 1
    assert row["item_id"] is None


def test_send_alert_retries_then_logs_undelivered(conn):
    with patch(
        "gleaner.alerts.telegram.requests.post", return_value=_response(status_code=401, ok=False)
    ) as mock_post, patch("gleaner.alerts.telegram.time.sleep"):
        delivered = telegram.send_alert(conn, bot_token="bad", chat_id="c", message="hello")

    assert delivered is False
    assert mock_post.call_count == telegram.MAX_RETRIES
    row = conn.execute("SELECT * FROM alerts").fetchone()
    assert row["delivered"] == 0
    assert row["retry_count"] == telegram.MAX_RETRIES


def test_send_alert_recovers_after_transient_failure(conn):
    responses = [_response(status_code=500, ok=False), _response()]
    with patch("gleaner.alerts.telegram.requests.post", side_effect=responses), \
         patch("gleaner.alerts.telegram.time.sleep"):
        delivered = telegram.send_alert(conn, bot_token="t", chat_id="c", message="hello")

    assert delivered is True
    row = conn.execute("SELECT * FROM alerts").fetchone()
    assert row["delivered"] == 1
    assert row["retry_count"] == 1
