from __future__ import annotations

import os
import time
from typing import Dict, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

router = APIRouter(prefix="/admin", tags=["admin-auth"])
security = HTTPBearer(auto_error=False)

# ====== SINGLE ADMIN ACCOUNT (hardcoded) ======
ADMIN_USERNAME = "sinauguardian@gmail.com"
ADMIN_PASSWORD = "bismillahjuara"

# ====== JWT CONFIG ======
JWT_SECRET = os.getenv("JWT_SECRET", "CHANGE_ME_SUPER_SECRET")
JWT_ALG = "HS256"
JWT_EXPIRE_SECONDS = int(os.getenv("JWT_EXPIRE_SECONDS", "86400"))  # 24 jam


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str


def _create_token(username: str) -> str:
    now = int(time.time())
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + JWT_EXPIRE_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def admin_required(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Dict[str, str]:
    if cred is None or cred.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = cred.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    sub = payload.get("sub")
    if sub != ADMIN_USERNAME:
        raise HTTPException(status_code=403, detail="Forbidden")

    return {"username": sub}


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    if body.username != ADMIN_USERNAME or body.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid username/password")
    return TokenResponse(token=_create_token(body.username))


@router.get("/me")
def me(admin=Depends(admin_required)):
    return {"ok": True, "admin": admin}
