import os
import tempfile

# Must be set BEFORE importing the app so it uses an isolated DB and folder.
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["CERT_DIR"] = f"{_tmp}/certs"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    # TestClient runs BackgroundTasks before returning, so jobs are finished
    # by the time the POST call returns.
    with TestClient(app) as c:
        yield c


def make_recipient(name="Alice Johnson", email="alice@example.com", course="Cybersecurity 101"):
    return {"name": name, "email": email, "course": course}
