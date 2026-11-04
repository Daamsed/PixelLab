import argparse
from concurrent import futures

import grpc

from . import matrix_sender_pb2, matrix_sender_pb2_grpc
from .sender import MatrixSender, resize_rgb_frame


class MatrixSenderService(matrix_sender_pb2_grpc.MatrixSenderServicer):
    def __init__(self, sender: MatrixSender | None = None):
        self._sender = sender if sender is not None else MatrixSender()

    def close(self) -> None:
        self._sender.close()

    def ListPorts(self, request, context):
        try:
            return matrix_sender_pb2.ListPortsResponse(ports=self._sender.list_ports())
        except RuntimeError as exc:
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, str(exc))

    def SendFrame(self, request, context):
        if not request.port.strip():
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "A serial port must be specified.")

        try:
            frame = resize_rgb_frame(request.rgb_frame, request.width, request.height)
            bytes_sent = self._sender.send_frame(request.port, frame)
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        except (OSError, RuntimeError) as exc:
            context.abort(grpc.StatusCode.UNAVAILABLE, str(exc))

        return matrix_sender_pb2.SendFrameResponse(bytes_sent=bytes_sent)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the RGB matrix gRPC sender.")
    parser.add_argument("--host", default="127.0.0.1", help="Interface to bind (default: localhost)")
    parser.add_argument("--port", type=int, default=50051, help="TCP port to bind")
    args = parser.parse_args()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    service = MatrixSenderService()
    matrix_sender_pb2_grpc.add_MatrixSenderServicer_to_server(service, server)
    address = f"{args.host}:{args.port}"
    if server.add_insecure_port(address) == 0:
        raise RuntimeError(f"Could not bind gRPC server to {address}.")

    server.start()
    print(f"Matrix sender gRPC service listening on {address}")
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(grace=0).wait()
    finally:
        service.close()


if __name__ == "__main__":
    main()
