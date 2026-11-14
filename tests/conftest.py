import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import engine
from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:  # runs lifespan -> schema + seed data
        yield c


@pytest.fixture(autouse=True)
def clean_reservations(client):
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE reservations RESTART IDENTITY"))
    yield
