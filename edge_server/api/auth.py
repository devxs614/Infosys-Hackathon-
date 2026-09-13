"""Central authentication endpoints for every laptop on the Rumbo network."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from edge_server.data.auth_store import AuthConflictError, AuthInvalidCredentialsError
from edge_server.models import AuthLoginRequest, AuthRegisterRequest

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: AuthRegisterRequest, request: Request) -> dict:
    try:
        return request.app.state.auth_store.register(**payload.model_dump())
    except AuthConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/login")
async def login(payload: AuthLoginRequest, request: Request) -> dict:
    try:
        return request.app.state.auth_store.login(**payload.model_dump())
    except AuthInvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
