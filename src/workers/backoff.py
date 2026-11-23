import random

# Délais entre deux essais (secondes) : 5 s, 15 s, 1 min, 5 min, 15 min, puis toutes les heures.
SCHEDULE = (5, 15, 60, 300, 900)
HOURLY = 3600
JITTER = 0.2


def retry_delay(attempts: int, rng: random.Random | None = None) -> float:
    """Délai avant l'essai suivant, après `attempts` essais déjà faits (au moins 1), avec ±20 % de gigue."""
    if attempts < 1:
        raise ValueError("attempts doit être au moins 1")
    base = SCHEDULE[attempts - 1] if attempts <= len(SCHEDULE) else HOURLY
    spread = (rng or random).uniform(-JITTER, JITTER)
    return base * (1 + spread)
