from src.v1.errors import missing_currency_error


def test_missing_currency_error_shape():
    assert missing_currency_error.status == 400
    assert missing_currency_error.content_type == "application/json"
    assert b"invalid payload" in missing_currency_error.body
