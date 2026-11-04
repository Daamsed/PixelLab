import struct
import threading
import time
from pathlib import Path
from typing import Callable, Protocol

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None

BAUD = 115200
WIDTH = 64
HEIGHT = 64
PIXELS = WIDTH * HEIGHT
FRAME_BYTES = PIXELS * 3


class SerialConnection(Protocol):
    def write(self, data: bytes) -> int: ...

    def flush(self) -> None: ...

    def close(self) -> None: ...


def list_serial_ports() -> list[str]:
    if list_ports is None:
        raise RuntimeError("pyserial is not installed. Install it with: pip install pyserial")
    return [port.device for port in list_ports.comports()]


def make_test_pattern() -> bytes:
    """Create a 64x64 RGB test image in row-major order."""
    frame = bytearray(FRAME_BYTES)
    index = 0
    for y in range(HEIGHT):
        for x in range(WIDTH):
            frame[index:index + 3] = bytes(
                ((x * 4) % 256, (y * 4) % 256, ((x + y) * 2) % 256)
            )
            index += 3
    return bytes(frame)


def resize_rgb_frame(frame: bytes, width: int, height: int) -> bytes:
    """Center-pad an RGB image to a square and downsample it to the matrix size."""
    if width <= 0 or height <= 0:
        raise ValueError("Image width and height must be greater than zero.")

    expected_bytes = width * height * 3
    if len(frame) != expected_bytes:
        raise ValueError(
            f"Expected {expected_bytes} bytes for {width}x{height} RGB, "
            f"got {len(frame)} bytes"
        )

    block_size = (max(width, height) + WIDTH - 1) // WIDTH
    square_size = block_size * WIDTH
    offset_x = (square_size - width) // 2
    offset_y = (square_size - height) // 2
    color_counts = [dict() for _ in range(PIXELS)]

    for y in range(height):
        output_y = (y + offset_y) // block_size
        for x in range(width):
            output_x = (x + offset_x) // block_size
            input_index = (y * width + x) * 3
            color = (frame[input_index], frame[input_index + 1], frame[input_index + 2])
            counts = color_counts[output_y * WIDTH + output_x]
            counts[color] = counts.get(color, 0) + 1

    output = bytearray(FRAME_BYTES)
    block_area = block_size * block_size
    for index, counts in enumerate(color_counts):
        if not counts:
            color = (0, 0, 0)
        else:
            padding_pixels = block_area - sum(counts.values())
            if padding_pixels:
                counts[(0, 0, 0)] = counts.get((0, 0, 0), 0) + padding_pixels
            color = max(counts, key=counts.get)
        output_index = index * 3
        output[output_index:output_index + 3] = bytes(color)

    return bytes(output)


def open_serial_port(port: str) -> SerialConnection:
    if serial is None:
        raise RuntimeError("pyserial is not installed. Install it with: pip install pyserial")

    connection = serial.Serial(
        None,
        BAUD,
        timeout=0.2,
        write_timeout=2,
        rtscts=False,
        dsrdtr=False,
    )
    connection.port = port
    connection.dtr = False
    connection.rts = False
    connection.open()
    time.sleep(3.0)
    return connection


def send_frame(connection: SerialConnection, frame: bytes) -> None:
    if len(frame) != FRAME_BYTES:
        raise ValueError(
            f"Expected {FRAME_BYTES} bytes for {WIDTH}x{HEIGHT} RGB, got {len(frame)} bytes"
        )

    packet = struct.pack("<I", len(frame)) + frame
    written = connection.write(packet)
    connection.flush()
    if written != len(packet):
        raise IOError(f"Only wrote {written} of {len(packet)} packet bytes.")


class MatrixSender:
    """Keep the selected serial port open until it is changed or closed."""

    def __init__(
        self,
        serial_opener: Callable[[str], SerialConnection] = open_serial_port,
    ):
        self._serial_opener = serial_opener
        self._connection: SerialConnection | None = None
        self._port: str | None = None
        self._lock = threading.Lock()

    def list_ports(self) -> list[str]:
        return list_serial_ports()

    def send_frame(self, port: str, frame: bytes) -> int:
        if not port or not port.strip():
            raise ValueError("A serial port must be specified.")
        if len(frame) != FRAME_BYTES:
            raise ValueError(
                f"Expected {FRAME_BYTES} bytes for {WIDTH}x{HEIGHT} RGB, got {len(frame)} bytes"
            )

        with self._lock:
            connection = self._connection
            if self._port != port or connection is None:
                self._close_connection()
                connection = self._serial_opener(port)
                self._connection = connection
                self._port = port
            try:
                send_frame(connection, frame)
            except OSError:
                self._close_connection()
                raise
        return len(frame)

    def send_from_file(self, port: str, path: str | Path) -> int:
        return self.send_frame(port, Path(path).read_bytes())

    def close(self) -> None:
        with self._lock:
            self._close_connection()

    def _close_connection(self) -> None:
        connection = self._connection
        self._connection = None
        self._port = None
        if connection is not None:
            connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


def send_rgb_frame(port: str, frame: bytes) -> None:
    with MatrixSender() as sender:
        sender.send_frame(port, frame)


def send_from_file(port: str, path: str | Path) -> None:
    with MatrixSender() as sender:
        sender.send_from_file(port, path)
