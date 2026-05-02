import pytest

from hsp_user_service.domain.errors import AuthenticationError, ValidationError
from hsp_user_service.domain.models import EmploymentStatus, UserRole
from hsp_user_service.repository.in_memory import InMemoryUserRepository
from hsp_user_service.service.auth_service import AuthService


@pytest.fixture
def auth_service() -> AuthService:
    repository = InMemoryUserRepository()
    return AuthService(
        repository=repository,
        jwt_secret="test-secret-key-with-32-bytes-minimum!!",
        jwt_issuer="hsp-user-service",
        jwt_audience="hsp-api",
        access_token_ttl_seconds=900,
    )


@pytest.mark.asyncio
async def test_register_worker_creates_worker_profile(auth_service: AuthService) -> None:
    result = await auth_service.register(
        email="worker@example.com",
        password="password123",
        role=UserRole.WORKER,
        worker_display_name="worker-one",
    )

    assert result.user.email == "worker@example.com"
    assert result.user.password_hash != "password123"
    assert result.worker_profile is not None
    assert result.worker_profile.user_id == result.user.id


@pytest.mark.asyncio
async def test_register_worker_without_display_name_raises_validation_error(
    auth_service: AuthService,
) -> None:
    with pytest.raises(ValidationError):
        await auth_service.register(
            email="worker@example.com",
            password="password123",
            role=UserRole.WORKER,
            worker_display_name=None,
        )


@pytest.mark.asyncio
async def test_login_success_returns_access_token(auth_service: AuthService) -> None:
    await auth_service.register(
        email="cs@example.com",
        password="password123",
        role=UserRole.CUSTOMER_SERVICE,
        worker_display_name=None,
    )

    login = await auth_service.login(
        email="cs@example.com",
        password="password123",
        ip="127.0.0.1",
        user_agent="pytest",
    )

    assert login.access_token.token
    assert login.access_token.token_type == "Bearer"
    assert login.identity.user.role == UserRole.CUSTOMER_SERVICE


@pytest.mark.asyncio
async def test_login_with_invalid_password_fails(auth_service: AuthService) -> None:
    await auth_service.register(
        email="cs@example.com",
        password="password123",
        role=UserRole.CUSTOMER_SERVICE,
        worker_display_name=None,
    )

    with pytest.raises(AuthenticationError):
        await auth_service.login(
            email="cs@example.com",
            password="bad-password",
            ip="127.0.0.1",
            user_agent="pytest",
        )


@pytest.mark.asyncio
async def test_disabled_worker_cannot_login(auth_service: AuthService) -> None:
    result = await auth_service.register(
        email="worker@example.com",
        password="password123",
        role=UserRole.WORKER,
        worker_display_name="worker-two",
    )

    await auth_service.update_worker_status(
        user_id=result.user.id,
        employment_status=EmploymentStatus.DISABLED,
    )

    with pytest.raises(AuthenticationError):
        await auth_service.login(
            email="worker@example.com",
            password="password123",
            ip="127.0.0.1",
            user_agent="pytest",
        )
