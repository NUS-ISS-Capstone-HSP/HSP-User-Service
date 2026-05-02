from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from jwt import InvalidTokenError

from hsp_user_service.domain.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from hsp_user_service.domain.models import (
    AccessToken,
    EmploymentStatus,
    LoginAuditEvent,
    User,
    UserRole,
    UserStatus,
    WorkerProfile,
)
from hsp_user_service.repository.interfaces import UserRepository


@dataclass(slots=True)
class AuthenticatedIdentity:
    user: User
    worker_profile: WorkerProfile | None


@dataclass(slots=True)
class LoginResult:
    access_token: AccessToken
    identity: AuthenticatedIdentity


@dataclass(slots=True)
class RegisterResult:
    user: User
    worker_profile: WorkerProfile | None


class AuthService:
    def __init__(
        self,
        repository: UserRepository,
        jwt_secret: str,
        jwt_issuer: str,
        jwt_audience: str,
        access_token_ttl_seconds: int,
    ) -> None:
        self._repository = repository
        self._jwt_secret = jwt_secret
        self._jwt_issuer = jwt_issuer
        self._jwt_audience = jwt_audience
        self._access_token_ttl_seconds = access_token_ttl_seconds

    async def register(
        self,
        email: str,
        password: str,
        role: UserRole,
        worker_display_name: str | None,
    ) -> RegisterResult:
        normalized_email = _normalize_email(email)
        _validate_password_strength(password)
        display_name: str | None = None
        if role == UserRole.WORKER:
            display_name = (worker_display_name or "").strip()
            if not display_name:
                raise ValidationError("worker_display_name is required for WORKER role")

        existing = await self._repository.get_user_by_email(normalized_email)
        if existing is not None:
            raise ConflictError("email already exists")

        password_hash = _hash_password(password)
        user = await self._repository.create_user(
            email=normalized_email,
            password_hash=password_hash,
            role=role,
            status=UserStatus.ACTIVE,
        )

        worker_profile: WorkerProfile | None = None
        if role == UserRole.WORKER:
            assert display_name is not None
            worker_profile = await self._repository.create_worker_profile(
                user_id=user.id,
                worker_no=f"WK{user.id:08d}",
                display_name=display_name,
                employment_status=EmploymentStatus.ON_DUTY,
            )

        return RegisterResult(user=user, worker_profile=worker_profile)

    async def login(
        self,
        email: str,
        password: str,
        ip: str | None,
        user_agent: str | None,
    ) -> LoginResult:
        normalized_email = _normalize_email(email)
        user = await self._repository.get_user_by_email(normalized_email)

        if user is None:
            await self._repository.create_login_audit_log(
                user_id=None,
                email=normalized_email,
                event=LoginAuditEvent.LOGIN_FAILED,
                ip=ip,
                user_agent=user_agent,
                reason="user_not_found",
            )
            raise AuthenticationError("invalid email or password")

        if not _verify_password(password, user.password_hash):
            await self._repository.create_login_audit_log(
                user_id=user.id,
                email=user.email,
                event=LoginAuditEvent.LOGIN_FAILED,
                ip=ip,
                user_agent=user_agent,
                reason="invalid_password",
            )
            raise AuthenticationError("invalid email or password")

        if user.status != UserStatus.ACTIVE:
            await self._repository.create_login_audit_log(
                user_id=user.id,
                email=user.email,
                event=LoginAuditEvent.LOGIN_FAILED,
                ip=ip,
                user_agent=user_agent,
                reason="account_disabled",
            )
            raise AuthenticationError("account is disabled")

        worker_profile = await self._repository.get_worker_profile_by_user_id(user.id)
        if user.role == UserRole.WORKER:
            if worker_profile is None:
                raise NotFoundError("worker profile not found")
            if worker_profile.employment_status != EmploymentStatus.ON_DUTY:
                await self._repository.create_login_audit_log(
                    user_id=user.id,
                    email=user.email,
                    event=LoginAuditEvent.LOGIN_FAILED,
                    ip=ip,
                    user_agent=user_agent,
                    reason="worker_disabled",
                )
                raise AuthenticationError("worker account is disabled")

        now = datetime.now(UTC)
        await self._repository.update_user_last_login_at(user.id, now)

        access_token = self._issue_access_token(user)

        await self._repository.create_login_audit_log(
            user_id=user.id,
            email=user.email,
            event=LoginAuditEvent.LOGIN_SUCCESS,
            ip=ip,
            user_agent=user_agent,
        )

        latest_user = await self._repository.get_user_by_id(user.id)
        if latest_user is None:
            raise NotFoundError("user not found")

        return LoginResult(
            access_token=access_token,
            identity=AuthenticatedIdentity(
                user=latest_user,
                worker_profile=worker_profile,
            ),
        )

    async def logout(
        self,
        identity: AuthenticatedIdentity,
        ip: str | None,
        user_agent: str | None,
    ) -> None:
        await self._repository.create_login_audit_log(
            user_id=identity.user.id,
            email=identity.user.email,
            event=LoginAuditEvent.LOGOUT,
            ip=ip,
            user_agent=user_agent,
        )

    async def get_me(self, identity: AuthenticatedIdentity) -> AuthenticatedIdentity:
        user = await self._repository.get_user_by_id(identity.user.id)
        if user is None:
            raise NotFoundError("user not found")
        worker_profile = await self._repository.get_worker_profile_by_user_id(user.id)
        return AuthenticatedIdentity(user=user, worker_profile=worker_profile)

    async def authenticate_access_token(self, token: str) -> AuthenticatedIdentity:
        payload = self._decode_access_token(token)
        user_id_str = payload.get("sub")
        role_raw = payload.get("role")
        if not isinstance(user_id_str, str) or not user_id_str.isdigit():
            raise AuthenticationError("invalid token subject")
        if not isinstance(role_raw, str):
            raise AuthenticationError("invalid token role")
        try:
            role = UserRole(role_raw)
        except ValueError as exc:
            raise AuthenticationError("invalid token role") from exc

        return await self.authenticate_gateway_identity(
            user_id=int(user_id_str),
            role=role,
        )

    async def authenticate_gateway_identity(
        self,
        user_id: int,
        role: UserRole,
    ) -> AuthenticatedIdentity:
        user = await self._repository.get_user_by_id(user_id)
        if user is None:
            raise AuthenticationError("user not found")
        if user.role != role:
            raise AuthenticationError("gateway role mismatch")
        if user.status != UserStatus.ACTIVE:
            raise AuthenticationError("account is disabled")

        worker_profile = await self._repository.get_worker_profile_by_user_id(user.id)
        if user.role == UserRole.WORKER:
            if worker_profile is None:
                raise AuthenticationError("worker profile not found")
            if worker_profile.employment_status != EmploymentStatus.ON_DUTY:
                raise AuthenticationError("worker account is disabled")

        return AuthenticatedIdentity(user=user, worker_profile=worker_profile)

    async def update_worker_status(
        self,
        user_id: int,
        employment_status: EmploymentStatus,
    ) -> AuthenticatedIdentity:
        user = await self._repository.get_user_by_id(user_id)
        if user is None:
            raise NotFoundError("user not found")
        if user.role != UserRole.WORKER:
            raise ValidationError("target user is not WORKER")

        worker_profile = await self._repository.update_worker_employment_status(
            user_id,
            employment_status,
        )
        if worker_profile is None:
            raise NotFoundError("worker profile not found")

        next_user_status = (
            UserStatus.ACTIVE
            if employment_status == EmploymentStatus.ON_DUTY
            else UserStatus.DISABLED
        )
        updated_user = await self._repository.update_user_status(user_id, next_user_status)
        if updated_user is None:
            raise NotFoundError("user not found")

        return AuthenticatedIdentity(user=updated_user, worker_profile=worker_profile)

    def ensure_roles(self, identity: AuthenticatedIdentity, allowed: set[UserRole]) -> None:
        if identity.user.role not in allowed:
            raise AuthorizationError("forbidden")

    def _issue_access_token(self, user: User) -> AccessToken:
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=self._access_token_ttl_seconds)
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "iss": self._jwt_issuer,
            "aud": self._jwt_audience,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        token = jwt.encode(payload, self._jwt_secret, algorithm="HS256")
        return AccessToken(
            token=token,
            token_type="Bearer",
            expires_in=self._access_token_ttl_seconds,
        )

    def _decode_access_token(self, token: str) -> dict[str, object]:
        try:
            payload = jwt.decode(
                token,
                self._jwt_secret,
                algorithms=["HS256"],
                audience=self._jwt_audience,
                issuer=self._jwt_issuer,
            )
        except InvalidTokenError as exc:
            raise AuthenticationError("invalid token") from exc
        return payload


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized:
        raise ValidationError("email must not be empty")
    if "@" not in normalized:
        raise ValidationError("invalid email")
    return normalized


def _validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise ValidationError("password must be at least 8 characters")


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
