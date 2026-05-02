import grpc
import pytest
import pytest_asyncio

from hsp_user_service.repository.in_memory import InMemoryUserRepository
from hsp_user_service.service.auth_service import AuthService
from hsp_user_service.transport.grpc.service import UserAuthGrpcService
from rpc.user.v1 import user_pb2, user_pb2_grpc


@pytest_asyncio.fixture
async def auth_grpc_stub() -> user_pb2_grpc.UserAuthServiceStub:
    auth_service = AuthService(
        repository=InMemoryUserRepository(),
        jwt_secret="test-secret-key-with-32-bytes-minimum!!",
        jwt_issuer="hsp-user-service",
        jwt_audience="hsp-api",
        access_token_ttl_seconds=900,
    )

    server = grpc.aio.server()
    user_pb2_grpc.add_UserAuthServiceServicer_to_server(UserAuthGrpcService(auth_service), server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()

    channel = grpc.aio.insecure_channel(f"127.0.0.1:{port}")
    stub = user_pb2_grpc.UserAuthServiceStub(channel)

    try:
        yield stub
    finally:
        await channel.close()
        await server.stop(0)


def _gateway_md(user_id: int, role: str) -> tuple[tuple[str, str], ...]:
    return (
        ("x-user-id", str(user_id)),
        ("x-user-role", role),
    )


@pytest.mark.asyncio
async def test_register_worker_success(auth_grpc_stub: user_pb2_grpc.UserAuthServiceStub) -> None:
    response = await auth_grpc_stub.Register(
        user_pb2.RegisterRequest(
            email="worker@example.com",
            password="password123",
            role=user_pb2.USER_ROLE_WORKER,
            worker_display_name="worker-one",
        ),
    )

    assert response.user.email == "worker@example.com"
    assert response.user.role == user_pb2.USER_ROLE_WORKER
    assert response.user.worker_profile.display_name == "worker-one"


@pytest.mark.asyncio
async def test_login_and_get_me_success(auth_grpc_stub: user_pb2_grpc.UserAuthServiceStub) -> None:
    await auth_grpc_stub.Register(
        user_pb2.RegisterRequest(
            email="cs@example.com",
            password="password123",
            role=user_pb2.USER_ROLE_CUSTOMER_SERVICE,
        ),
    )

    login_response = await auth_grpc_stub.Login(
        user_pb2.LoginRequest(email="cs@example.com", password="password123"),
    )

    me_response = await auth_grpc_stub.GetMe(
        user_pb2.GetMeRequest(),
        metadata=_gateway_md(login_response.user.id, "CUSTOMER_SERVICE"),
    )

    assert login_response.token_type == "Bearer"
    assert me_response.user.email == "cs@example.com"
    assert me_response.user.role == user_pb2.USER_ROLE_CUSTOMER_SERVICE


@pytest.mark.asyncio
async def test_worker_cannot_access_admin_dashboard(
    auth_grpc_stub: user_pb2_grpc.UserAuthServiceStub,
) -> None:
    await auth_grpc_stub.Register(
        user_pb2.RegisterRequest(
            email="worker@example.com",
            password="password123",
            role=user_pb2.USER_ROLE_WORKER,
            worker_display_name="worker-one",
        ),
    )
    login_response = await auth_grpc_stub.Login(
        user_pb2.LoginRequest(email="worker@example.com", password="password123"),
    )

    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        await auth_grpc_stub.GetAdminDashboard(
            user_pb2.GetAdminDashboardRequest(),
            metadata=_gateway_md(login_response.user.id, "WORKER"),
        )

    assert exc_info.value.code() == grpc.StatusCode.PERMISSION_DENIED


@pytest.mark.asyncio
async def test_customer_service_can_dispatch_order(
    auth_grpc_stub: user_pb2_grpc.UserAuthServiceStub,
) -> None:
    await auth_grpc_stub.Register(
        user_pb2.RegisterRequest(
            email="cs@example.com",
            password="password123",
            role=user_pb2.USER_ROLE_CUSTOMER_SERVICE,
        ),
    )
    login_response = await auth_grpc_stub.Login(
        user_pb2.LoginRequest(email="cs@example.com", password="password123"),
    )

    response = await auth_grpc_stub.DispatchOrder(
        user_pb2.DispatchOrderRequest(),
        metadata=_gateway_md(login_response.user.id, "CUSTOMER_SERVICE"),
    )

    assert response.message == "order dispatched"


@pytest.mark.asyncio
async def test_disabled_worker_cannot_login(
    auth_grpc_stub: user_pb2_grpc.UserAuthServiceStub,
) -> None:
    worker = await auth_grpc_stub.Register(
        user_pb2.RegisterRequest(
            email="worker@example.com",
            password="password123",
            role=user_pb2.USER_ROLE_WORKER,
            worker_display_name="worker-one",
        ),
    )
    await auth_grpc_stub.Register(
        user_pb2.RegisterRequest(
            email="cs@example.com",
            password="password123",
            role=user_pb2.USER_ROLE_CUSTOMER_SERVICE,
        ),
    )

    cs_login = await auth_grpc_stub.Login(
        user_pb2.LoginRequest(email="cs@example.com", password="password123"),
    )

    update_response = await auth_grpc_stub.UpdateWorkerStatus(
        user_pb2.UpdateWorkerStatusRequest(
            user_id=worker.user.id,
            employment_status=user_pb2.EMPLOYMENT_STATUS_DISABLED,
        ),
        metadata=_gateway_md(cs_login.user.id, "CUSTOMER_SERVICE"),
    )
    assert update_response.user.status == user_pb2.USER_STATUS_DISABLED

    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        await auth_grpc_stub.Login(
            user_pb2.LoginRequest(email="worker@example.com", password="password123"),
        )

    assert exc_info.value.code() == grpc.StatusCode.UNAUTHENTICATED


@pytest.mark.asyncio
async def test_missing_gateway_identity_metadata_rejected(
    auth_grpc_stub: user_pb2_grpc.UserAuthServiceStub,
) -> None:
    await auth_grpc_stub.Register(
        user_pb2.RegisterRequest(
            email="cs@example.com",
            password="password123",
            role=user_pb2.USER_ROLE_CUSTOMER_SERVICE,
        ),
    )

    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        await auth_grpc_stub.GetMe(user_pb2.GetMeRequest())

    assert exc_info.value.code() == grpc.StatusCode.UNAUTHENTICATED
