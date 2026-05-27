from pathlib import Path

import pytest

from hsp_user_service.domain.models import EmploymentStatus, SourceType, UserRole, UserStatus
from hsp_user_service.infrastructure.db import (
    create_engine,
    create_session_factory,
    init_db,
)
from hsp_user_service.repository.mysql import SQLAlchemyEchoRepository, SQLAlchemyUserRepository


@pytest.mark.asyncio
async def test_sqlalchemy_repository_create_and_get(tmp_path: Path) -> None:
    db_file = tmp_path / "echo.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_file}")
    await init_db(engine)

    repository = SQLAlchemyEchoRepository(create_session_factory(engine))

    created = await repository.create("repo-message", SourceType.GRPC)
    fetched = await repository.get_by_id(created.id)

    assert created.message == "repo-message"
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.source == SourceType.GRPC

    await engine.dispose()


@pytest.mark.asyncio
async def test_sqlalchemy_repository_get_missing_returns_none(tmp_path: Path) -> None:
    db_file = tmp_path / "echo.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_file}")
    await init_db(engine)

    repository = SQLAlchemyEchoRepository(create_session_factory(engine))

    fetched = await repository.get_by_id("missing-id")
    assert fetched is None

    await engine.dispose()


@pytest.mark.asyncio
async def test_sqlalchemy_user_repository_updates_worker_profile(tmp_path: Path) -> None:
    db_file = tmp_path / "user.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_file}")
    await init_db(engine)

    repository = SQLAlchemyUserRepository(create_session_factory(engine))
    user = await repository.create_user(
        email="worker@example.com",
        password_hash="hashed",
        role=UserRole.WORKER,
        status=UserStatus.ACTIVE,
    )
    created_profile = await repository.create_worker_profile(
        user_id=user.id,
        worker_no="WK00000001",
        display_name="worker-one",
        employment_status=EmploymentStatus.ON_DUTY,
    )

    updated_profile = await repository.update_worker_profile_display_name(
        user_id=user.id,
        display_name="worker-renamed",
    )

    assert created_profile.display_name == "worker-one"
    assert updated_profile is not None
    assert updated_profile.display_name == "worker-renamed"
    assert updated_profile.updated_at >= created_profile.updated_at

    await engine.dispose()


@pytest.mark.asyncio
async def test_sqlalchemy_user_repository_update_missing_worker_profile_returns_none(
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "user.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_file}")
    await init_db(engine)

    repository = SQLAlchemyUserRepository(create_session_factory(engine))

    updated_profile = await repository.update_worker_profile_display_name(
        user_id=999,
        display_name="missing",
    )

    assert updated_profile is None

    await engine.dispose()
