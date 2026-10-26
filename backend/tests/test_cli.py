import json

import pytest
from sqlalchemy import func, select

from lost_property.cli import main
from lost_property.persistence.database import Database
from lost_property.persistence.models import ItemRow


def test_migrate_and_seed_are_explicit_and_idempotent(tmp_path):
    url = f"sqlite:///{(tmp_path / 'cli.db').as_posix()}"
    assert main(["--database-url", url, "migrate"]) == 0
    args = ["--database-url", url, "seed", "--demo", "--as-of", "2026-10-26"]
    assert main(args) == 0
    assert main(args) == 0
    db = Database(url)
    with db.sessions() as session:
        assert session.scalar(select(func.count()).select_from(ItemRow)) == 24
    db.engine.dispose()


def test_seed_requires_explicit_demo_flag(tmp_path):
    with pytest.raises(SystemExit) as error:
        main(["seed"])
    assert error.value.code == 2


def test_openapi_export_contains_public_contract_only(tmp_path):
    path = tmp_path / "openapi.json"
    assert main(["export-openapi", "--output", str(path)]) == 0
    data = json.loads(path.read_text())
    assert "/api/v1/turns" in data["paths"]
    assert "private_facts" not in path.read_text()
