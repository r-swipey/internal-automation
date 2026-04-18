import os

# Must be set before any app imports so pydantic-settings finds them
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-anon-key")
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-chars-exactly!!")
os.environ.setdefault("SWIPEY_BP_API_KEY", "stub-test")
os.environ.setdefault("SWIPEY_API_URL", "https://api.swipey.app")
os.environ.setdefault("SWIPEY_COMPANY_UUID", "test-company-uuid")

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.core.auth import create_access_token


def make_mock_db(*results):
    """
    Returns a MagicMock Supabase client.
    All fluent query methods return self so chains work.
    db.execute() returns results in order from the queue.
    """
    db = MagicMock()
    for method in [
        "table", "select", "eq", "neq", "in_", "order",
        "like", "insert", "update", "delete", "upsert", "storage",
    ]:
        getattr(db, method).return_value = db

    queue = list(results)

    def execute():
        r = MagicMock()
        r.data = queue.pop(0) if queue else []
        return r

    db.execute.side_effect = execute
    return db


def admin_token():
    return create_access_token({"sub": "user-admin-001", "role": "admin", "name": "Admin"})


def manager_token():
    return create_access_token({"sub": "user-mgr-001", "role": "manager", "name": "Manager"})


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {admin_token()}"}
