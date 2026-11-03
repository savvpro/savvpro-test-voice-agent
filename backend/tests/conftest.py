import pytest
from brain.availability import reset_db

@pytest.fixture(autouse=True)
def clean_database():
    reset_db()
    yield
    reset_db()
