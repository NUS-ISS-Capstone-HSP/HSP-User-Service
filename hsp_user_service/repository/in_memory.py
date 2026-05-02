from datetime import UTC, datetime
from uuid import uuid4

from hsp_user_service.domain.errors import ConflictError
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
from hsp_user_service.repository.interfaces import EchoRepository, UserRepository


class InMemoryEchoRepository(EchoRepository):
    def __init__(self) -> None:
        self._store: dict[str, EchoRecord] = {}

    async def create(self, message: str, source: SourceType) -> EchoRecord:
        record = EchoRecord(
            id=str(uuid4()),
            message=message,
            source=source,
            created_at=datetime.now(UTC),
        )
        self._store[record.id] = record
        return record

    async def get_by_id(self, record_id: str) -> EchoRecord | None:
        return self._store.get(record_id)


class InMemoryUserRepository(UserRepository):
    def __init__(self) -> None:
        self._users: dict[int, User] = {}
        self._users_by_email: dict[str, int] = {}
        self._worker_profiles_by_user_id: dict[int, WorkerProfile] = {}
        self._login_logs: dict[int, LoginAuditLog] = {}
        self._user_id_seq = 0
        self._worker_profile_id_seq = 0
        self._login_log_id_seq = 0

    async def create_user(
        self,
        email: str,
        password_hash: str,
        role: UserRole,
        status: UserStatus,
    ) -> User:
        if email in self._users_by_email:
            raise ConflictError("user already exists")

        self._user_id_seq += 1
        now = datetime.now(UTC)
        user = User(
            id=self._user_id_seq,
            email=email,
            password_hash=password_hash,
            role=role,
            status=status,
            last_login_at=None,
            created_at=now,
            updated_at=now,
        )
        self._users[user.id] = user
        self._users_by_email[email] = user.id
        return user

    async def get_user_by_email(self, email: str) -> User | None:
        user_id = self._users_by_email.get(email)
        if user_id is None:
            return None
        return self._users.get(user_id)

    async def get_user_by_id(self, user_id: int) -> User | None:
        return self._users.get(user_id)

    async def create_worker_profile(
        self,
        user_id: int,
        worker_no: str,
        display_name: str,
        employment_status: EmploymentStatus,
    ) -> WorkerProfile:
        if user_id in self._worker_profiles_by_user_id:
            raise ConflictError("worker profile already exists")

        self._worker_profile_id_seq += 1
        now = datetime.now(UTC)
        profile = WorkerProfile(
            id=self._worker_profile_id_seq,
            user_id=user_id,
            worker_no=worker_no,
            display_name=display_name,
            employment_status=employment_status,
            created_at=now,
            updated_at=now,
        )
        self._worker_profiles_by_user_id[user_id] = profile
        return profile

    async def get_worker_profile_by_user_id(self, user_id: int) -> WorkerProfile | None:
        return self._worker_profiles_by_user_id.get(user_id)

    async def update_user_last_login_at(self, user_id: int, at: datetime) -> None:
        user = self._users[user_id]
        self._users[user_id] = User(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            role=user.role,
            status=user.status,
            last_login_at=at,
            created_at=user.created_at,
            updated_at=at,
        )

    async def update_user_status(self, user_id: int, status: UserStatus) -> User | None:
        user = self._users.get(user_id)
        if user is None:
            return None
        now = datetime.now(UTC)
        updated = User(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            role=user.role,
            status=status,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=now,
        )
        self._users[user_id] = updated
        return updated

    async def update_worker_employment_status(
        self,
        user_id: int,
        status: EmploymentStatus,
    ) -> WorkerProfile | None:
        profile = self._worker_profiles_by_user_id.get(user_id)
        if profile is None:
            return None
        now = datetime.now(UTC)
        updated = WorkerProfile(
            id=profile.id,
            user_id=profile.user_id,
            worker_no=profile.worker_no,
            display_name=profile.display_name,
            employment_status=status,
            created_at=profile.created_at,
            updated_at=now,
        )
        self._worker_profiles_by_user_id[user_id] = updated
        return updated

    async def create_login_audit_log(
        self,
        user_id: int | None,
        email: str,
        event: LoginAuditEvent,
        ip: str | None,
        user_agent: str | None,
        reason: str | None = None,
    ) -> LoginAuditLog:
        self._login_log_id_seq += 1
        log = LoginAuditLog(
            id=self._login_log_id_seq,
            user_id=user_id,
            email=email,
            event=event,
            ip=ip,
            user_agent=user_agent,
            reason=reason,
            created_at=datetime.now(UTC),
        )
        self._login_logs[log.id] = log
        return log
