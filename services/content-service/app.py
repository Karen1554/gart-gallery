import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import connection
from psycopg.types.json import Json

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(title="Gart Gallery Content Service", version="1.0.0")


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




def init_db() -> None:
    with connection() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS content_artists (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                biography TEXT NOT NULL DEFAULT '',
                image_url TEXT,
                active BOOLEAN NOT NULL DEFAULT TRUE
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS content_pages (
                slug TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                published BOOLEAN NOT NULL DEFAULT TRUE
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS content_landing (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                title TEXT NOT NULL,
                subtitle TEXT NOT NULL DEFAULT '',
                hero_image_url TEXT,
                featured_work_ids JSONB NOT NULL DEFAULT '[]'::jsonb
            )
            """
        )
        if db.execute("SELECT COUNT(*) AS count FROM content_artists").fetchone()["count"] == 0:
            db.executemany(
                """
                INSERT INTO content_artists (id, name, biography, image_url, active)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [
                    (1, "Laura Méndez", "Pinta paisajes de memoria y territorio.", None, True),
                    (2, "Carlos Pérez", "Explora el color desde la abstracción.", None, True),
                    (3, "Ana Torres", "Crea composiciones llenas de luz.", None, True),
                    (4, "Miguel Ángel", "Retrata viajes, montañas y horizontes.", None, True),
                ],
            )
            db.execute(
                "SELECT setval(pg_get_serial_sequence('content_artists', 'id'), "
                "COALESCE(MAX(id), 1), true) FROM content_artists"
            )
        if db.execute("SELECT COUNT(*) AS count FROM content_pages").fetchone()["count"] == 0:
            db.executemany(
                "INSERT INTO content_pages (slug, title, body, published) VALUES (%s, %s, %s, TRUE)",
                [
                    ("about", "Sobre GART Gallery", "Un espacio para descubrir arte, artistas y galerías."),
                    ("contact", "Contacto", "Escríbenos para conocer nuestras obras y exposiciones."),
                ],
            )
        if db.execute("SELECT COUNT(*) AS count FROM content_landing").fetchone()["count"] == 0:
            db.execute(
                """
                INSERT INTO content_landing (id, title, subtitle, hero_image_url, featured_work_ids)
                VALUES (1, %s, %s, %s, %s)
                """,
                (
                    "Arte que inspira, espacios que conectan.",
                    "Descubre obras únicas de artistas increíbles en nuestras galerías.",
                    None,
                    Json([1, 2, 3, 4]),
                ),
            )


def artist_from_row(row: dict) -> Artist:
    return Artist(
        id=row["id"],
        name=row["name"],
        biography=row["biography"],
        image_url=row["image_url"],
        active=row["active"],
    )


def page_from_row(row: dict) -> ContentPage:
    return ContentPage(
        slug=row["slug"],
        title=row["title"],
        body=row["body"],
        published=row["published"],
    )


def landing_from_row(row: dict) -> LandingContent:
    return LandingContent(
        title=row["title"],
        subtitle=row["subtitle"],
        hero_image_url=row["hero_image_url"],
        featured_work_ids=row["featured_work_ids"],
    )


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "content", "status": "ok"}


@app.get("/api/content")
def content() -> dict[str, object]:
    with connection() as db:
        landing = landing_from_row(db.execute("SELECT * FROM content_landing WHERE id = 1").fetchone())
        pages = [page_from_row(row) for row in db.execute("SELECT * FROM content_pages ORDER BY slug")]
        artists = [artist_from_row(row) for row in db.execute("SELECT * FROM content_artists ORDER BY id")]
    return {"landing": landing, "pages": pages, "artists": artists}


@app.get("/api/content/landing", response_model=LandingContent)
def get_landing() -> LandingContent:
    with connection() as db:
        row = db.execute("SELECT * FROM content_landing WHERE id = 1").fetchone()
    return landing_from_row(row)


@app.get("/api/content/pages/{slug}", response_model=ContentPage)
def get_page(slug: str) -> ContentPage:
    with connection() as db:
        row = db.execute("SELECT * FROM content_pages WHERE slug = %s", (slug,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Content page not found")
    return page_from_row(row)


@app.post("/api/content/pages", response_model=ContentPage, status_code=201)
def create_page(payload: ContentPageInput) -> ContentPage:
    page = ContentPage(**payload.model_dump())
    with connection() as db:
        db.execute(
            """
            INSERT INTO content_pages (slug, title, body, published)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT(slug) DO UPDATE SET
                title = excluded.title, body = excluded.body, published = excluded.published
            """,
            (page.slug, page.title, page.body, page.published),
        )
    return page


@app.get("/api/artists")
def list_artists() -> dict[str, list[Artist]]:
    with connection() as db:
        artists = [artist_from_row(row) for row in db.execute("SELECT * FROM content_artists ORDER BY id")]
    return {"items": artists}


@app.get("/api/artists/{artist_id}", response_model=Artist)
def get_artist(artist_id: int) -> Artist:
    with connection() as db:
        row = db.execute("SELECT * FROM content_artists WHERE id = %s", (artist_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Artist not found")
    return artist_from_row(row)


@app.post("/api/artists", response_model=Artist, status_code=201)
def create_artist(payload: ArtistInput) -> Artist:
    with connection() as db:
        cursor = db.execute(
            "INSERT INTO content_artists (name, biography, image_url, active) VALUES (%s, %s, %s, %s) RETURNING id",
            (payload.name, payload.biography, payload.image_url, payload.active),
        )
        artist_id = cursor.fetchone()["id"]
    return Artist(id=artist_id, **payload.model_dump())


@app.put("/api/artists/{artist_id}", response_model=Artist)
def update_artist(artist_id: int, payload: ArtistInput) -> Artist:
    with connection() as db:
        if db.execute("SELECT 1 FROM content_artists WHERE id = %s", (artist_id,)).fetchone() is None:
            raise HTTPException(status_code=404, detail="Artist not found")
        db.execute(
            """
            UPDATE content_artists SET name = %s, biography = %s, image_url = %s, active = %s
            WHERE id = %s
            """,
            (payload.name, payload.biography, payload.image_url, payload.active, artist_id),
        )
    return Artist(id=artist_id, **payload.model_dump())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3005)
