import pytest

from hsp_user_service.bootstrap.seed_users import seed_default_users
from hsp_user_service.domain.models import UserRole, UserStatus
from hsp_user_service.repository.in_memory import InMemoryUserRepository
from hsp_user_service.service.auth_service import AuthService


@pytest.mark.asyncio
async def test_seed_default_users_creates_loginable_accounts() -> None:
    repository = InMemoryUserRepository()

    await seed_default_users(repository)

    auth_service = AuthService(
        repository=repository,
        jwt_secret="test-secret-key-with-32-bytes-minimum!!",
        jwt_issuer="hsp-user-service",
        jwt_audience="hsp-api",
        access_token_ttl_seconds=900,
    )

    admin_login = await auth_service.login(
        email="admin001@hsp.local",
        password="111111",
        ip=None,
        user_agent="pytest",
    )
    cs_login = await auth_service.login(
        email="cs001@hsp.local",
        password="cs111111",
        ip=None,
        user_agent="pytest",
    )
    worker_login = await auth_service.login(
        email="worker.test@example.com",
        password="worker1234",
        ip=None,
        user_agent="pytest",
    )

    assert admin_login.identity.user.role == UserRole.OWNER
    assert cs_login.identity.user.role == UserRole.CUSTOMER_SERVICE
    assert worker_login.identity.user.role == UserRole.WORKER
    assert worker_login.identity.worker_profile is not None


@pytest.mark.asyncio
async def test_seed_default_users_skips_existing_email() -> None:
    repository = InMemoryUserRepository()
    existing = await repository.create_user(
        email="admin001@hsp.local",
        password_hash="existing-hash",
        role=UserRole.CUSTOMER_SERVICE,
        status=UserStatus.ACTIVE,
    )

    await seed_default_users(repository)

    admin = await repository.get_user_by_email("admin001@hsp.local")

    assert admin == existing
