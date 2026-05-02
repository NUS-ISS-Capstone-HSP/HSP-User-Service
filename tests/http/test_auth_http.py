from fastapi.testclient import TestClient

from hsp_user_service.repository.in_memory import InMemoryEchoRepository, InMemoryUserRepository
from hsp_user_service.service.auth_service import AuthService
from hsp_user_service.service.echo_service import EchoService
from hsp_user_service.transport.http.app import create_http_app


def build_client() -> TestClient:
    echo_service = EchoService(InMemoryEchoRepository())
    auth_service = AuthService(
        repository=InMemoryUserRepository(),
        jwt_secret="test-secret-key-with-32-bytes-minimum!!",
        jwt_issuer="hsp-user-service",
        jwt_audience="hsp-api",
        access_token_ttl_seconds=900,
    )
    app = create_http_app(echo_service, auth_service)
    return TestClient(app)


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_worker_success() -> None:
    client = build_client()

    response = client.post(
        "/api/users/v1/auth/register",
        json={
            "email": "worker@example.com",
            "password": "password123",
            "role": "WORKER",
            "worker_display_name": "worker-one",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["user"]["email"] == "worker@example.com"
    assert payload["user"]["worker_profile"] is not None
    assert payload["user"]["worker_profile"]["employment_status"] == "ON_DUTY"


def test_login_me_logout_success() -> None:
    client = build_client()
    client.post(
        "/api/users/v1/auth/register",
        json={
            "email": "cs@example.com",
            "password": "password123",
            "role": "CUSTOMER_SERVICE",
        },
    )

    login_resp = client.post(
        "/api/users/v1/auth/login",
        json={"email": "cs@example.com", "password": "password123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    me_resp = client.get("/api/users/v1/auth/me", headers=_auth_header(token))
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["role"] == "CUSTOMER_SERVICE"

    logout_resp = client.post("/api/users/v1/auth/logout", headers=_auth_header(token))
    assert logout_resp.status_code == 200
    assert logout_resp.json() == {"message": "logged out"}


def test_worker_cannot_access_admin_dashboard() -> None:
    client = build_client()
    client.post(
        "/api/users/v1/auth/register",
        json={
            "email": "worker@example.com",
            "password": "password123",
            "role": "WORKER",
            "worker_display_name": "worker-one",
        },
    )
    login_resp = client.post(
        "/api/users/v1/auth/login",
        json={"email": "worker@example.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]

    response = client.get("/api/users/v1/admin/dashboard", headers=_auth_header(token))

    assert response.status_code == 403


def test_customer_service_can_dispatch_order() -> None:
    client = build_client()
    client.post(
        "/api/users/v1/auth/register",
        json={
            "email": "cs@example.com",
            "password": "password123",
            "role": "CUSTOMER_SERVICE",
        },
    )
    login_resp = client.post(
        "/api/users/v1/auth/login",
        json={"email": "cs@example.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]

    response = client.post("/api/users/v1/orders/dispatch", headers=_auth_header(token))

    assert response.status_code == 200
    assert response.json() == {"message": "order dispatched"}


def test_missing_token_rejected() -> None:
    client = build_client()

    response = client.get("/api/users/v1/auth/me")

    assert response.status_code == 401


def test_disabled_worker_cannot_login() -> None:
    client = build_client()
    worker_resp = client.post(
        "/api/users/v1/auth/register",
        json={
            "email": "worker@example.com",
            "password": "password123",
            "role": "WORKER",
            "worker_display_name": "worker-one",
        },
    )
    customer_resp = client.post(
        "/api/users/v1/auth/register",
        json={
            "email": "cs@example.com",
            "password": "password123",
            "role": "CUSTOMER_SERVICE",
        },
    )

    assert worker_resp.status_code == 201
    assert customer_resp.status_code == 201

    cs_login = client.post(
        "/api/users/v1/auth/login",
        json={"email": "cs@example.com", "password": "password123"},
    )
    cs_token = cs_login.json()["access_token"]

    worker_user_id = worker_resp.json()["user"]["id"]
    disable_resp = client.patch(
        f"/api/users/v1/workers/{worker_user_id}/status",
        headers=_auth_header(cs_token),
        json={"employment_status": "DISABLED"},
    )
    assert disable_resp.status_code == 200

    worker_login = client.post(
        "/api/users/v1/auth/login",
        json={"email": "worker@example.com", "password": "password123"},
    )

    assert worker_login.status_code == 401
