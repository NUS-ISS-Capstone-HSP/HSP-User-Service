from dataclasses import dataclass

import grpc
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from hsp_user_service.config import Settings, get_settings
from hsp_user_service.infrastructure.db import (
    create_engine,
    create_session_factory,
    init_db,
)
from hsp_user_service.repository.in_memory import InMemoryEchoRepository, InMemoryUserRepository
from hsp_user_service.repository.interfaces import EchoRepository, UserRepository
from hsp_user_service.repository.mysql import SQLAlchemyEchoRepository, SQLAlchemyUserRepository
from hsp_user_service.service.auth_service import AuthService
from hsp_user_service.service.echo_service import EchoService
from hsp_user_service.transport.grpc.server import build_grpc_server
from hsp_user_service.transport.http.app import create_http_app


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    engine: AsyncEngine | None
    session_factory: async_sessionmaker[AsyncSession] | None
    echo_repository: EchoRepository
    user_repository: UserRepository
    echo_service: EchoService
    auth_service: AuthService
    http_app: FastAPI
    grpc_server: grpc.aio.Server


async def build_container() -> AppContainer:
    settings = get_settings()
    echo_repository: EchoRepository
    user_repository: UserRepository

    if settings.use_mock_repository:
        engine = None
        session_factory = None
        echo_repository = InMemoryEchoRepository()
        user_repository = InMemoryUserRepository()
    else:
        engine = create_engine(settings.mysql_dsn)
        await init_db(engine)
        session_factory = create_session_factory(engine)
        echo_repository = SQLAlchemyEchoRepository(session_factory)
        user_repository = SQLAlchemyUserRepository(session_factory)

    echo_service = EchoService(echo_repository)
    auth_service = AuthService(
        repository=user_repository,
        jwt_secret=settings.jwt_secret,
        jwt_issuer=settings.jwt_issuer,
        jwt_audience=settings.jwt_audience,
        access_token_ttl_seconds=settings.access_token_ttl_seconds,
    )
    http_app = create_http_app(echo_service, auth_service)
    grpc_server = build_grpc_server(settings, echo_service, auth_service)

    return AppContainer(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        echo_repository=echo_repository,
        user_repository=user_repository,
        echo_service=echo_service,
        auth_service=auth_service,
        http_app=http_app,
        grpc_server=grpc_server,
    )
