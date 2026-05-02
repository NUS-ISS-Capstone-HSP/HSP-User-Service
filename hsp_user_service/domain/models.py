from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SourceType(StrEnum):
    HTTP = "HTTP"
    GRPC = "GRPC"


@dataclass(slots=True)
class EchoRecord:
    id: str
    message: str
    source: SourceType
    created_at: datetime


class UserRole(StrEnum):
    WORKER = "WORKER"
    CUSTOMER_SERVICE = "CUSTOMER_SERVICE"
    OWNER = "OWNER"


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class EmploymentStatus(StrEnum):
    ON_DUTY = "ON_DUTY"
    DISABLED = "DISABLED"


class LoginAuditEvent(StrEnum):
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"


@dataclass(slots=True)
class User:
    id: int
    email: str
    password_hash: str
    role: UserRole
    status: UserStatus
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class WorkerProfile:
    id: int
    user_id: int
    worker_no: str
    display_name: str
    employment_status: EmploymentStatus
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class LoginAuditLog:
    id: int
    user_id: int | None
    email: str
    event: LoginAuditEvent
    ip: str | None
    user_agent: str | None
    reason: str | None
    created_at: datetime


@dataclass(slots=True)
class AccessToken:
    token: str
    token_type: str
    expires_in: int
