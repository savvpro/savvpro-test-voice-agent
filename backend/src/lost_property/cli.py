import argparse
import json
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

from lost_property.config import Settings
from lost_property.main import create_app, utcnow
from lost_property.persistence.database import Database
from lost_property.persistence.fixtures import demo_items


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Riverside setup and maintenance")
    parser.add_argument("--database-url", default=Settings().database_url)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="Apply versioned database migrations")
    seed = commands.add_parser(
        "seed", help="Insert fictional demo inventory without overwriting data"
    )
    seed.add_argument("--demo", action="store_true", required=True)
    seed.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=utcnow().astimezone(ZoneInfo("Asia/Karachi")).date(),
    )
    commands.add_parser("cleanup", help="Remove expired conversations and cases")
    export = commands.add_parser("export-openapi", help="Write the public API contract")
    export.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "export-openapi":
        schema = create_app(Settings(database_url=args.database_url)).openapi()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print("Exported the public API contract.")
        return 0
    db = Database(args.database_url)
    try:
        if args.command == "migrate":
            db.migrate()
            print("Database migrations applied.")
        elif args.command == "seed":
            print(f"Inserted {db.seed(demo_items(args.as_of))} fictional items.")
        else:
            chats, cases = db.cleanup(utcnow().timestamp())
            print(f"Removed {chats} expired conversations and {cases} expired cases.")
    finally:
        db.engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
