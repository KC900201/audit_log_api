# To execute authentication
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from uuid import UUID

import jwt

SECRET_KEY = "sample-secret"
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
security = HTTPBearer()

def verify_jwt(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload # include "tenant_id", "role", "sub" etc.
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT token")

def generate_mock_jwt():
    payload = {
        "sub": "user123",
        "tenant_id": "f248d1ee-f3c7-458a-9c17-27cef4b89e38",
        "role": "admin",
        "exp": datetime.utcnow() + timedelta(hours=1)
    }

    token = jwt.encode(payload, SECRET_KEY, ALGORITHM)
    return token

def generate_mock_user_jwt():
    payload = {
        "sub": "user123",
        "tenant_id": "f248d1ee-f3c7-458a-9c17-27cef4b89e38",
        "role": "user",
        "exp": datetime.utcnow() + timedelta(hours=1)
    }

    token = jwt.encode(payload, SECRET_KEY, ALGORITHM)
    return token
