from datetime import datetime
from typing import Protocol

from hsp_user_service.domain.models import (
    EchoRecord,
    EmploymentStatus,
    LoginAuditEvent,
    LoginAuditLog,
    SourceType,
    User,
    UserRole,
    UserStatus,
    WorkerProfile,
)


class EchoRepository(Protocol):
    async def create(self, message: str, source: SourceType) -> EchoRecord:
        ...

    async def get_by_id(self, record_id: str) -> EchoRecord | None:
        ...


class UserRepository(Protocol):
    async def create_user(
        self,
        email: str,
        password_hash: str,
        role: UserRole,
        status: UserStatus,
    ) -> User:
        ...

    async def get_user_by_email(self, email: str) -> User | None:
        ...

    async def get_user_by_id(self, user_id: int) -> User | None:
        ...

    async def create_worker_profile(
        self,
        user_id: int,
        worker_no: str,
        display_name: str,
        employment_status: EmploymentStatus,
    ) -> WorkerProfile:
        ...

    async def get_worker_profile_by_user_id(self, user_id: int) -> WorkerProfile | None:
        ...

    async def update_user_last_login_at(self, user_id: int, at: datetime) -> None:
        ...

    async def update_user_status(self, user_id: int, status: UserStatus) -> User | None:
        ...

    async def update_worker_employment_status(
        self,
        user_id: int,
        status: EmploymentStatus,
    ) -> WorkerProfile | None:
        ...

    async def create_login_audit_log(
        self,
        user_id: int | None,
        email: str,
        event: LoginAuditEvent,
        ip: str | None,
        user_agent: str | None,
        reason: str | None = None,
    ) -> LoginAuditLog:
        ...
