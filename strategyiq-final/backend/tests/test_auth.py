"""Auth endpoint tests."""

from db.auth import hash_password, verify_password


def test_password_hash_roundtrip():
    hashed = hash_password("testpassword123")
    assert verify_password("testpassword123", hashed)
    assert not verify_password("wrongpassword", hashed)


def test_auth_router_exists():
    from routers.auth import router

    paths = [route.path for route in router.routes]
    assert "/auth/register" in paths or "/register" in [p.split("/")[-1] for p in paths]
