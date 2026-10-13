import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import connection
from psycopg.types.json import Json

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(title="Gart Gallery Purchase Service", version="1.0.0")


class CartItem(BaseModel):
    work_id: int
    quantity: int = Field(default=1, ge=1)
    unit_price: float = Field(ge=0)


class Cart(BaseModel):
    user_id: int
    items: list[CartItem] = Field(default_factory=list)


class Purchase(BaseModel):
    id: int
    user_id: int
    items: list[CartItem]
    total: float
    status: str = "pending"
    created_at: datetime


class PurchaseInput(BaseModel):
    user_id: int
    items: list[CartItem] = Field(min_length=1)




def init_db() -> None:
    with connection() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS purchase_carts (
                user_id INTEGER PRIMARY KEY,
                items JSONB NOT NULL DEFAULT '[]'::jsonb
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS purchase_purchases (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                items JSONB NOT NULL,
                total DOUBLE PRECISION NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMPTZ NOT NULL
            )
            """
        )


def items_from_json(value: list[dict] | str) -> list[CartItem]:
    return [CartItem(**item) for item in (json.loads(value) if isinstance(value, str) else value)]


def cart_from_row(row: dict) -> Cart:
    return Cart(user_id=row["user_id"], items=items_from_json(row["items"]))


def purchase_from_row(row: dict) -> Purchase:
    return Purchase(
        id=row["id"],
        user_id=row["user_id"],
        items=items_from_json(row["items"]),
        total=row["total"],
        status=row["status"],
        created_at=(
            datetime.fromisoformat(row["created_at"])
            if isinstance(row["created_at"], str) else row["created_at"]
        ),
    )


def items_json(items: list[CartItem]) -> Json:
    return Json([item.model_dump() for item in items])


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "purchase", "status": "ok"}


@app.get("/api/cart/{user_id}", response_model=Cart)
def get_cart(user_id: int) -> Cart:
    with connection() as db:
        row = db.execute("SELECT * FROM purchase_carts WHERE user_id = %s", (user_id,)).fetchone()
        if row is None:
            db.execute("INSERT INTO purchase_carts (user_id, items) VALUES (%s, '[]')", (user_id,))
            return Cart(user_id=user_id)
    return cart_from_row(row)


@app.put("/api/cart/{user_id}", response_model=Cart)
def update_cart(user_id: int, items: list[CartItem]) -> Cart:
    cart = Cart(user_id=user_id, items=items)
    with connection() as db:
        db.execute(
            """
            INSERT INTO purchase_carts (user_id, items) VALUES (%s, %s)
            ON CONFLICT(user_id) DO UPDATE SET items = excluded.items
            """,
            (user_id, items_json(items)),
        )
    return cart


@app.delete("/api/cart/{user_id}")
def clear_cart(user_id: int) -> dict[str, bool]:
    with connection() as db:
        db.execute(
            """
            INSERT INTO purchase_carts (user_id, items) VALUES (%s, '[]')
            ON CONFLICT(user_id) DO UPDATE SET items = '[]'
            """,
            (user_id,),
        )
    return {"ok": True}


@app.get("/api/purchases")
def list_purchases(user_id: int | None = None) -> dict[str, list[Purchase]]:
    with connection() as db:
        if user_id is None:
            rows = db.execute("SELECT * FROM purchase_purchases ORDER BY id").fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM purchase_purchases WHERE user_id = %s ORDER BY id",
                (user_id,),
            ).fetchall()
    return {"items": [purchase_from_row(row) for row in rows]}


@app.post("/api/purchases", response_model=Purchase, status_code=201)
def create_purchase(payload: PurchaseInput) -> Purchase:
    total = sum(item.quantity * item.unit_price for item in payload.items)
    created_at = datetime.now(timezone.utc)
    with connection() as db:
        cursor = db.execute(
            """
            INSERT INTO purchase_purchases (user_id, items, total, status, created_at)
            VALUES (%s, %s, %s, 'pending', %s)
            RETURNING id
            """,
            (payload.user_id, items_json(payload.items), total, created_at.isoformat()),
        )
        purchase_id = cursor.fetchone()["id"]
    return Purchase(
        id=purchase_id,
        user_id=payload.user_id,
        items=payload.items,
        total=total,
        created_at=created_at,
    )


@app.get("/api/purchases/{purchase_id}", response_model=Purchase)
def get_purchase(purchase_id: int) -> Purchase:
    with connection() as db:
        row = db.execute("SELECT * FROM purchase_purchases WHERE id = %s", (purchase_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return purchase_from_row(row)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3004)
