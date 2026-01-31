from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from .admin_auth import ADMIN_USERNAME, ADMIN_PASSWORD, create_token, require_admin

router = APIRouter(prefix="/admin", tags=["admin-auth"])


class LoginReq(BaseModel):
    username: str
    password: str


class LoginResp(BaseModel):
    token: str


@router.post("/login", response_model=LoginResp)
def login(req: LoginReq) -> LoginResp:
    if req.username != ADMIN_USERNAME or req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return LoginResp(token=create_token(req.username))


@router.get("/me")
def me(user: str = Depends(require_admin)):
    return {"ok": True, "user": user}
