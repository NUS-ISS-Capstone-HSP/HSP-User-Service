import grpc

from hsp_user_service.config import Settings
from hsp_user_service.service.auth_service import AuthService
from hsp_user_service.service.echo_service import EchoService
from hsp_user_service.transport.grpc.service import EchoGrpcService, UserAuthGrpcService
from rpc.echo.v1 import echo_pb2_grpc
from rpc.user.v1 import user_pb2_grpc


def build_grpc_server(
    settings: Settings,
    echo_service: EchoService,
    auth_service: AuthService,
) -> grpc.aio.Server:
    server = grpc.aio.server()
    echo_pb2_grpc.add_EchoServiceServicer_to_server(EchoGrpcService(echo_service), server)
    user_pb2_grpc.add_UserAuthServiceServicer_to_server(UserAuthGrpcService(auth_service), server)
    server.add_insecure_port(f"{settings.grpc_host}:{settings.grpc_port}")
    return server
