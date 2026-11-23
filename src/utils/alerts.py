from typing import Any, Literal

from chauff_cmn.logging import logger as log

# Noms réservés (contrat shop ↔ bitcoin-service, §10) : les règles d'Alertmanager se branchent dessus.
AlertName = Literal[
    "webhook_failed_permanently",
    "webhook_rejected",
    "webhook_unknown_address",
    "reorg_after_notification",
    "scanner_stalled",
    "node_unreachable",
    "db_unavailable",
    "price_unavailable",
    "reconciliation_mismatch",
]

# Jamais dans un log d'alerte, même par erreur d'appel.
_FORBIDDEN_FIELDS = frozenset({"authorization", "x_api_key", "api_token", "xpub", "password", "secret"})


def alert(name: AlertName, message: str, *, level: Literal["WARNING", "ERROR"] = "ERROR", **fields: Any) -> None:
    """Journalise une alerte : `alert=true` et `alert_name` sont des clés JSON de premier niveau.

    Une ligne par occurrence ; le dédoublonnage est du ressort d'Alertmanager.
    """
    forbidden = _FORBIDDEN_FIELDS & {key.lower() for key in fields}
    if forbidden:
        raise ValueError(f"Champs interdits dans une alerte : {sorted(forbidden)}")
    log.bind(alert=True, alert_name=name, **fields).log(level, message)
