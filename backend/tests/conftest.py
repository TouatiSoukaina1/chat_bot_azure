from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import get_current_user
import logging

logging.getLogger("azure").setLevel(logging.CRITICAL)
logging.getLogger("azure").propagate = False
logging.getLogger("azure.cosmos").setLevel(logging.CRITICAL)
logging.getLogger("azure.cosmos").propagate = False
logging.getLogger("azure.core.pipeline").setLevel(logging.CRITICAL)
logging.getLogger("azure.core.pipeline").propagate = False
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.CRITICAL)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").propagate = False

class FakeUser:
    user_id = "tenant123:user123"
    oid = "user123"
    tid = "tenant123"
    display_name = "Soukaina"
    preferred_username = "soukaina@example.com"
    raw_claims = {}


def fake_current_user():
    return FakeUser()


app.dependency_overrides[get_current_user] = fake_current_user


def get_test_client():
    return TestClient(app)