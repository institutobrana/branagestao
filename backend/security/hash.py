from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["bcrypt_sha256", "bcrypt"],
    deprecated="auto",
    bcrypt__truncate_error=False,
)

BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2x$", "$2y$")
BCRYPT_MAX_PASSWORD_BYTES = 72


def hash_password(password: str):
    return pwd_context.hash(password)


def _is_legacy_bcrypt_hash(hashed: str) -> bool:
    return hashed.startswith(BCRYPT_PREFIXES)


def _truncate_bcrypt_secret(password: str) -> bytes:
    return password.encode("utf-8")[:BCRYPT_MAX_PASSWORD_BYTES]


def verify_password(password: str, hashed: str):
    if not password or not hashed:
        return False

    secret: str | bytes = password
    if _is_legacy_bcrypt_hash(hashed):
        secret = _truncate_bcrypt_secret(password)

    try:
        return bool(pwd_context.verify(secret, hashed))
    except (ValueError, TypeError):
        return False
