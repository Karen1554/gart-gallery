"""Initialize and seed every microservice table in the configured PostgreSQL database."""

import importlib.util
from pathlib import Path
import sys

from psycopg import OperationalError


sys.path.insert(0, str(Path(__file__).resolve().parent))


SERVICES = (
    ("auth-service/app.py", ("auth_users", "auth_sessions")),
    ("gallery-service/app.py", ("gallery_galleries",)),
    ("works-service/app.py", ("works_works",)),
    ("purchase-service/app.py", ("purchase_carts", "purchase_purchases")),
    ("content-service/app.py", ("content_artists", "content_pages", "content_landing")),
)


def load_service(path: Path):
    module_name = f"gart_{path.parent.name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load service module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    root = Path(__file__).resolve().parent
    from db import connection

    try:
        with connection() as db:
            db.execute("SELECT 1")
        print("PostgreSQL connection verified.")

        for relative_path, expected_tables in SERVICES:
            service_path = root / relative_path
            service = load_service(service_path)
            service.init_db()
            with connection() as db:
                for table in expected_tables:
                    result = db.execute("SELECT to_regclass(%s) AS table_name", (table,)).fetchone()
                    if result["table_name"] is None:
                        raise RuntimeError(f"Table creation failed: {table}")
            print(f"{service_path.parent.name}: {', '.join(expected_tables)} ready")
    except OperationalError as error:
        raise SystemExit(
            "Could not connect to PostgreSQL. Set DATABASE_URL in the project-root .env "
            "file or environment, and confirm the database accepts connections."
        ) from error


if __name__ == "__main__":
    main()
