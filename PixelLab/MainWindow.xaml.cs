using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using Grpc.Core;

namespace PixelLab;

public partial class MainWindow : Window
{
    private const string Port = "COM3";
    private int patternId = 0;
    private readonly DispatcherTimer continuousUpdateTimer;
    private readonly Brush blackBoardBackground;
    private CancellationTokenSource? cameraStreamingCancellation;
    private bool isSendingContinuousFrame;

    public MainWindow()
    {
        InitializeComponent();
        blackBoardBackground = BlackBoard.Background;
        BlackBoard.DefaultDrawingAttributes.Color = Colors.White;
        BlackBoard.DefaultDrawingAttributes.Width = 4;
        BlackBoard.DefaultDrawingAttributes.Height = 4;
        ThicknessSlider.ValueChanged += Thickness_ValueChanged;

        continuousUpdateTimer = new DispatcherTimer
        {
            Interval = TimeSpan.FromMilliseconds(250)
        };
        continuousUpdateTimer.Tick += ContinuousUpdateTimer_Tick;
    }

    private async void TestPatternButton_Click(object sender, RoutedEventArgs e)
    {
        var button = (Button)sender;
        button.IsEnabled = false;

        try
        {
            var bytesSent = await MatrixSenderService.SendTestPatternAsync(Port, patternId);
            MessageBox.Show($"Sent {bytesSent} RGB bytes to {Port}.");
        }
        catch (RpcException exception) when (exception.StatusCode == StatusCode.Unavailable)
        {
            MessageBox.Show(
                "Could not connect to the matrix sender gRPC service at 127.0.0.1:50051.\n"
                + "Start it with: python -m matrix_sender.server --port 50051\n\n"
                + exception.Status.Detail,
                "Connection failed",
                MessageBoxButton.OK,
                MessageBoxImage.Error);
        }
        catch (RpcException exception)
        {
            MessageBox.Show(
                $"The matrix sender request failed ({exception.StatusCode}): {exception.Status.Detail}",
                "Send failed",
                MessageBoxButton.OK,
                MessageBoxImage.Error);
        }
        finally
        {
            patternId++;
            button.IsEnabled = true;
        }
    }

    private async void SendInkCanvasButton_Click(object sender, RoutedEventArgs e)
    {
        var button = (Button)sender;
        button.IsEnabled = false;

        try
        {
            var (rgbFrame, width, height) = CaptureInkCanvas(BlackBoard);
            var bytesSent = await MatrixSenderService.SendFrameAsync(
                Port, rgbFrame, width, height);
        }
        catch (RpcException exception) when (exception.StatusCode == StatusCode.Unavailable)
        {
            MessageBox.Show(
                "Could not connect to the matrix sender gRPC service at 127.0.0.1:50051.\n"
                + "Start it with: python -m matrix_sender.server --port 50051\n\n"
                + exception.Status.Detail,
                "Connection failed",
                MessageBoxButton.OK,
                MessageBoxImage.Error);
        }
        catch (RpcException exception)
        {
            MessageBox.Show(
                $"The matrix sender request failed ({exception.StatusCode}): {exception.Status.Detail}",
                "Send failed",
                MessageBoxButton.OK,
                MessageBoxImage.Error);
        }
        finally
        {
            button.IsEnabled = true;
        }
    }

    private void ContinuousUpdates_Click(object sender, RoutedEventArgs e)
    {
        if (ContinuousUpdates.IsChecked == true)
        {
            continuousUpdateTimer.Start();
        }
        else
        {
            continuousUpdateTimer.Stop();
        }
    }

    private async void CameraStreaming_Checked(object sender, RoutedEventArgs e)
    {
        var cancellation = new CancellationTokenSource();
        cameraStreamingCancellation = cancellation;

        try
        {
            await foreach (var frame in MatrixSenderService.StreamCameraAsync(cancellation.Token))
            {
                if (cancellation.IsCancellationRequested)
                {
                    break;
                }

                var width = checked((int)frame.Width);
                var height = checked((int)frame.Height);
                var bitmap = BitmapSource.Create(
                    width,
                    height,
                    96,
                    96,
                    PixelFormats.Rgb24,
                    null,
                    frame.RgbFrame.ToByteArray(),
                    checked(width * 3));
                BlackBoard.Background = new ImageBrush(bitmap);
            }
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested)
        {
        }
        catch (RpcException exception)
            when (cancellation.IsCancellationRequested
                && exception.StatusCode == StatusCode.Cancelled)
        {
        }
        catch (RpcException exception)
        {
            MessageBox.Show(
                $"Camera streaming failed ({exception.StatusCode}): {exception.Status.Detail}",
                "Camera streaming failed",
                MessageBoxButton.OK,
                MessageBoxImage.Error);
        }
        catch (Exception exception)
        {
            MessageBox.Show(
                exception.Message,
                "Camera streaming failed",
                MessageBoxButton.OK,
                MessageBoxImage.Error);
        }
        finally
        {
            if (ReferenceEquals(cameraStreamingCancellation, cancellation))
            {
                cameraStreamingCancellation = null;
                CameraStreaming.IsChecked = false;
            }

            cancellation.Dispose();
        }
    }

    private void CameraStreaming_Unchecked(object sender, RoutedEventArgs e)
    {
        cameraStreamingCancellation?.Cancel();
    }

    private void Thickness_ValueChanged(
        object sender, RoutedPropertyChangedEventArgs<double> e)
    {
        BlackBoard.DefaultDrawingAttributes.Width = ThicknessSlider.Value;
        BlackBoard.DefaultDrawingAttributes.Height = ThicknessSlider.Value;
        ThicknessValue.Text = ((int)ThicknessSlider.Value).ToString();
    }

    private void DrawingColorPicker_SelectedColorChanged(
        object sender, RoutedPropertyChangedEventArgs<Color?> e)
    {
        if (e.NewValue is Color color)
        {
            BlackBoard.DefaultDrawingAttributes.Color = color;
        }
    }

    private async void ContinuousUpdateTimer_Tick(object? sender, EventArgs e)
    {
        if (isSendingContinuousFrame)
        {
            return;
        }

        isSendingContinuousFrame = true;
        try
        {
            var (rgbFrame, width, height) = CaptureInkCanvas(BlackBoard);
            await MatrixSenderService.SendFrameAsync(Port, rgbFrame, width, height);
        }
        catch (RpcException exception) when (exception.StatusCode == StatusCode.Unavailable)
        {
            continuousUpdateTimer.Stop();
            ContinuousUpdates.IsChecked = false;
            MessageBox.Show(
                "Could not connect to the matrix sender gRPC service at 127.0.0.1:50051.\n"
                + "Start it with: python -m matrix_sender.server --port 50051\n\n"
                + exception.Status.Detail,
                "Connection failed",
                MessageBoxButton.OK,
                MessageBoxImage.Error);
        }
        catch (RpcException exception)
        {
            continuousUpdateTimer.Stop();
            ContinuousUpdates.IsChecked = false;
            MessageBox.Show(
                $"The matrix sender request failed ({exception.StatusCode}): {exception.Status.Detail}",
                "Send failed",
                MessageBoxButton.OK,
                MessageBoxImage.Error);
        }
        catch (Exception exception)
        {
            continuousUpdateTimer.Stop();
            ContinuousUpdates.IsChecked = false;
            MessageBox.Show(
                exception.Message,
                "Continuous update failed",
                MessageBoxButton.OK,
                MessageBoxImage.Error);
        }
        finally
        {
            isSendingContinuousFrame = false;
        }
    }

    private void ClearDrawingButton_Click(object sender, RoutedEventArgs e)
    {
        BlackBoard.Strokes.Clear();
    }

    private static (byte[] RgbFrame, int Width, int Height) CaptureInkCanvas(InkCanvas canvas)
    {
        canvas.UpdateLayout();
        var width = (int)Math.Ceiling(canvas.ActualWidth);
        var height = (int)Math.Ceiling(canvas.ActualHeight);

        if (width <= 0 || height <= 0)
        {
            throw new InvalidOperationException("The InkCanvas has no renderable size.");
        }

        var bitmap = new RenderTargetBitmap(width, height, 96, 96, PixelFormats.Pbgra32);

        var visual = new DrawingVisual();
        using (var context = visual.RenderOpen())
        {
            context.DrawRectangle(canvas.Background, null, new Rect(0, 0, width, height));
            canvas.Strokes.Draw(context);
        }

        bitmap.Render(visual);

        var bgraFrame = new byte[width * height * 4];
        bitmap.CopyPixels(bgraFrame, width * 4, 0);

        var rgbFrame = new byte[width * height * 3];
        for (var pixel = 0; pixel < width * height; pixel++)
        {
            var sourceIndex = pixel * 4;
            var targetIndex = pixel * 3;
            rgbFrame[targetIndex] = bgraFrame[sourceIndex + 2];
            rgbFrame[targetIndex + 1] = bgraFrame[sourceIndex + 1];
            rgbFrame[targetIndex + 2] = bgraFrame[sourceIndex];
        }

        return (rgbFrame, width, height);
    }
}