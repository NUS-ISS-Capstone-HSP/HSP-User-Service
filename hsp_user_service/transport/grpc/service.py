import logging

import grpc
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message

from hsp_user_service.domain.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    NotFoundError,
    ValidationError,
)
from hsp_user_service.domain.models import SourceType, UserRole
from hsp_user_service.service.auth_service import AuthenticatedIdentity, AuthService
from hsp_user_service.service.echo_service import EchoService
from hsp_user_service.transport.grpc.auth_mapper import (
    to_domain_employment_status,
    to_domain_user_role,
    to_grpc_user,
)
from hsp_user_service.transport.grpc.mapper import to_grpc_record
from rpc.echo.v1 import echo_pb2, echo_pb2_grpc
from rpc.user.v1 import user_pb2, user_pb2_grpc

logger = logging.getLogger(__name__)


class EchoGrpcService(echo_pb2_grpc.EchoServiceServicer):
    def __init__(self, echo_service: EchoService) -> None:
        self._echo_service = echo_service

    async def CreateEcho(
        self,
        request: echo_pb2.CreateEchoRequest,
        context: grpc.aio.ServicerContext,
    ) -> echo_pb2.CreateEchoResponse:
        _log_grpc_request(context, "EchoService.CreateEcho", request)
        try:
            record = await self._echo_service.create_echo(request.message, SourceType.GRPC)
        except ValidationError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return echo_pb2.CreateEchoResponse(record=to_grpc_record(record))

    async def GetEcho(
        self,
        request: echo_pb2.GetEchoRequest,
        context: grpc.aio.ServicerContext,
    ) -> echo_pb2.GetEchoResponse:
        _log_grpc_request(context, "EchoService.GetEcho", request)
        try:
            record = await self._echo_service.get_echo(request.id)
        except ValidationError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        except NotFoundError as exc:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(exc))
        return echo_pb2.GetEchoResponse(record=to_grpc_record(record))

    async def Health(
        self,
        request: echo_pb2.HealthRequest,
        context: grpc.aio.ServicerContext,
    ) -> echo_pb2.HealthResponse:
        _log_grpc_request(context, "EchoService.Health", request)
        del request, context
        return echo_pb2.HealthResponse(status="ok")


class UserAuthGrpcService(user_pb2_grpc.UserAuthServiceServicer):
    def __init__(self, auth_service: AuthService) -> None:
        self._auth_service = auth_service

    async def Register(
        self,
        request: user_pb2.RegisterRequest,
        context: grpc.aio.ServicerContext,
    ) -> user_pb2.RegisterResponse:
        _log_grpc_request(
            context,
            "UserAuthService.Register",
            request,
            redacted_fields={"password"},
        )
        try:
            role = to_domain_user_role(request.role)
            result = await self._auth_service.register(
                email=request.email,
                password=request.password,
                role=role,
                worker_display_name=request.worker_display_name or None,
            )
            identity = AuthenticatedIdentity(
                user=result.user,
                worker_profile=result.worker_profile,
            )
            return user_pb2.RegisterResponse(
                user=to_grpc_user(identity),
            )
        except DomainError as exc:
            await _abort_with_domain_error(context, exc)

    async def Login(
        self,
        request: user_pb2.LoginRequest,
        context: grpc.aio.ServicerContext,
    ) -> user_pb2.LoginResponse:
        _log_grpc_request(context, "UserAuthService.Login", request)
        ip = _parse_peer_ip(context.peer())
        user_agent = _metadata_value(context, "user-agent")
        try:
            result = await self._auth_service.login(
                email=request.email,
                password=request.password,
                ip=ip,
                user_agent=user_agent,
            )
            return user_pb2.LoginResponse(
                access_token=result.access_token.token,
                token_type=result.access_token.token_type,
                expires_in=result.access_token.expires_in,
                user=to_grpc_user(result.identity),
            )
        except DomainError as exc:
            await _abort_with_domain_error(context, exc)

    async def Logout(
        self,
        request: user_pb2.LogoutRequest,
        context: grpc.aio.ServicerContext,
    ) -> user_pb2.LogoutResponse:
        _log_grpc_request(context, "UserAuthService.Logout", request)
        del request
        ip = _parse_peer_ip(context.peer())
        user_agent = _metadata_value(context, "user-agent")
        try:
            identity = await self._authenticate_from_context(context)
            await self._auth_service.logout(identity=identity, ip=ip, user_agent=user_agent)
            return user_pb2.LogoutResponse(message="logged out")
        except DomainError as exc:
            await _abort_with_domain_error(context, exc)

    async def GetMe(
        self,
        request: user_pb2.GetMeRequest,
        context: grpc.aio.ServicerContext,
    ) -> user_pb2.GetMeResponse:
        _log_grpc_request(context, "UserAuthService.GetMe", request)
        del request
        try:
            identity = await self._authenticate_from_context(context)
            latest = await self._auth_service.get_me(identity)
            return user_pb2.GetMeResponse(user=to_grpc_user(latest))
        except DomainError as exc:
            await _abort_with_domain_error(context, exc)

    async def GetAdminDashboard(
        self,
        request: user_pb2.GetAdminDashboardRequest,
        context: grpc.aio.ServicerContext,
    ) -> user_pb2.GetAdminDashboardResponse:
        _log_grpc_request(context, "UserAuthService.GetAdminDashboard", request)
        del request
        try:
            identity = await self._authenticate_from_context(context)
            self._auth_service.ensure_roles(identity, {UserRole.CUSTOMER_SERVICE, UserRole.OWNER})
            return user_pb2.GetAdminDashboardResponse(message="dashboard access granted")
        except DomainError as exc:
            await _abort_with_domain_error(context, exc)

    async def DispatchOrder(
        self,
        request: user_pb2.DispatchOrderRequest,
        context: grpc.aio.ServicerContext,
    ) -> user_pb2.DispatchOrderResponse:
        _log_grpc_request(context, "UserAuthService.DispatchOrder", request)
        del request
        try:
            identity = await self._authenticate_from_context(context)
            self._auth_service.ensure_roles(identity, {UserRole.CUSTOMER_SERVICE, UserRole.OWNER})
            return user_pb2.DispatchOrderResponse(message="order dispatched")
        except DomainError as exc:
            await _abort_with_domain_error(context, exc)

    async def UpdateWorkerStatus(
        self,
        request: user_pb2.UpdateWorkerStatusRequest,
        context: grpc.aio.ServicerContext,
    ) -> user_pb2.UpdateWorkerStatusResponse:
        _log_grpc_request(context, "UserAuthService.UpdateWorkerStatus", request)
        try:
            identity = await self._authenticate_from_context(context)
            self._auth_service.ensure_roles(identity, {UserRole.CUSTOMER_SERVICE, UserRole.OWNER})
            employment_status = to_domain_employment_status(request.employment_status)
            updated = await self._auth_service.update_worker_status(
                user_id=request.user_id,
                employment_status=employment_status,
            )
            return user_pb2.UpdateWorkerStatusResponse(user=to_grpc_user(updated))
        except DomainError as exc:
            await _abort_with_domain_error(context, exc)

    async def _authenticate_from_context(
        self,
        context: grpc.aio.ServicerContext,
    ) -> AuthenticatedIdentity:
        user_id_raw = _metadata_value(context, "x-user-id")
        role_raw = _metadata_value(context, "x-user-role")
        if user_id_raw is None or role_raw is None:
            raise AuthenticationError("missing gateway identity metadata")
        if not user_id_raw.isdigit():
            raise AuthenticationError("invalid x-user-id")

        role = _parse_gateway_role(role_raw)
        return await self._auth_service.authenticate_gateway_identity(
            user_id=int(user_id_raw),
            role=role,
        )


def _metadata_value(context: grpc.aio.ServicerContext, key: str) -> str | None:
    for k, v in context.invocation_metadata():
        if k.lower() == key:
            if isinstance(v, bytes):
                return v.decode("utf-8")
            return str(v)
    return None


def _parse_peer_ip(peer: str) -> str | None:
    # peer format examples: ipv4:127.0.0.1:51234 or ipv6:[::1]:51234
    if ":" not in peer:
        return None
    parts = peer.split(":")
    if len(parts) >= 2:
        return parts[1].strip("[]")
    return None


async def _abort_with_domain_error(
    context: grpc.aio.ServicerContext,
    exc: DomainError,
) -> None:
    if isinstance(exc, ValidationError):
        await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
    elif isinstance(exc, ConflictError):
        await context.abort(grpc.StatusCode.ALREADY_EXISTS, str(exc))
    elif isinstance(exc, NotFoundError):
        await context.abort(grpc.StatusCode.NOT_FOUND, str(exc))
    elif isinstance(exc, AuthenticationError):
        await context.abort(grpc.StatusCode.UNAUTHENTICATED, str(exc))
    elif isinstance(exc, AuthorizationError):
        await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(exc))
    else:
        await context.abort(grpc.StatusCode.INTERNAL, str(exc))


def _log_grpc_request(
    context: grpc.aio.ServicerContext,
    method: str,
    request: Message,
    redacted_fields: set[str] | None = None,
) -> None:
    metadata_keys = [k for k, _ in context.invocation_metadata()]
    has_gateway_identity = (
        _metadata_value(context, "x-user-id") is not None
        and _metadata_value(context, "x-user-role") is not None
    )
    payload = MessageToDict(
        request,
        preserving_proto_field_name=True,
        use_integers_for_enums=False,
    )
    if redacted_fields:
        payload = _redact_payload(payload, redacted_fields)
    logger.info(
        "grpc request received method=%s has_gateway_identity=%s metadata_keys=%s payload=%s",
        method,
        has_gateway_identity,
        metadata_keys,
        payload,
    )


def _redact_payload(data: dict[str, object], redacted_fields: set[str]) -> dict[str, object]:
    masked: dict[str, object] = {}
    for key, value in data.items():
        if key in redacted_fields:
            masked[key] = "***"
        else:
            masked[key] = value
    return masked


def _parse_gateway_role(raw_role: str) -> UserRole:
    normalized = raw_role.strip().upper()
    if normalized.startswith("USER_ROLE_"):
        normalized = normalized.replace("USER_ROLE_", "", 1)
    try:
        return UserRole(normalized)
    except ValueError as exc:
        raise AuthenticationError("invalid x-user-role") from exc
