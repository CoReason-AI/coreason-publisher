import pytest
from coreason_identity.models import UserContext


@pytest.fixture
def mock_user_context() -> UserContext:
    return UserContext(
        user_id="test_user",
        email="test@coreason.ai",
        groups=["SRE", "SRB"],
        scopes=["*"],
        claims={"sub": "test_user"},
        downstream_token="fake-token",
    )
