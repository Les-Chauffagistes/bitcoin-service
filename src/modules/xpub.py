from hashlib import sha256

_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

# Octets de version des clés étendues publiques (BIP32 et SLIP-132).
_XPUB = bytes.fromhex("0488b21e")
_TPUB = bytes.fromhex("043587cf")
_ZPUB = bytes.fromhex("04b24746")
_VPUB = bytes.fromhex("045f1cf6")

# Versions acceptées par réseau, et version canonique du descripteur.
_ACCEPTED = {
    "main": (_XPUB, _ZPUB),
    "testnet4": (_TPUB, _VPUB),
    "regtest": (_TPUB, _VPUB),
}
_CANONICAL = {"main": _XPUB, "testnet4": _TPUB, "regtest": _TPUB}


def _b58decode_check(value: str) -> bytes:
    number = 0
    for char in value:
        index = _ALPHABET.find(char)
        if index < 0:
            raise ValueError("Clé publique étendue invalide : caractère inattendu")
        number = number * 58 + index
    raw = number.to_bytes((number.bit_length() + 7) // 8, "big")
    raw = b"\x00" * (len(value) - len(value.lstrip("1"))) + raw
    payload, checksum = raw[:-4], raw[-4:]
    if sha256(sha256(payload).digest()).digest()[:4] != checksum:
        raise ValueError("Clé publique étendue invalide : somme de contrôle incorrecte")
    return payload


def _b58encode_check(payload: bytes) -> str:
    raw = payload + sha256(sha256(payload).digest()).digest()[:4]
    number = int.from_bytes(raw, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = _ALPHABET[remainder] + encoded
    return "1" * (len(raw) - len(raw.lstrip(b"\x00"))) + encoded


def normalize_xpub(xpub: str, network: str) -> str:
    """Renvoie la clé au format du descripteur (xpub ou tpub), après avoir vérifié qu'elle est du bon réseau.

    Une zpub / vpub (SLIP-132) est convertie ; une clé privée étendue ou d'un autre réseau est refusée.
    """
    payload = _b58decode_check(xpub.strip())
    if len(payload) != 78:
        raise ValueError("Clé publique étendue invalide : longueur inattendue")
    version = payload[:4]
    if version not in _ACCEPTED[network]:
        raise ValueError(f"La clé publique étendue ne correspond pas au réseau {network}")
    return _b58encode_check(_CANONICAL[network] + payload[4:])
