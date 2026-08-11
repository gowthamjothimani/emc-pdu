from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from .config import API_USERNAME, API_PASSWORD, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

token_expire_exception = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Token expired",
    headers={"WWW-Authenticate": "Bearer"},
)


def authenticate_user(username: str, password: str) -> bool:
    return username == API_USERNAME and password == API_PASSWORD


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta is not None else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": int(expire.timestamp())})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_acv_token(token: str = Depends(oauth2_scheme)):
    if token is None:
        raise credentials_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp = payload.get("exp")
        if isinstance(exp, datetime):
            exp_time = exp
        else:
            exp_time = datetime.fromtimestamp(int(exp), tz=timezone.utc)
        if datetime.now(timezone.utc) > exp_time:
            raise token_expire_exception
        return payload
    except InvalidTokenError:
        raise credentials_exception
