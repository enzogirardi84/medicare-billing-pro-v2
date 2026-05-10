"""Auth — login y registro de usuarios con JWT."""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta

import jwt
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db, UsuarioModel, _generar_id, _ahora

router = APIRouter()

JWT_SECRET = os.getenv("JWT_SECRET", "cambia-esto-en-produccion-2026")
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _crear_token(user_id: str, username: str, rol: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "rol": rol,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _verificar_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token invalido")


async def obtener_usuario_actual(request: Request, db: Session = Depends(get_db)):
    """Obtiene el usuario actual desde X-API-Key o Authorization Bearer JWT."""
    # Primero intentar JWT
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        payload = _verificar_token(token)
        user = db.query(UsuarioModel).filter(
            UsuarioModel.id == payload["sub"],
            UsuarioModel.activo == "true",
            UsuarioModel.deleted_at == ""
        ).first()
        if user:
            return {"id": user.id, "username": user.username, "rol": user.rol, "nombre": user.nombre}
    # Fallback a API key
    from auth.api_key import verificar_api_key
    try:
        api_key = await verificar_api_key(request)
        return {"id": "api", "username": "api", "rol": "admin", "nombre": "API"}
    except Exception:
        raise HTTPException(401, "Autenticacion requerida: API key o JWT token")


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=4, max_length=100)

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=4, max_length=100)
    nombre: str = Field(default="", max_length=100)
    email: str = Field(default="", max_length=150)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: dict


@router.post("/login", response_model=TokenResponse, summary="Iniciar sesion con usuario y contrasena")
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    password_hash = _hash_password(body.password)
    user = db.query(UsuarioModel).filter(
        UsuarioModel.username == body.username,
        UsuarioModel.password_hash == password_hash,
        UsuarioModel.activo == "true",
        UsuarioModel.deleted_at == ""
    ).first()
    if not user:
        raise HTTPException(401, "Usuario o contrasena incorrectos")
    token = _crear_token(user.id, user.username, user.rol)
    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario": {"id": user.id, "username": user.username, "nombre": user.nombre, "rol": user.rol},
    }


@router.post("/register", response_model=TokenResponse, status_code=201, summary="Registrar nuevo usuario")
async def register(body: RegisterRequest, db: Session = Depends(get_db)):
    # Verificar si ya existe
    existing = db.query(UsuarioModel).filter(UsuarioModel.username == body.username).first()
    if existing:
        raise HTTPException(409, "El usuario ya existe")
    user = UsuarioModel(
        id=_generar_id(),
        username=body.username,
        password_hash=_hash_password(body.password),
        nombre=body.nombre,
        email=body.email,
        rol="user",
        activo="true",
        created_at=_ahora(),
        updated_at=_ahora(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = _crear_token(user.id, user.username, user.rol)
    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario": {"id": user.id, "username": user.username, "nombre": user.nombre, "rol": user.rol},
    }


@router.get("/me", summary="Obtener usuario actual")
async def me(current_user: dict = Depends(obtener_usuario_actual)):
    return {"usuario": current_user}
