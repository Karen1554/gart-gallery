import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import connection
from psycopg.types.json import Json

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(title="Gart Gallery Gallery Service", version="1.0.0")


class Gallery(BaseModel):
    id: int
    name: str
    description: str = ""
    address: str = ""
    city: str = ""
    country: str = ""
    website: str | None = None
    phone: str = ""
    email: str = ""
    image_url: str | None = None
    additional_images: list[str] = Field(default_factory=list)
    artist_ids: list[int] = Field(default_factory=list)
    active: bool = True


class GalleryInput(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    address: str = ""
    city: str = ""
    country: str = ""
    website: str | None = None
    phone: str = ""
    email: str = ""
    image_url: str | None = None
    additional_images: list[str] = Field(default_factory=list)
    artist_ids: list[int] = Field(default_factory=list)
    active: bool = True




def init_db() -> None:
    with connection() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS gallery_galleries (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                address TEXT NOT NULL DEFAULT '',
                city TEXT NOT NULL DEFAULT '',
                country TEXT NOT NULL DEFAULT '',
                website TEXT,
                phone TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                image_url TEXT,
                additional_images JSONB NOT NULL DEFAULT '[]'::jsonb,
                artist_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
                active BOOLEAN NOT NULL DEFAULT TRUE
            )
            """
        )
        if db.execute("SELECT COUNT(*) AS count FROM gallery_galleries").fetchone()["count"] == 0:
            seed = [
                Gallery(
                    id=1, name="GART Gallery", description="Arte contemporáneo colombiano.",
                    address="Carrera 7 # 72-41", city="Bogotá", country="Colombia",
                    phone="+57 601 555 0101", email="hola@gartgallery.co",
                    website="https://gartgallery.co", artist_ids=[1, 3],
                    image_url="https://images.unsplash.com/photo-1561214115-f2f134cc4912?auto=format&fit=crop&w=1200&q=85",
                ),
                Gallery(
                    id=2, name="Galería Horizonte", description="Nuevas miradas y territorios.",
                    address="Carrera 37 # 10-28", city="Medellín", country="Colombia",
                    phone="+57 604 555 0102", email="contacto@horizonte.co", artist_ids=[2],
                    image_url="https://images.unsplash.com/photo-1577083552431-6e5fd01aa342?auto=format&fit=crop&w=1200&q=85",
                ),
                Gallery(
                    id=3, name="Arte Vivo", description="Espacio para artistas emergentes.",
                    address="Calle 5 # 4-18", city="Cali", country="Colombia",
                    phone="+57 602 555 0103", email="hola@artevivo.co", artist_ids=[4],
                    image_url="https://images.unsplash.com/photo-1577083288073-40892c0860a4?auto=format&fit=crop&w=1200&q=85",
                ),
                Gallery(
                    id=4, name="Espacio Creativo", description="Exposiciones y encuentros.",
                    address="Carrera 53 # 76-12", city="Barranquilla", country="Colombia",
                    phone="+57 605 555 0104", email="info@espaciocreativo.co", artist_ids=[],
                    image_url="https://images.unsplash.com/photo-1594784051650-5a5e8e8a0c6f?auto=format&fit=crop&w=1200&q=85",
                ),
            ]
            db.executemany(
                """
                INSERT INTO gallery_galleries (
                    id, name, description, address, city, country, website, phone,
                    email, image_url, additional_images, artist_ids, active
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        gallery.id, gallery.name, gallery.description, gallery.address,
                        gallery.city, gallery.country, gallery.website, gallery.phone,
                        gallery.email, gallery.image_url, Json(gallery.additional_images),
                        Json(gallery.artist_ids), gallery.active,
                    )
                    for gallery in seed
                ],
            )
            db.execute(
                "SELECT setval(pg_get_serial_sequence('gallery_galleries', 'id'), "
                "COALESCE(MAX(id), 1), true) FROM gallery_galleries"
            )


def gallery_from_row(row: dict) -> Gallery:
    return Gallery(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        address=row["address"],
        city=row["city"],
        country=row["country"],
        website=row["website"],
        phone=row["phone"],
        email=row["email"],
        image_url=row["image_url"],
        additional_images=row["additional_images"],
        artist_ids=row["artist_ids"],
        active=row["active"],
    )


def save_gallery(db, gallery_id: int, payload: GalleryInput) -> None:
    db.execute(
        """
        UPDATE gallery_galleries SET name = %s, description = %s, address = %s, city = %s,
            country = %s, website = %s, phone = %s, email = %s, image_url = %s,
            additional_images = %s, artist_ids = %s, active = %s
        WHERE id = %s
        """,
        (
            payload.name, payload.description, payload.address, payload.city,
            payload.country, payload.website, payload.phone, payload.email,
            payload.image_url, Json(payload.additional_images),
            Json(payload.artist_ids), payload.active, gallery_id,
        ),
    )


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "gallery", "status": "ok"}


@app.get("/api/galleries")
def list_galleries() -> dict[str, list[Gallery]]:
    with connection() as db:
        galleries = [gallery_from_row(row) for row in db.execute("SELECT * FROM gallery_galleries ORDER BY id")]
    return {"items": galleries}


@app.get("/api/galleries/{gallery_id}", response_model=Gallery)
def get_gallery(gallery_id: int) -> Gallery:
    with connection() as db:
        row = db.execute("SELECT * FROM gallery_galleries WHERE id = %s", (gallery_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Gallery not found")
    return gallery_from_row(row)


@app.post("/api/galleries", response_model=Gallery, status_code=201)
def create_gallery(payload: GalleryInput) -> Gallery:
    with connection() as db:
        cursor = db.execute(
            """
            INSERT INTO gallery_galleries (
                name, description, address, city, country, website, phone, email,
                image_url, additional_images, artist_ids, active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                payload.name, payload.description, payload.address, payload.city,
                payload.country, payload.website, payload.phone, payload.email,
                payload.image_url, Json(payload.additional_images),
                Json(payload.artist_ids), payload.active,
            ),
        )
        gallery_id = cursor.fetchone()["id"]
    return Gallery(id=gallery_id, **payload.model_dump())


@app.put("/api/galleries/{gallery_id}", response_model=Gallery)
def update_gallery(gallery_id: int, payload: GalleryInput) -> Gallery:
    with connection() as db:
        if db.execute("SELECT 1 FROM gallery_galleries WHERE id = %s", (gallery_id,)).fetchone() is None:
            raise HTTPException(status_code=404, detail="Gallery not found")
        save_gallery(db, gallery_id, payload)
    return Gallery(id=gallery_id, **payload.model_dump())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3001)
