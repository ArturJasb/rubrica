import os
import tempfile

# Banco SQLite temporário e configurações falsas ANTES de importar a aplicação
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ["SUPABASE_URL"] = "https://fake.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "anon"
os.environ["RECALL_API_KEY"] = "recall-test"
os.environ["LLM_API_KEY"] = "llm-test"
os.environ["WEBHOOK_TOKEN"] = "segredo"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import auth  # noqa: E402
from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

USERS = {
    "tok-ana": auth.AuthUser(id="u-ana", email="ana@empresa.com", name="Ana"),
    "tok-bia": auth.AuthUser(id="u-bia", email="bia@empresa.com", name="Bia"),
    "tok-caio": auth.AuthUser(id="u-caio", email="caio@outra.com", name="Caio"),
}


def fake_verify(token: str):
    if token not in USERS:
        from fastapi import HTTPException
        raise HTTPException(401, "inválido")
    return USERS[token]


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(auth, "verify_token", fake_verify)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
