from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from hsp_user_service.domain.errors import AuthenticationError
from hsp_user_service.domain.models import UserRole
from hsp_user_service.service.auth_service import AuthenticatedIdentity, AuthService

HTTP_BEARER = HTTPBearer(auto_error=False)
CredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(HTTP_BEARER)]


class AuthDependencies:
    def __init__(self, auth_service: AuthService) -> None:
        self._auth_service = auth_service

    async def current_identity(
        self,
        credentials: CredentialsDep,
    ) -> AuthenticatedIdentity:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise AuthenticationError("missing bearer token")
        return await self._auth_service.authenticate_access_token(credentials.credentials)

    def require_roles(
        self,
        *roles: UserRole,
    ) -> Callable[..., Awaitable[AuthenticatedIdentity]]:
        allowed_roles = set(roles)

        async def dependency(
            identity: Annotated[AuthenticatedIdentity, Depends(self.current_identity)],
        ) -> AuthenticatedIdentity:
            self._auth_service.ensure_roles(identity, allowed_roles)
            return identity

        return dependency
