import os
from pathlib import Path


TEST_ROOT = Path(__file__).parent / ".runtime"
TEST_ROOT.mkdir(exist_ok=True)
os.environ["MONO_DATABASE_URL"] = f"sqlite:///{TEST_ROOT / 'test.db'}"
os.environ["MONO_ARTIFACT_PATH"] = str(TEST_ROOT / "artifacts")
os.environ["MONO_SEED_DEMO"] = "true"
os.environ["MONO_DEV"] = "true"
os.environ["MONO_DEMO"] = "false"


import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from mono_api.database import Base, engine  # noqa: E402
from mono_api.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as client:
        yield client
