from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
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
    if req.username == ADMIN_USERNAME and req.password == ADMIN_PASSWORD:
        return LoginResp(token=create_token(req.username))
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.get("/me")
def me(user: str = Depends(require_admin)):
    return {"ok": True, "user": user}
