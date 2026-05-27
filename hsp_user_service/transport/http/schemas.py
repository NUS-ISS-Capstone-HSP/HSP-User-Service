from pydantic import BaseModel, ConfigDict, Field

from hsp_user_service.domain.models import EmploymentStatus, UserRole, UserStatus


class CreateEchoRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"message": "Hello from HTTP"}},
    )

    message: str = Field(
        min_length=1,
        max_length=2048,
        description="Message content to be stored as an echo record.",
    )


class EchoRecordResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "6f88f9f2-65fd-4ef7-80de-2c96d8ab7b5b",
                "message": "Hello from HTTP",
                "source": "HTTP",
                "created_at": "2026-03-18T12:34:56+00:00",
            }
        },
    )

    id: str = Field(description="Echo record id (UUID).")
    message: str = Field(description="Stored message.")
    source: str = Field(description="Record source. HTTP or GRPC.")
    created_at: str = Field(description="Creation time in ISO-8601 format.")


class WorkerProfileResponse(BaseModel):
    id: int = Field(description="Worker profile id.")
    user_id: int = Field(description="Bound user id.")
    worker_no: str = Field(description="Worker number.")
    display_name: str = Field(description="Worker display name.")
    employment_status: EmploymentStatus = Field(description="Worker employment status.")


class UserResponse(BaseModel):
    id: int = Field(description="User id.")
    email: str = Field(description="Email login identifier.")
    role: UserRole = Field(description="User role.")
    status: UserStatus = Field(description="User account status.")
    worker_profile: WorkerProfileResponse | None = Field(
        default=None,
        description="Worker profile if role is WORKER.",
    )


class RegisterRequest(BaseModel):
    email: str = Field(
        min_length=3,
        max_length=255,
        description="User email.",
    )
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Raw password. Will be hashed in storage.",
    )
    role: UserRole = Field(description="User role.")
    worker_display_name: str | None = Field(
        default=None,
        max_length=128,
        description="Required when role is WORKER.",
    )


class RegisterResponse(BaseModel):
    user: UserResponse = Field(description="Created user.")


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255, description="User email.")
    password: str = Field(min_length=1, max_length=128, description="Raw password.")


class LoginResponse(BaseModel):
    access_token: str = Field(description="JWT access token.")
    token_type: str = Field(description="Token type, normally Bearer.")
    expires_in: int = Field(description="Token expiration in seconds.")
    user: UserResponse = Field(description="Current user profile.")


class LogoutResponse(BaseModel):
    message: str = Field(description="Logout result.")


class MeResponse(BaseModel):
    user: UserResponse = Field(description="Current user profile.")


class UpdateWorkerStatusRequest(BaseModel):
    employment_status: EmploymentStatus = Field(description="Target worker employment status.")


class UpdateWorkerStatusResponse(BaseModel):
    user: UserResponse = Field(description="Updated worker user profile.")


class UpdateWorkerProfileRequest(BaseModel):
    display_name: str = Field(
        min_length=1,
        max_length=128,
        description="Worker display name.",
    )


class WorkerProfileManagementResponse(BaseModel):
    worker_profile: WorkerProfileResponse = Field(description="Worker profile.")
