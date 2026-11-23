import json

import pytest
from chauff_cmn.logging import logger as log

from src.utils.alerts import alert


@pytest.fixture
def records():
    captured = []
    handler_id = log.add(lambda message: captured.append(message.record), level="DEBUG")
    try:
        yield captured
    finally:
        log.remove(handler_id)


def test_alert_sets_structured_fields(records):
    alert("webhook_rejected", "Le shop a refusé le webhook", txid="abc", vout=0, status_code=409)

    extra = records[-1]["extra"]
    assert extra["alert"] is True
    assert extra["alert_name"] == "webhook_rejected"
    assert (extra["txid"], extra["vout"], extra["status_code"]) == ("abc", 0, 409)
    assert records[-1]["level"].name == "ERROR"
    json.dumps(extra, default=str)


def test_alert_warning_level(records):
    alert("price_unavailable", "Taux indisponible", level="WARNING")
    assert records[-1]["level"].name == "WARNING"


@pytest.mark.parametrize("field", ["xpub", "Authorization", "password", "api_token"])
def test_alert_refuses_secret_fields(records, field):
    with pytest.raises(ValueError):
        alert("node_unreachable", "RPC injoignable", **{field: "x"})
    assert records == []
