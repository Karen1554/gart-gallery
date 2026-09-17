import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(title="Gart Gallery Content Service", version="1.0.0")
DB_PATH = os.getenv(
    "DB_PATH",
    str(Path(__file__).resolve().parent / "data" / "content.db"),
)


class Artist(BaseModel):
    id: int
    name: str
    biography: str = ""
    image_url: str | None = None
    active: bool = True


class ArtistInput(BaseModel):
    name: str = Field(min_length=1)
    biography: str = ""
    image_url: str | None = None
    active: bool = True


class ContentPage(BaseModel):
    slug: str
    title: str
    body: str
    published: bool = True


class LandingContent(BaseModel):
    title: str
    subtitle: str = ""
    hero_image_url: str | None = None
    featured_work_ids: list[int] = Field(default_factory=list)


class ContentPageInput(BaseModel):
    slug: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body: str
    published: bool = True


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
            CREATE TABLE IF NOT EXISTS artists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                biography TEXT NOT NULL DEFAULT '',
                image_url TEXT,
                active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS pages (
                slug TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                published INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS landing (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                title TEXT NOT NULL,
                subtitle TEXT NOT NULL DEFAULT '',
                hero_image_url TEXT,
                featured_work_ids TEXT NOT NULL
            )
            """
        )
        if db.execute("SELECT COUNT(*) FROM artists").fetchone()[0] == 0:
            db.executemany(
                """
                INSERT INTO artists (id, name, biography, image_url, active)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (1, "Laura Méndez", "Pinta paisajes de memoria y territorio.", None, 1),
                    (2, "Carlos Pérez", "Explora el color desde la abstracción.", None, 1),
                    (3, "Ana Torres", "Crea composiciones llenas de luz.", None, 1),
                    (4, "Miguel Ángel", "Retrata viajes, montañas y horizontes.", None, 1),
                ],
            )
        if db.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == 0:
            db.executemany(
                "INSERT INTO pages (slug, title, body, published) VALUES (?, ?, ?, 1)",
                [
                    ("about", "Sobre GART Gallery", "Un espacio para descubrir arte, artistas y galerías."),
                    ("contact", "Contacto", "Escríbenos para conocer nuestras obras y exposiciones."),
                ],
            )
        if db.execute("SELECT COUNT(*) FROM landing").fetchone()[0] == 0:
            db.execute(
                """
                INSERT INTO landing (id, title, subtitle, hero_image_url, featured_work_ids)
                VALUES (1, ?, ?, ?, ?)
                """,
                (
                    "Arte que inspira, espacios que conectan.",
                    "Descubre obras únicas de artistas increíbles en nuestras galerías.",
                    None,
                    json.dumps([1, 2, 3, 4]),
                ),
            )


def artist_from_row(row: sqlite3.Row) -> Artist:
    return Artist(
        id=row["id"],
        name=row["name"],
        biography=row["biography"],
        image_url=row["image_url"],
        active=bool(row["active"]),
    )


def page_from_row(row: sqlite3.Row) -> ContentPage:
    return ContentPage(
        slug=row["slug"],
        title=row["title"],
        body=row["body"],
        published=bool(row["published"]),
    )


def landing_from_row(row: sqlite3.Row) -> LandingContent:
    return LandingContent(
        title=row["title"],
        subtitle=row["subtitle"],
        hero_image_url=row["hero_image_url"],
        featured_work_ids=json.loads(row["featured_work_ids"]),
    )


init_db()


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "content", "status": "ok"}


@app.get("/api/content")
def content() -> dict[str, object]:
    with connection() as db:
        landing = landing_from_row(db.execute("SELECT * FROM landing WHERE id = 1").fetchone())
        pages = [page_from_row(row) for row in db.execute("SELECT * FROM pages ORDER BY rowid")]
        artists = [artist_from_row(row) for row in db.execute("SELECT * FROM artists ORDER BY id")]
    return {"landing": landing, "pages": pages, "artists": artists}


@app.get("/api/content/landing", response_model=LandingContent)
def get_landing() -> LandingContent:
    with connection() as db:
        row = db.execute("SELECT * FROM landing WHERE id = 1").fetchone()
    return landing_from_row(row)


@app.get("/api/content/pages/{slug}", response_model=ContentPage)
def get_page(slug: str) -> ContentPage:
    with connection() as db:
        row = db.execute("SELECT * FROM pages WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Content page not found")
    return page_from_row(row)


@app.post("/api/content/pages", response_model=ContentPage, status_code=201)
def create_page(payload: ContentPageInput) -> ContentPage:
    page = ContentPage(**payload.model_dump())
    with connection() as db:
        db.execute(
            """
            INSERT INTO pages (slug, title, body, published)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                title = excluded.title, body = excluded.body, published = excluded.published
            """,
            (page.slug, page.title, page.body, int(page.published)),
        )
    return page


@app.get("/api/artists")
def list_artists() -> dict[str, list[Artist]]:
    with connection() as db:
        artists = [artist_from_row(row) for row in db.execute("SELECT * FROM artists ORDER BY id")]
    return {"items": artists}


@app.get("/api/artists/{artist_id}", response_model=Artist)
def get_artist(artist_id: int) -> Artist:
    with connection() as db:
        row = db.execute("SELECT * FROM artists WHERE id = ?", (artist_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Artist not found")
    return artist_from_row(row)


@app.post("/api/artists", response_model=Artist, status_code=201)
def create_artist(payload: ArtistInput) -> Artist:
    with connection() as db:
        cursor = db.execute(
            "INSERT INTO artists (name, biography, image_url, active) VALUES (?, ?, ?, ?)",
            (payload.name, payload.biography, payload.image_url, int(payload.active)),
        )
        artist_id = cursor.lastrowid
    return Artist(id=artist_id, **payload.model_dump())


@app.put("/api/artists/{artist_id}", response_model=Artist)
def update_artist(artist_id: int, payload: ArtistInput) -> Artist:
    with connection() as db:
        if db.execute("SELECT 1 FROM artists WHERE id = ?", (artist_id,)).fetchone() is None:
            raise HTTPException(status_code=404, detail="Artist not found")
        db.execute(
            """
            UPDATE artists SET name = ?, biography = ?, image_url = ?, active = ?
            WHERE id = ?
            """,
            (payload.name, payload.biography, payload.image_url, int(payload.active), artist_id),
        )
    return Artist(id=artist_id, **payload.model_dump())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3005)
