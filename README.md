# PixelLab RGB matrix

PixelLab is a Windows WPF drawing app that sends RGB images to a 64×64 LED
matrix through a local Python gRPC service and an ESP32 serial receiver.

## Requirements

- Windows and the .NET 8 SDK
- Python 3.10 or later
- An ESP32 flashed with [`ESP32MatrixReceiver.ino`](./ESP32MatrixReceiver.ino)
- The `ESP32-HUB75-MatrixPanel-I2S-DMA` Arduino library

The WPF project restores its NuGet dependencies, including the Extended WPF
Toolkit ColorPicker, when it is built.

## Run the sender service

From the repository root, create and activate a Python environment, then
install the project:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Connect the ESP32 and start the service in that terminal:

```powershell
python -m matrix_sender.server --port 50051
```

The gRPC service binds to `127.0.0.1` by default. It lists serial ports and
sends frames over the selected port at 115200 baud. The WPF app currently uses
`COM3`; change the `Port` constant in
[`PixelLab/MainWindow.xaml.cs`](./PixelLab/MainWindow.xaml.cs) to match your
ESP32's port.

## Run the WPF app

In another terminal, from the repository root:

```powershell
dotnet run --project .\PixelLab\PixelLab.csproj
```

Draw on the InkCanvas, choose a color and stroke thickness, then click **Send
Drawing**. **Continuously Updates RGB screen** sends the current drawing
repeatedly while enabled. **Test Pattern** sends a generated image, and **Clear
Drawing** clears the canvas.

The app captures the canvas as row-major RGB bytes and sends those bytes with
the source width and height. The Python service validates the frame, center
pads it to a square using black, downsamples each block to its most common
color, and sends a 64×64 RGB frame to the ESP32. Thin strokes can be lost when
they are outnumbered by background pixels in a downsampling block.

## Protocol and generated bindings

The gRPC API is defined in
[`matrix_sender/matrix_sender.proto`](./matrix_sender/matrix_sender.proto).
`SendFrame` accepts a port, image width and height, and exactly
`width × height × 3` row-major RGB bytes.

The Python protobuf bindings are checked in. After changing the `.proto`, from
the repository root regenerate them with:

```powershell
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. matrix_sender/matrix_sender.proto
```

The WPF project's C# bindings are generated during its build.
