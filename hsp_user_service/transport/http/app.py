from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from hsp_user_service.domain.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from hsp_user_service.service.auth_service import AuthService
from hsp_user_service.service.echo_service import EchoService
from hsp_user_service.transport.http.auth_router import build_auth_router
from hsp_user_service.transport.http.router import build_router


def create_http_app(
    echo_service: EchoService,
    auth_service: AuthService | None = None,
) -> FastAPI:
    app = FastAPI(title="HSP User Service")
    app.include_router(build_router(echo_service))
    if auth_service is not None:
        app.include_router(build_auth_router(auth_service))

    @app.get("/api/users/health", tags=["health"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.exception_handler(ValidationError)
    async def validation_handler(_: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def conflict_handler(_: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(AuthenticationError)
    async def authentication_handler(_: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(AuthorizationError)
    async def authorization_handler(_: Request, exc: AuthorizationError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    return app
