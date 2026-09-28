import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import Container
from app.core.security import sign_session
from app.main import create_app
from tests.support.db import SingleConnection
from tests.support.fakes import FakeCompleter, fake_jev
from tests.support.seed import embedder

SECRET = b"test-secret"


@pytest.fixture(scope="module")
def api(db):
    return TestClient(create_app(Container(SingleConnection(db), embedder, FakeCompleter(), fake_jev(), SECRET)))


def auth(ws: str) -> dict:
    return {"Authorization": "Bearer " + sign_session(ws, SECRET)}
