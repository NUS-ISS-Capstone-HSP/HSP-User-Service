from hsp_user_service.domain.models import EchoRecord, WorkerProfile
from hsp_user_service.service.auth_service import AuthenticatedIdentity
from hsp_user_service.transport.http.schemas import (
    EchoRecordResponse,
    UserResponse,
    WorkerProfileResponse,
)


def to_http_response(record: EchoRecord) -> EchoRecordResponse:
    return EchoRecordResponse(
        id=record.id,
        message=record.message,
        source=record.source.value,
        created_at=record.created_at.isoformat(),
    )


def to_user_response(identity: AuthenticatedIdentity) -> UserResponse:
    return UserResponse(
        id=identity.user.id,
        email=identity.user.email,
        role=identity.user.role,
        status=identity.user.status,
        worker_profile=to_worker_profile_response(identity.worker_profile),
    )


def to_worker_profile_response(
    profile: WorkerProfile | None,
) -> WorkerProfileResponse | None:
    if profile is None:
        return None
    return WorkerProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        worker_no=profile.worker_no,
        display_name=profile.display_name,
        employment_status=profile.employment_status,
    )
