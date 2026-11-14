import argparse
from concurrent import futures
import threading
import time

import cv2
import grpc

from . import matrix_sender_pb2, matrix_sender_pb2_grpc
from .sender import MatrixSender, resize_rgb_frame

CAMERA_WIDTH = 256
CAMERA_HEIGHT = 256
CAMERA_FPS = 10


class MatrixSenderService(matrix_sender_pb2_grpc.MatrixSenderServicer):
    def __init__(self, sender: MatrixSender | None = None):
        self._sender = sender if sender is not None else MatrixSender()
        self._camera_lock = threading.Lock()

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

    def StreamCamera(self, request, context):
        if not self._camera_lock.acquire(blocking=False):
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, "A camera stream is already active.")

        camera = None
        try:
            camera = cv2.VideoCapture(0)
            if not camera.isOpened():
                context.abort(
                    grpc.StatusCode.FAILED_PRECONDITION,
                    "Could not open the USB camera at index 0.",
                )

            camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

            while context.is_active():
                started_at = time.monotonic()
                captured, frame = camera.read()
                if not captured:
                    context.abort(grpc.StatusCode.UNAVAILABLE, "Could not capture a camera frame.")

                height, width = frame.shape[:2]
                square_size = min(width, height)
                left = (width - square_size) // 2
                top = (height - square_size) // 2
                center_square = frame[
                    top:top + square_size,
                    left:left + square_size,
                ]
                resized = cv2.resize(
                    center_square,
                    (CAMERA_WIDTH, CAMERA_HEIGHT),
                    interpolation=cv2.INTER_AREA,
                )
                rgb_frame = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
                yield matrix_sender_pb2.CameraFrame(
                    rgb_frame=rgb_frame.tobytes(),
                    width=CAMERA_WIDTH,
                    height=CAMERA_HEIGHT,
                )

                remaining = (1 / CAMERA_FPS) - (time.monotonic() - started_at)
                if remaining > 0:
                    time.sleep(remaining)
        finally:
            try:
                if camera is not None:
                    camera.release()
            finally:
                self._camera_lock.release()


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
