import pytest

from src.modules.xpub import normalize_xpub

# Vecteur BIP84 : même clé en zpub (SLIP-132) et en xpub
ZPUB = "zpub6rFR7y4Q2AijBEqTUquhVz398htDFrtymD9xYYfG1m4wAcvPhXNfE3EfH1r1ADqtfSdVCToUG868RvUUkgDKf31mGDtKsAYz2oz2AGutZYs"
XPUB = "xpub6CatWdiZiodmUeTDp8LT5or8nmbKNcuyvz7WyksVFkKB4RHwCD3XyuvPEbvqAQY3rAPshWcMLoP2fMFMKHPJ4ZeZXYVUhLv1VMrjPC7PW6V"


def test_xpub_unchanged_on_main():
    assert normalize_xpub(XPUB, "main") == XPUB


def test_zpub_converted_to_xpub_on_main():
    assert normalize_xpub(ZPUB, "main") == XPUB


@pytest.mark.parametrize("network", ["testnet4", "regtest"])
def test_mainnet_key_refused_on_test_networks(network):
    with pytest.raises(ValueError, match="réseau"):
        normalize_xpub(XPUB, network)


def test_test_key_roundtrip_and_refused_on_main():
    from src.modules.xpub import _CANONICAL, _b58decode_check, _b58encode_check

    tpub = _b58encode_check(_CANONICAL["regtest"] + _b58decode_check(XPUB)[4:])
    assert tpub.startswith("tpub")
    assert normalize_xpub(tpub, "regtest") == tpub
    with pytest.raises(ValueError, match="réseau"):
        normalize_xpub(tpub, "main")


def test_corrupted_key_refused():
    with pytest.raises(ValueError, match="somme de contrôle"):
        normalize_xpub(XPUB[:-1] + ("a" if XPUB[-1] != "a" else "b"), "main")


def test_private_key_refused():
    xprv = "xprv9s21ZrQH143K3QTDL4LXw2F7HEK3wJUD2nW2nRk4stbPy6cq3jPPqjiChkVvvNKmPGJxWUtg6LnF5kejMRNNU3TGtRBeJgk33yuGBxrMPHi"
    with pytest.raises(ValueError, match="réseau"):
        normalize_xpub(xprv, "main")


def test_garbage_refused():
    with pytest.raises(ValueError):
        normalize_xpub("0OIl-not-base58", "main")
