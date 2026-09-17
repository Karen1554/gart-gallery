# Gart Gallery microservices

Each service is an independent FastAPI application. The API gateway is the
only public entry point and routes requests by domain. Services own their
domain data and must communicate through APIs rather than reading another
service's database directly.

| Service | Port | Responsibility |
| --- | ---: | --- |
| Gallery | 3001 | Galleries and artist-gallery relationships |
| Works | 3002 | Works, images, availability, prices, and artist/work relationships |
| Auth | 3003 | Users, roles, permissions, login, sessions, and logout |
| Purchase | 3004 | Cart, purchase orders, totals, status, and sales |
| Content | 3005 | Landing page, web pages, artists, and public content |

## API contracts

Every service exposes `GET /health`.

* Auth: `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout`.
* Gallery: `GET/POST /api/galleries`, `GET /api/galleries/{id}`.
* Works: `GET/POST /api/works`, `GET /api/works/{id}`,
  `DELETE /api/works/{id}`. Listing supports `q`, `category`, `page`, and
  `limit` and retains the existing pagination response.
* Purchase: `GET/PUT /api/cart/{user_id}`, `GET/POST /api/purchases`,
  `GET /api/purchases/{id}`.
* Content: `GET /api/content`, `GET /api/content/landing`,
  `GET/POST /api/content/pages`, and `GET /api/artists`.

## Database ownership and configuration

All services use the PostgreSQL database in `DATABASE_URL`; no service reads
another service's tables. Each service creates and seeds only its own tables:

| Service | PostgreSQL tables |
| --- | --- |
| Gallery | `gallery_galleries` |
| Works | `works_works` |
| Auth | `auth_users`, `auth_sessions` |
| Purchase | `purchase_carts`, `purchase_purchases` |
| Content | `content_artists`, `content_pages`, `content_landing` |

Set `DATABASE_URL` for every service. `ENVIRONMENT=production` fails clearly
when it is missing. For local development only, the helper uses the explicit
PostgreSQL default `postgresql://postgres:postgres@localhost:5432/gart_gallery`;
start that PostgreSQL database first. The schemas and seed records are
initialized on startup, and seed data is inserted only when its table is empty.
JSON list fields are stored as PostgreSQL `JSONB`. Auth stores users and active
bearer sessions, so data, carts, purchases, and sessions survive restarts.

## Local setup

Create a virtual environment and install the shared dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r services\requirements.txt
```

Copy `.env.example` to `.env` and set `DATABASE_URL` to your local PostgreSQL
connection string (or use the documented development default).

Run a service from the repository root:

```powershell
python services\auth-service\app.py
```

The gateway can then route to the service on its configured port.
