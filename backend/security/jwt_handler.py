from datetime import datetime, timedelta
from jose import JWTError, jwt

SECRET_KEY = "BRANA_SAAS_SUPER_SECRET_2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def create_access_token(data: dict, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES):
    to_encode = data.copy()
    ttl = max(1, int(expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES))
    expire = datetime.utcnow() + timedelta(minutes=ttl)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
