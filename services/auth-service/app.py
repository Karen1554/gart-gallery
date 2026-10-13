import os
import secrets
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import connection
from psycopg.errors import UniqueViolation
from psycopg.types.json import Json

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field


app = FastAPI(title="Gart Gallery Auth Service", version="1.0.0")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="VISITANTE", pattern="^(VISITANTE|ARTISTA)$")


class User(BaseModel):
    id: int
    username: str
    role: str
    permissions: list[str]
    active: bool = True


class LoginResponse(BaseModel):
    ok: bool
    user: User
    access_token: str
    token_type: str = "bearer"




def init_db() -> None:
    with connection() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_users (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                permissions JSONB NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES auth_users(id),
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        if db.execute("SELECT COUNT(*) AS count FROM auth_users").fetchone()["count"] == 0:
            permissions = ["works:read", "works:write", "galleries:read", "content:read"]
            db.execute(
                """
                INSERT INTO auth_users (username, password, role, permissions, active)
                VALUES (%s, %s, %s, %s, TRUE)
                """,
                (ADMIN_USER, ADMIN_PASSWORD, "WEBMASTER", Json(permissions)),
            )


def user_from_row(row: dict) -> User:
    return User(
        id=row["id"],
        username=row["username"],
        role=row["role"],
        permissions=row["permissions"],
        active=row["active"],
    )


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "auth", "status": "ok"}


@app.post("/api/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    with connection() as db:
        row = db.execute(
            "SELECT * FROM auth_users WHERE username = %s",
            (payload.username,),
        ).fetchone()
        if row is None or row["password"] != payload.password or not row["active"]:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        user = user_from_row(row)
        access_token = secrets.token_urlsafe(32)
        db.execute(
            "INSERT INTO auth_sessions (token, user_id) VALUES (%s, %s)",
            (access_token, user.id),
        )
    return LoginResponse(ok=True, user=user, access_token=access_token)


@app.post("/api/auth/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest) -> LoginResponse:
    permissions = ["works:read", "galleries:read", "content:read"]
    if payload.role == "ARTISTA":
        permissions.append("works:submit")
    try:
        with connection() as db:
            cursor = db.execute(
                """
                INSERT INTO auth_users (username, password, role, permissions, active)
                VALUES (%s, %s, %s, %s, TRUE)
                RETURNING id
                """,
                (payload.username, payload.password, payload.role, Json(permissions)),
            )
            user_id = cursor.fetchone()["id"]
            user = User(
                id=user_id,
                username=payload.username,
                role=payload.role,
                permissions=permissions,
            )
            access_token = secrets.token_urlsafe(32)
            db.execute(
                "INSERT INTO auth_sessions (token, user_id) VALUES (%s, %s)",
                (access_token, user.id),
            )
    except UniqueViolation:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already registered")
    return LoginResponse(ok=True, user=user, access_token=access_token)


def token_from_header(authorization: str | None) -> str:
    return authorization.removeprefix("Bearer ").strip() if authorization else ""


@app.get("/api/auth/me")
def current_user(authorization: str | None = Header(default=None)) -> dict[str, bool | User]:
    token = token_from_header(authorization)
    with connection() as db:
        row = db.execute(
            """
            SELECT u.* FROM auth_sessions s
            JOIN auth_users u ON u.id = s.user_id
            WHERE s.token = %s
            """,
            (token,),
        ).fetchone()
    user = user_from_row(row) if row is not None and row["active"] else None
    return {"authenticated": user is not None, **({"user": user} if user else {})}


@app.post("/api/auth/logout")
def logout(authorization: str | None = Header(default=None)) -> dict[str, bool]:
    with connection() as db:
        db.execute("DELETE FROM auth_sessions WHERE token = %s", (token_from_header(authorization),))
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3003)
