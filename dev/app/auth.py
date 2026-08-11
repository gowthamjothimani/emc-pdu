from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.config import USERNAME, PASSWORD
import secrets

security = HTTPBasic()

def verify_user(credentials: HTTPBasicCredentials = Depends(security)):

    username_ok = secrets.compare_digest(
        credentials.username,
        USERNAME
    )

    password_ok = secrets.compare_digest(
        credentials.password,
        PASSWORD
    )

    if not (username_ok and password_ok):

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={
                "WWW-Authenticate": "Basic"
            },
        )

    return credentials.username