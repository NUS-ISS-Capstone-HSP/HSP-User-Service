from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
from hsp_user_service.infrastructure.orm import (
    EchoRecordORM,
    LoginAuditLogORM,
    UserORM,
    WorkerProfileORM,
)
from hsp_user_service.repository.interfaces import EchoRepository, UserRepository


class SQLAlchemyEchoRepository(EchoRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, message: str, source: SourceType) -> EchoRecord:
        row = EchoRecordORM(
            id=str(uuid4()),
            message=message,
            source=source.value,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return _to_domain(row)

    async def get_by_id(self, record_id: str) -> EchoRecord | None:
        async with self._session_factory() as session:
            stmt = select(EchoRecordORM).where(EchoRecordORM.id == record_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
        if row is None:
            return None
        return _to_domain(row)


def _to_domain(row: EchoRecordORM) -> EchoRecord:
    created_at = row.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)

    return EchoRecord(
        id=row.id,
        message=row.message,
        source=SourceType(row.source),
        created_at=created_at,
    )


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_user(
        self,
        email: str,
        password_hash: str,
        role: UserRole,
        status: UserStatus,
    ) -> User:
        row = UserORM(
            email=email,
            password_hash=password_hash,
            role=role,
            status=status,
        )
        async with self._session_factory() as session:
            session.add(row)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ConflictError("user already exists") from exc
            await session.refresh(row)
        return _to_domain_user(row)

    async def get_user_by_email(self, email: str) -> User | None:
        async with self._session_factory() as session:
            stmt = select(UserORM).where(UserORM.email == email)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
        if row is None:
            return None
        return _to_domain_user(row)

    async def get_user_by_id(self, user_id: int) -> User | None:
        async with self._session_factory() as session:
            stmt = select(UserORM).where(UserORM.id == user_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
        if row is None:
            return None
        return _to_domain_user(row)

    async def create_worker_profile(
        self,
        user_id: int,
        worker_no: str,
        display_name: str,
        employment_status: EmploymentStatus,
    ) -> WorkerProfile:
        row = WorkerProfileORM(
            user_id=user_id,
            worker_no=worker_no,
            display_name=display_name,
            employment_status=employment_status,
        )
        async with self._session_factory() as session:
            session.add(row)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ConflictError("worker profile already exists") from exc
            await session.refresh(row)
        return _to_domain_worker_profile(row)

    async def get_worker_profile_by_user_id(self, user_id: int) -> WorkerProfile | None:
        async with self._session_factory() as session:
            stmt = select(WorkerProfileORM).where(WorkerProfileORM.user_id == user_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
        if row is None:
            return None
        return _to_domain_worker_profile(row)

    async def update_user_last_login_at(self, user_id: int, at: datetime) -> None:
        async with self._session_factory() as session:
            stmt = select(UserORM).where(UserORM.id == user_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                return
            row.last_login_at = at
            row.updated_at = at
            await session.commit()

    async def update_user_status(self, user_id: int, status: UserStatus) -> User | None:
        async with self._session_factory() as session:
            stmt = select(UserORM).where(UserORM.id == user_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                return None
            row.status = status
            row.updated_at = _utc_now()
            await session.commit()
            await session.refresh(row)
        return _to_domain_user(row)

    async def update_worker_employment_status(
        self,
        user_id: int,
        status: EmploymentStatus,
    ) -> WorkerProfile | None:
        async with self._session_factory() as session:
            stmt = select(WorkerProfileORM).where(WorkerProfileORM.user_id == user_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                return None
            row.employment_status = status
            row.updated_at = _utc_now()
            await session.commit()
            await session.refresh(row)
        return _to_domain_worker_profile(row)

    async def create_login_audit_log(
        self,
        user_id: int | None,
        email: str,
        event: LoginAuditEvent,
        ip: str | None,
        user_agent: str | None,
        reason: str | None = None,
    ) -> LoginAuditLog:
        row = LoginAuditLogORM(
            user_id=user_id,
            email=email,
            event=event,
            ip=ip,
            user_agent=user_agent,
            reason=reason,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return _to_domain_login_audit_log(row)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _to_domain_user(row: UserORM) -> User:
    return User(
        id=row.id,
        email=row.email,
        password_hash=row.password_hash,
        role=row.role,
        status=row.status,
        last_login_at=_normalize_datetime(row.last_login_at) if row.last_login_at else None,
        created_at=_normalize_datetime(row.created_at),
        updated_at=_normalize_datetime(row.updated_at),
    )


def _to_domain_worker_profile(row: WorkerProfileORM) -> WorkerProfile:
    return WorkerProfile(
        id=row.id,
        user_id=row.user_id,
        worker_no=row.worker_no,
        display_name=row.display_name,
        employment_status=row.employment_status,
        created_at=_normalize_datetime(row.created_at),
        updated_at=_normalize_datetime(row.updated_at),
    )


def _to_domain_login_audit_log(row: LoginAuditLogORM) -> LoginAuditLog:
    return LoginAuditLog(
        id=row.id,
        user_id=row.user_id,
        email=row.email,
        event=row.event,
        ip=row.ip,
        user_agent=row.user_agent,
        reason=row.reason,
        created_at=_normalize_datetime(row.created_at),
    )
