import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(title="Gart Gallery Purchase Service", version="1.0.0")
DB_PATH = os.getenv(
    "DB_PATH",
    str(Path(__file__).resolve().parent / "data" / "purchase.db"),
)


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


@contextmanager
def connection():
    Path(DB_PATH).expanduser().parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    with connection() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS carts (
                user_id INTEGER PRIMARY KEY,
                items TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                items TEXT NOT NULL,
                total REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
            """
        )


def items_from_json(value: str) -> list[CartItem]:
    return [CartItem(**item) for item in json.loads(value)]


def cart_from_row(row: sqlite3.Row) -> Cart:
    return Cart(user_id=row["user_id"], items=items_from_json(row["items"]))


def purchase_from_row(row: sqlite3.Row) -> Purchase:
    return Purchase(
        id=row["id"],
        user_id=row["user_id"],
        items=items_from_json(row["items"]),
        total=row["total"],
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def items_json(items: list[CartItem]) -> str:
    return json.dumps([item.model_dump() for item in items])


init_db()


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "purchase", "status": "ok"}


@app.get("/api/cart/{user_id}", response_model=Cart)
def get_cart(user_id: int) -> Cart:
    with connection() as db:
        row = db.execute("SELECT * FROM carts WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            db.execute("INSERT INTO carts (user_id, items) VALUES (?, '[]')", (user_id,))
            return Cart(user_id=user_id)
    return cart_from_row(row)


@app.put("/api/cart/{user_id}", response_model=Cart)
def update_cart(user_id: int, items: list[CartItem]) -> Cart:
    cart = Cart(user_id=user_id, items=items)
    with connection() as db:
        db.execute(
            """
            INSERT INTO carts (user_id, items) VALUES (?, ?)
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
            INSERT INTO carts (user_id, items) VALUES (?, '[]')
            ON CONFLICT(user_id) DO UPDATE SET items = '[]'
            """,
            (user_id,),
        )
    return {"ok": True}


@app.get("/api/purchases")
def list_purchases(user_id: int | None = None) -> dict[str, list[Purchase]]:
    with connection() as db:
        if user_id is None:
            rows = db.execute("SELECT * FROM purchases ORDER BY id").fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM purchases WHERE user_id = ? ORDER BY id",
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
            INSERT INTO purchases (user_id, items, total, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
            """,
            (payload.user_id, items_json(payload.items), total, created_at.isoformat()),
        )
        purchase_id = cursor.lastrowid
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
        row = db.execute("SELECT * FROM purchases WHERE id = ?", (purchase_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return purchase_from_row(row)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3004)
