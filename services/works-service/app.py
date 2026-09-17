import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field


app = FastAPI(title="Gart Gallery Works Service", version="1.0.0")
DB_PATH = os.getenv(
    "DB_PATH",
    str(Path(__file__).resolve().parent / "data" / "works.db"),
)


class Work(BaseModel):
    id: int
    title: str
    description: str = ""
    year: str = ""
    category: str = "Landscape Paintings"
    image_url: str | None = None
    artist_id: int | None = None
    gallery_id: int | None = None
    available: bool = True
    price: float | None = None
    moderation_status: str = "published"
    created_at: datetime


class WorkInput(BaseModel):
    title: str = Field(min_length=1)
    description: str = ""
    year: str = ""
    category: str = "Landscape Paintings"
    image_url: str | None = None
    artist_id: int | None = None
    gallery_id: int | None = None
    available: bool = True
    price: float | None = Field(default=None, ge=0)
    moderation_status: str = "published"


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
            CREATE TABLE IF NOT EXISTS works (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                year TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT 'Landscape Paintings',
                image_url TEXT,
                artist_id INTEGER,
                gallery_id INTEGER,
                available INTEGER NOT NULL DEFAULT 1,
                price REAL,
                moderation_status TEXT NOT NULL DEFAULT 'published',
                created_at TEXT NOT NULL
            )
            """
        )
        if db.execute("SELECT COUNT(*) FROM works").fetchone()[0] == 0:
            seed = [
                Work(
                    id=1, title="Reflejos del alma", description="Una exploración de luz y memoria.",
                    year="2024", category="Landscape Paintings",
                    image_url="https://images.unsplash.com/photo-1549490349-8643362247b5?auto=format&fit=crop&w=700&q=85",
                    artist_id=1, gallery_id=1, available=True, price=1200000,
                    created_at=datetime(2024, 5, 1, tzinfo=timezone.utc),
                ),
                Work(
                    id=2, title="Naturaleza abstracta", description="Texturas y color en movimiento.",
                    year="2025", category="Abstract Oil Paintings",
                    image_url="https://images.unsplash.com/photo-1577083288073-40892c0860a4?auto=format&fit=crop&w=700&q=85",
                    artist_id=2, gallery_id=2, available=True, price=950000,
                    created_at=datetime(2024, 5, 2, tzinfo=timezone.utc),
                ),
                Work(
                    id=3, title="Sueños de colores", description="Una composición sobre libertad e imaginación.",
                    year="2024", category="Abstract Watercolours",
                    image_url="https://images.unsplash.com/photo-1579783902614-a3fb3927b6a5?auto=format&fit=crop&w=700&q=85",
                    artist_id=3, gallery_id=1, available=True, price=1500000,
                    created_at=datetime(2024, 5, 3, tzinfo=timezone.utc),
                ),
                Work(
                    id=4, title="Travesía", description="Paisaje de viaje y contemplación.",
                    year="2023", category="Landscape Paintings",
                    image_url="https://images.unsplash.com/photo-1561214115-f2f134cc4912?auto=format&fit=crop&w=700&q=85",
                    artist_id=4, gallery_id=3, available=False, price=800000,
                    created_at=datetime(2024, 5, 4, tzinfo=timezone.utc),
                ),
            ]
            db.executemany(
                """
                INSERT INTO works (
                    id, title, description, year, category, image_url, artist_id,
                    gallery_id, available, price, moderation_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        work.id, work.title, work.description, work.year, work.category,
                        work.image_url, work.artist_id, work.gallery_id, int(work.available),
                        work.price, work.moderation_status, work.created_at.isoformat(),
                    )
                    for work in seed
                ],
            )


def work_from_row(row: sqlite3.Row) -> Work:
    return Work(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        year=row["year"],
        category=row["category"],
        image_url=row["image_url"],
        artist_id=row["artist_id"],
        gallery_id=row["gallery_id"],
        available=bool(row["available"]),
        price=row["price"],
        moderation_status=row["moderation_status"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def update_values(payload: WorkInput) -> tuple[object, ...]:
    return (
        payload.title, payload.description, payload.year, payload.category,
        payload.image_url, payload.artist_id, payload.gallery_id, int(payload.available),
        payload.price, payload.moderation_status,
    )


init_db()


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "works", "status": "ok"}


@app.get("/api/works")
def list_works(
    q: str = Query(default=""),
    category: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=6, ge=1, le=50),
) -> dict[str, object]:
    with connection() as db:
        works = [work_from_row(row) for row in db.execute("SELECT * FROM works")]
    query = q.strip().lower()
    filtered = [
        work for work in works
        if (not query or query in f"{work.title} {work.description} {work.year}".lower())
        and (not category.strip() or work.category == category.strip())
    ]
    filtered.sort(key=lambda work: work.created_at, reverse=True)
    total = len(filtered)
    start = (page - 1) * limit
    return {
        "items": filtered[start:start + limit],
        "pagination": {
            "page": page,
            "limit": limit,
            "totalItems": total,
            "totalPages": max(1, (total + limit - 1) // limit),
        },
    }


@app.get("/api/works/{work_id}", response_model=Work)
def get_work(work_id: int) -> Work:
    with connection() as db:
        row = db.execute("SELECT * FROM works WHERE id = ?", (work_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Work not found")
    return work_from_row(row)


@app.post("/api/works", response_model=Work, status_code=status.HTTP_201_CREATED)
def create_work(payload: WorkInput) -> Work:
    created_at = datetime.now(timezone.utc)
    with connection() as db:
        cursor = db.execute(
            """
            INSERT INTO works (
                title, description, year, category, image_url, artist_id, gallery_id,
                available, price, moderation_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*update_values(payload), created_at.isoformat()),
        )
        work_id = cursor.lastrowid
    return Work(id=work_id, created_at=created_at, **payload.model_dump())


@app.put("/api/works/{work_id}", response_model=Work)
def update_work(work_id: int, payload: WorkInput) -> Work:
    with connection() as db:
        row = db.execute("SELECT created_at FROM works WHERE id = ?", (work_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Work not found")
        db.execute(
            """
            UPDATE works SET title = ?, description = ?, year = ?, category = ?,
                image_url = ?, artist_id = ?, gallery_id = ?, available = ?,
                price = ?, moderation_status = ?
            WHERE id = ?
            """,
            (*update_values(payload), work_id),
        )
        created_at = datetime.fromisoformat(row["created_at"])
    return Work(id=work_id, created_at=created_at, **payload.model_dump())


@app.delete("/api/works/{work_id}")
def delete_work(work_id: int) -> dict[str, bool]:
    with connection() as db:
        cursor = db.execute("DELETE FROM works WHERE id = ?", (work_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Work not found")
    return {"ok": True}


@app.patch("/api/works/{work_id}/moderation", response_model=Work)
def moderate_work(work_id: int, moderation_status: str = Query(..., pattern="^(draft|pending|published|rejected)$")) -> Work:
    with connection() as db:
        row = db.execute("SELECT * FROM works WHERE id = ?", (work_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Work not found")
        db.execute(
            "UPDATE works SET moderation_status = ? WHERE id = ?",
            (moderation_status, work_id),
        )
        row = db.execute("SELECT * FROM works WHERE id = ?", (work_id,)).fetchone()
    return work_from_row(row)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3002)
