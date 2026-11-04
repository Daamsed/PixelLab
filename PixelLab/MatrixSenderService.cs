using Google.Protobuf;
using Grpc.Net.Client;
using MatrixSender;

namespace PixelLab;

internal static class MatrixSenderService
{
    private const int Width = 256;
    private const int Height = 256;

    public static async Task<uint> SendTestPatternAsync(string port, int patternId = 0)
    {
        return await SendFrameAsync(port, CreateTestPattern(patternId), Width, Height);
    }

    public static async Task<uint> SendFrameAsync(
        string port, byte[] rgbFrame, int width, int height)
    {
        using var channel = GrpcChannel.ForAddress("http://127.0.0.1:50051");
        var client = new global::MatrixSender.MatrixSender.MatrixSenderClient(channel);
        var response = await client.SendFrameAsync(new SendFrameRequest
        {
            Port = port,
            RgbFrame = ByteString.CopyFrom(rgbFrame),
            Width = (uint)width,
            Height = (uint)height
        });

        return response.BytesSent;
    }

    private static byte[] CreateTestPattern(int patternId)
    {
        var frame = new byte[Width * Height * 3];
        var index = 0;
    
        switch (patternId%2)
        {
            case 0:
                // Create a simple test pattern
                for (var y = 0; y < Height; y++)
                {
                    for (var x = 0; x < Width; x++)
                    {
                        frame[index++] = (byte)(x * 4);
                        frame[index++] = (byte)(y * 4);
                        frame[index++] = (byte)((x + y) * 2);
                    }
                }
                break;
            case 1:
                // Create a simple test pattern
                for (var y = 0; y < Height; y++)
                {
                    for (var x = 0; x < Width; x++)
                    {
                        frame[index++] = (byte)(Math.Abs(x - Width / 2) * 4);
                        frame[index++] = (byte)(Math.Abs(y - Height / 2) * 4);
                        frame[index++] = (byte)(Math.Abs(x + y - Width) * 2);
                    }
                }
                break;
            // Add more cases for different patterns
        }

        return frame;
    }
}
