import random

import pytest

from src.workers.backoff import HOURLY, SCHEDULE, retry_delay
from src.workers.sender import Outcome, classify


@pytest.mark.parametrize(("attempts", "base"), [(1, 5), (2, 15), (3, 60), (4, 300), (5, 900), (6, HOURLY), (50, HOURLY)])
def test_delay_follows_the_schedule_with_jitter(attempts, base):
    delays = [retry_delay(attempts, random.Random(seed)) for seed in range(200)]
    assert min(delays) >= base * 0.8
    assert max(delays) <= base * 1.2
    assert max(delays) - min(delays) > base * 0.1  # la gigue joue vraiment


def test_schedule_is_increasing():
    assert list(SCHEDULE) == sorted(SCHEDULE) and SCHEDULE[-1] < HOURLY


def test_delay_requires_a_first_attempt():
    with pytest.raises(ValueError):
        retry_delay(0)


@pytest.mark.parametrize(
    ("status", "outcome"),
    [
        (200, Outcome.DELIVERED),
        (201, Outcome.DELIVERED),
        (404, Outcome.RETRY),
        (408, Outcome.RETRY),
        (429, Outcome.RETRY),
        (500, Outcome.RETRY),
        (503, Outcome.RETRY),
        (400, Outcome.REJECTED),
        (401, Outcome.REJECTED),
        (409, Outcome.REJECTED),
        (403, Outcome.REJECTED),
    ],
)
def test_classify_shop_responses(status, outcome):
    assert classify(status) is outcome
