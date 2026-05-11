from dataclasses import dataclass

from hsp_user_service.domain.models import EmploymentStatus, UserRole, UserStatus
from hsp_user_service.repository.interfaces import UserRepository


@dataclass(frozen=True, slots=True)
class SeedUser:
    email: str
    password_hash: str
    role: UserRole
    worker_display_name: str | None = None


DEFAULT_SEED_USERS: tuple[SeedUser, ...] = (
    SeedUser(
        email="admin001@hsp.local",
        password_hash="$2b$12$QOp1c83Eh4B78aV6MxRtJuY1WgSZRUQnVhUJUuub/hgQghhLwJoES",
        role=UserRole.OWNER,
    ),
    SeedUser(
        email="cs001@hsp.local",
        password_hash="$2b$12$tUP1LhCnHYikguyA5gQf.OmOG1vKOPeBg6l0R0I6zWB.4xJJj51B.",
        role=UserRole.CUSTOMER_SERVICE,
    ),
    SeedUser(
        email="worker.test@example.com",
        password_hash="$2b$12$XHzufjFvCGqMPnzTzqYzWeZoPeuw/bnbruijmm96A5iEaqbI5NZra",
        role=UserRole.WORKER,
        worker_display_name="worker",
    ),
)


async def seed_default_users(repository: UserRepository) -> None:
    for seed_user in DEFAULT_SEED_USERS:
        existing = await repository.get_user_by_email(seed_user.email)
        if existing is not None:
            continue

        user = await repository.create_user(
            email=seed_user.email,
            password_hash=seed_user.password_hash,
            role=seed_user.role,
            status=UserStatus.ACTIVE,
        )
        if seed_user.role == UserRole.WORKER:
            await repository.create_worker_profile(
                user_id=user.id,
                worker_no=f"WK{user.id:08d}",
                display_name=seed_user.worker_display_name or seed_user.email,
                employment_status=EmploymentStatus.ON_DUTY,
            )
