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

### Docker Compose

Docker Compose starts PostgreSQL, the five FastAPI services, and the Astro
site/API gateway. From the repository root, copy `.env.example` to `.env`,
replace `ADMIN_PASSWORD` and `POSTGRES_PASSWORD` with local development
passwords using URL-safe characters, then run:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open `http://localhost:3000`. The gateway waits until PostgreSQL and all
microservices pass their health checks. PostgreSQL is also available on
`localhost:5432` by default; configure `POSTGRES_PORT` if that port is already
in use.

Stop the stack with `docker compose down`. The named `postgres_data` volume
keeps database contents across restarts; `docker compose down -v` removes that
volume and permanently deletes the local database.

### Running services without Docker

Create a virtual environment and install the shared dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r services\requirements.txt
```

Copy `.env.example` to `.env` and set `DATABASE_URL` to your local PostgreSQL
connection string (or use the documented development default). The database
helper loads this root `.env` automatically for local commands.

Run a service from the repository root:

```powershell
python services\auth-service\app.py
```

Initialize all service tables and seed records explicitly:

```powershell
python services\init_db.py
```

Or from npm:

```powershell
npm run db:init
```

The command uses the same `DATABASE_URL` as the services and is safe to run
again because each service creates missing tables and seeds only empty tables.
It verifies the PostgreSQL connection and confirms every expected table exists.

The gateway can then route to the service on its configured port.

## Render deployment

The root Render web service builds Astro into `dist` and serves the static
pages and API gateway from one public URL. Set each microservice URL in the
gateway environment variables configured in `render.yaml`; the browser uses
same-origin `/api/...` routes in production. Render supplies `PORT` to each
web service, and every Python service initializes its own tables on startup.
