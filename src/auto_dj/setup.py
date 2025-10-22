"""Installation helper CLI to bootstrap the Auto-DJ stack."""
from __future__ import annotations

import argparse
import os
import sys
from getpass import getpass

from psycopg import connect, sql
from sqlalchemy.engine import make_url

from .config import AutoDjConfig, load_config
from .database.session import Database
from .services.admin import AdminService


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Auto-DJ installer")
    parser.add_argument(
        "--ensure-admin",
        action="store_true",
        help="Ensure admin accounts from the config exist (default password Admin123).",
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Create database tables if they do not exist.",
    )
    parser.add_argument(
        "--ensure-database",
        action="store_true",
        help="Ensure the PostgreSQL role and database referenced by the config exist.",
    )
    parser.add_argument(
        "--database-superuser-dsn",
        default=None,
        help=(
            "Optional PostgreSQL superuser DSN to manage roles/databases. "
            "Defaults to postgres://postgres@<host>/postgres if omitted. "
            "Can also be supplied via AUTO_DJ_SUPERUSER_DSN."
        ),
    )
    return parser.parse_args(argv)


def ensure_database(config: AutoDjConfig, superuser_dsn: str | None) -> None:
    """Ensure the configured PostgreSQL role and database exist."""

    target_url = make_url(config.database.dsn)
    base_driver = target_url.drivername.split("+", 1)[0]
    target_url = target_url.set(drivername=base_driver)

    if target_url.username is None or target_url.database is None:
        raise RuntimeError("Database DSN must include username and database components")

    user = target_url.username
    role_password = target_url.password or ""
    database_name = target_url.database

    host = target_url.host or "localhost"
    port = target_url.port or 5432

    env_superuser = os.environ.get("AUTO_DJ_SUPERUSER_DSN")
    default_superuser = f"{base_driver}://postgres@{host}:{port}/postgres"
    super_url = make_url(superuser_dsn or env_superuser or default_superuser)
    super_driver = super_url.drivername.split("+", 1)[0]
    super_url = super_url.set(drivername=super_driver)

    if super_url.password is None:
        env_password = os.environ.get("AUTO_DJ_SUPERUSER_PASSWORD")
        super_password: str | None = env_password
        if not super_password and sys.stdin.isatty():
            try:
                prompt_user = super_url.username or "postgres"
                prompt_host = super_url.host or host
                prompt_port = super_url.port or port
                super_password = getpass(
                    f"PostgreSQL password for {prompt_user}@{prompt_host}:{prompt_port} (leave blank to try without): "
                )
            except (EOFError, KeyboardInterrupt):
                super_password = ""
        if super_password:
            super_url = super_url.set(password=super_password)

    superuser_dsn_rendered = super_url.render_as_string(hide_password=False)
    target_dsn_display = target_url.render_as_string(hide_password=True)

    print(f"Ensuring PostgreSQL role '{user}' and database '{database_name}' for {target_dsn_display}")

    try:
        with connect(superuser_dsn_rendered) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (user,))
                if cur.fetchone() is None:
                    cur.execute(
                        sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                            sql.Identifier(user), sql.Literal(role_password)
                        )
                    )
                    print(f"Created role '{user}'")
                else:
                    cur.execute(
                        sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                            sql.Identifier(user), sql.Literal(role_password)
                        )
                    )
                    print(f"Updated password for role '{user}'")

                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database_name,))
                if cur.fetchone() is None:
                    cur.execute(
                        sql.SQL("CREATE DATABASE {} OWNER {}").format(
                            sql.Identifier(database_name), sql.Identifier(user)
                        )
                    )
                    print(f"Created database '{database_name}' owned by '{user}'")
                else:
                    cur.execute(
                        sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
                            sql.Identifier(database_name), sql.Identifier(user)
                        )
                    )
                    print(f"Ensured database '{database_name}' is owned by '{user}'")
    except Exception as exc:  # pragma: no cover - runtime safety
        raise RuntimeError(
            "Failed to ensure PostgreSQL role/database. Set AUTO_DJ_SUPERUSER_DSN or "
            "check superuser credentials"
        ) from exc


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config()

    database = Database(config.database)

    if args.ensure_database:
        ensure_database(config, args.database_superuser_dsn)

    if args.init_db:
        database.create_all()
        print("Database schema ready")

    if args.ensure_admin:
        admin_service = AdminService(database, config)
        admin_service.ensure_seed_accounts()
        print("Admin accounts ensured (default password Admin123)")

    if not any([args.ensure_database, args.init_db, args.ensure_admin]):
        print("Nothing to do. Use --ensure-database, --init-db and/or --ensure-admin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
