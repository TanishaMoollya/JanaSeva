import os
os.environ["DATABASE_URL"] = "sqlite:///./test_janaseva.db"
os.environ["JWT_SECRET"] = "test-secret-that-is-not-used-outside-tests"

import pytest
from fastapi.testclient import TestClient
from app.db import Base, engine
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client


def account(client, name, email, password="test-password-123"):
    response = client.post("/api/auth/register", json={"name": name, "email": email, "password": password})
    assert response.status_code == 201
    login = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}
