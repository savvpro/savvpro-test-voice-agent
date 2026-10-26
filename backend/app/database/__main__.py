"""Explicit database initialization: python -m app.database [--path FILE]."""

import argparse

from app.database import DEFAULT_DATABASE_PATH, ReservationStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the fictional restaurant database.")
    parser.add_argument("--path", default=str(DEFAULT_DATABASE_PATH))
    args = parser.parse_args()
    store = ReservationStore(args.path)
    store.initialize_database()
    print(f"Initialized reservation database: {store.database_path.resolve()}")


if __name__ == "__main__":
    main()
