"""Installation helper CLI to bootstrap the Auto-DJ stack."""
from __future__ import annotations

import argparse
import sys

from .config import AutoDjConfig
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = AutoDjConfig()
    database = Database(config.database)

    if args.init_db:
        database.create_all()
        print("Database schema ready")

    if args.ensure_admin:
        admin_service = AdminService(database, config)
        admin_service.ensure_seed_accounts()
        print("Admin accounts ensured (default password Admin123)")

    if not args.init_db and not args.ensure_admin:
        print("Nothing to do. Use --init-db and/or --ensure-admin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
