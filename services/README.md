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

Each service owns an independent SQLite database and never reads another
service's database directly. By default the files are created under the
service's `data` directory:

| Service | Default database |
| --- | --- |
| Gallery | `services/gallery-service/data/gallery.db` |
| Works | `services/works-service/data/works.db` |
| Auth | `services/auth-service/data/auth.db` |
| Purchase | `services/purchase-service/data/purchase.db` |
| Content | `services/content-service/data/content.db` |

Set `DB_PATH` to override the database location for an individual service.
The schemas and seed records are initialized on startup, and seed data is
inserted only when its table is empty. Lists are stored as JSON and timestamps
as ISO strings. Auth also stores users and active bearer sessions, so data,
cart contents, purchases, and login sessions survive service restarts.

## Local setup

Create a virtual environment and install the shared dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r services\requirements.txt
```

Run a service from the repository root:

```powershell
python services\auth-service\app.py
```

The gateway can then route to the service on its configured port.
