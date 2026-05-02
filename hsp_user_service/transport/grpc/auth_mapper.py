from hsp_user_service.domain.errors import ValidationError
from hsp_user_service.domain.models import EmploymentStatus, UserRole, UserStatus, WorkerProfile
from hsp_user_service.service.auth_service import AuthenticatedIdentity
from rpc.user.v1 import user_pb2


def to_grpc_user(identity: AuthenticatedIdentity) -> user_pb2.User:
    payload = user_pb2.User(
        id=identity.user.id,
        email=identity.user.email,
        role=to_grpc_user_role(identity.user.role),
        status=to_grpc_user_status(identity.user.status),
        created_at=identity.user.created_at.isoformat(),
        updated_at=identity.user.updated_at.isoformat(),
        last_login_at=(
            identity.user.last_login_at.isoformat()
            if identity.user.last_login_at
            else ""
        ),
    )
    if identity.worker_profile is not None:
        payload.worker_profile.CopyFrom(to_grpc_worker_profile(identity.worker_profile))
    return payload


def to_grpc_worker_profile(profile: WorkerProfile) -> user_pb2.WorkerProfile:
    return user_pb2.WorkerProfile(
        id=profile.id,
        user_id=profile.user_id,
        worker_no=profile.worker_no,
        display_name=profile.display_name,
        employment_status=to_grpc_employment_status(profile.employment_status),
        created_at=profile.created_at.isoformat(),
        updated_at=profile.updated_at.isoformat(),
    )


def to_grpc_user_role(role: UserRole) -> user_pb2.UserRole:
    mapping = {
        UserRole.WORKER: user_pb2.USER_ROLE_WORKER,
        UserRole.CUSTOMER_SERVICE: user_pb2.USER_ROLE_CUSTOMER_SERVICE,
        UserRole.OWNER: user_pb2.USER_ROLE_OWNER,
    }
    return mapping[role]


def to_grpc_user_status(status: UserStatus) -> user_pb2.UserStatus:
    mapping = {
        UserStatus.ACTIVE: user_pb2.USER_STATUS_ACTIVE,
        UserStatus.DISABLED: user_pb2.USER_STATUS_DISABLED,
    }
    return mapping[status]


def to_grpc_employment_status(status: EmploymentStatus) -> user_pb2.EmploymentStatus:
    mapping = {
        EmploymentStatus.ON_DUTY: user_pb2.EMPLOYMENT_STATUS_ON_DUTY,
        EmploymentStatus.DISABLED: user_pb2.EMPLOYMENT_STATUS_DISABLED,
    }
    return mapping[status]


def to_domain_user_role(role: user_pb2.UserRole) -> UserRole:
    mapping: dict[user_pb2.UserRole, UserRole] = {
        user_pb2.USER_ROLE_WORKER: UserRole.WORKER,
        user_pb2.USER_ROLE_CUSTOMER_SERVICE: UserRole.CUSTOMER_SERVICE,
        user_pb2.USER_ROLE_OWNER: UserRole.OWNER,
    }
    if role not in mapping:
        raise ValidationError("invalid user role")
    return mapping[role]


def to_domain_employment_status(status: user_pb2.EmploymentStatus) -> EmploymentStatus:
    mapping: dict[user_pb2.EmploymentStatus, EmploymentStatus] = {
        user_pb2.EMPLOYMENT_STATUS_ON_DUTY: EmploymentStatus.ON_DUTY,
        user_pb2.EMPLOYMENT_STATUS_DISABLED: EmploymentStatus.DISABLED,
    }
    if status not in mapping:
        raise ValidationError("invalid employment status")
    return mapping[status]
