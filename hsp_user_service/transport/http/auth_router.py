import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request

from hsp_user_service.domain.models import UserRole
from hsp_user_service.service.auth_service import AuthenticatedIdentity, AuthService
from hsp_user_service.transport.http.auth import AuthDependencies
from hsp_user_service.transport.http.mapper import to_user_response
from hsp_user_service.transport.http.schemas import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    MeResponse,
    RegisterRequest,
    RegisterResponse,
    UpdateWorkerStatusRequest,
    UpdateWorkerStatusResponse,
)

logger = logging.getLogger(__name__)


def build_auth_router(auth_service: AuthService) -> APIRouter:
    router = APIRouter(prefix="/api/users/v1", tags=["auth"])
    auth_dependencies = AuthDependencies(auth_service)
    current_identity = auth_dependencies.current_identity
    staff_or_owner = auth_dependencies.require_roles(UserRole.CUSTOMER_SERVICE, UserRole.OWNER)

    @router.post(
        "/auth/register",
        response_model=RegisterResponse,
        status_code=201,
        summary="Register a new user",
        description="Register WORKER / CUSTOMER_SERVICE / OWNER account.",
    )
    async def register(payload: RegisterRequest) -> RegisterResponse:
        result = await auth_service.register(
            email=payload.email,
            password=payload.password,
            role=payload.role,
            worker_display_name=payload.worker_display_name,
        )
        identity = AuthenticatedIdentity(
            user=result.user,
            worker_profile=result.worker_profile,
        )
        return RegisterResponse(user=to_user_response(identity))

    @router.post(
        "/auth/login",
        response_model=LoginResponse,
        summary="Login",
        description="Authenticate by email/password and return JWT access token.",
    )
    async def login(payload: LoginRequest, request: Request) -> LoginResponse:
        ip = request.client.host if request.client is not None else None
        logger.info(
            "http login request email=%s password=%s client_ip=%s user_agent=%s headers=%s",
            payload.email,
            payload.password,
            ip,
            request.headers.get("user-agent"),
            list(request.headers.keys()),
        )
        result = await auth_service.login(
            email=payload.email,
            password=payload.password,
            ip=ip,
            user_agent=request.headers.get("user-agent"),
        )
        return LoginResponse(
            access_token=result.access_token.token,
            token_type=result.access_token.token_type,
            expires_in=result.access_token.expires_in,
            user=to_user_response(result.identity),
        )

    @router.post(
        "/auth/logout",
        response_model=LogoutResponse,
        summary="Logout",
        description="Logout current user. Access token itself remains valid until expiration.",
    )
    async def logout(
        request: Request,
        identity: Annotated[AuthenticatedIdentity, Depends(current_identity)],
    ) -> LogoutResponse:
        ip = request.client.host if request.client is not None else None
        await auth_service.logout(
            identity=identity,
            ip=ip,
            user_agent=request.headers.get("user-agent"),
        )
        return LogoutResponse(message="logged out")

    @router.get(
        "/auth/me",
        response_model=MeResponse,
        summary="Get current user",
        description="Get profile for current authenticated user.",
    )
    async def me(
        identity: Annotated[AuthenticatedIdentity, Depends(current_identity)],
    ) -> MeResponse:
        latest = await auth_service.get_me(identity)
        return MeResponse(user=to_user_response(latest))

    @router.get(
        "/admin/dashboard",
        summary="Backoffice dashboard guard",
        description="Used for RBAC checks, requires CUSTOMER_SERVICE or OWNER.",
    )
    async def admin_dashboard(
        _: Annotated[AuthenticatedIdentity, Depends(staff_or_owner)],
    ) -> dict[str, str]:
        return {"message": "dashboard access granted"}

    @router.post(
        "/orders/dispatch",
        summary="Dispatch order guard",
        description="Used for RBAC checks, requires CUSTOMER_SERVICE or OWNER.",
    )
    async def dispatch_order(
        _: Annotated[AuthenticatedIdentity, Depends(staff_or_owner)],
    ) -> dict[str, str]:
        return {"message": "order dispatched"}

    @router.patch(
        "/workers/{user_id}/status",
        response_model=UpdateWorkerStatusResponse,
        summary="Enable/disable worker account",
        description="Update worker employment status and sync account status.",
    )
    async def update_worker_status(
        payload: UpdateWorkerStatusRequest,
        _: Annotated[AuthenticatedIdentity, Depends(staff_or_owner)],
        user_id: int = Path(..., ge=1, description="Worker user id."),
    ) -> UpdateWorkerStatusResponse:
        updated = await auth_service.update_worker_status(
            user_id=user_id,
            employment_status=payload.employment_status,
        )
        return UpdateWorkerStatusResponse(user=to_user_response(updated))

    return router
