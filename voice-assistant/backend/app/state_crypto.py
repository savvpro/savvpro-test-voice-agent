"""Encrypt persisted call state so patient details are not stored in plaintext."""
from cryptography.fernet import Fernet, InvalidToken

from . import config as C

_key = C.CALL_STATE_ENCRYPTION_KEY.encode() if C.CALL_STATE_ENCRYPTION_KEY else Fernet.generate_key()
_fernet = Fernet(_key)
_PREFIX = "fernet:"


def encrypt_state(value: str) -> str:
    return _PREFIX + _fernet.encrypt(value.encode()).decode()


def decrypt_state(value: str) -> str:
    if not value.startswith(_PREFIX):
        raise InvalidToken
    return _fernet.decrypt(value[len(_PREFIX):].encode()).decode()
