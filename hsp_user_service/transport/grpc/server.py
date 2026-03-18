import grpc

from hsp_user_service.config import Settings
from hsp_user_service.service.echo_service import EchoService
from hsp_user_service.transport.grpc.service import EchoGrpcService
from rpc.echo.v1 import echo_pb2_grpc


def build_grpc_server(settings: Settings, echo_service: EchoService) -> grpc.aio.Server:
    server = grpc.aio.server()
    echo_pb2_grpc.add_EchoServiceServicer_to_server(EchoGrpcService(echo_service), server)
    server.add_insecure_port(f"{settings.grpc_host}:{settings.grpc_port}")
    return server
