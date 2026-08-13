from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError

SECRET_KEY = "visics"
ALGORITHM = "HS256"

USERNAME = "admin"
PASSWORD = "admin"

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/token"
)

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

token_expire_exception = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Token expired",
)


def create_access_token(username: str, expiration_minutes: int = 30):
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expiration_minutes
    )

    payload = {
        "sub": username,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def verify_token(token: str = Depends(oauth2_scheme)):
    if token is None:
        raise credentials_exception

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        exp = payload.get("exp")

        if exp is None:
            raise credentials_exception

        exp_time = datetime.fromtimestamp(
            exp,
            tz=timezone.utc,
        )

        if datetime.now(timezone.utc) > exp_time:
            raise token_expire_exception

        return payload

    except InvalidTokenError:
        raise credentials_exception