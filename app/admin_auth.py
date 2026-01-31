from __future__ import annotations

import os
import time
from typing import Dict, Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import jwt  # wajib PyJWT

security = HTTPBearer()

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "sinauguardian@gmail.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "bismillahjuara")

# PENTING: samakan secret ini di semua endpoint (login & verify)
JWT_SECRET = os.getenv("JWT_SECRET", "CHANGE_ME_PLEASE")
JWT_EXPIRE_SECONDS = int(os.getenv("JWT_EXPIRE_SECONDS", "86400"))  # 24 jam


def create_token(username: str) -> str:
    now = int(time.time())
    payload = {"sub": username, "iat": now, "exp": now + JWT_EXPIRE_SECONDS}
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    # PyJWT kadang balikin bytes di versi lama
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def verify_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_admin(creds: HTTPAuthorizationCredentials = Depends(security)) -> str:
    payload = verify_token(creds.credentials)
    user = payload.get("sub")
    if user != ADMIN_USERNAME:
        raise HTTPException(status_code=403, detail="Forbidden")
    return user
