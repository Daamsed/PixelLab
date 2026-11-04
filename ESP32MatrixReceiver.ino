#include <ESP32-HUB75-MatrixPanel-I2S-DMA.h>

const int panelResX = 64;
const int panelResY = 64;
const int panel_chain = 1;

const uint32_t kPixels = 64 * 64;
const uint32_t kRgbBytesPerPixel = 3;
const uint32_t kFrameBytes = kPixels * kRgbBytesPerPixel;

MatrixPanel_I2S_DMA *dma_display = nullptr;
uint16_t rgb565Frame[kPixels];

// Only errors are shown on the matrix. Normal reception leaves the frame visible.
// 1 = empty packet
// 2 = packet length exceeds the frame buffer
// 3 = complete packet is not a 64x64 RGB frame
// 11 = packet reception timed out
const uint32_t kRxTimeoutMs = 3000;

struct RxState {
  uint8_t lengthBuf[4] = {0, 0, 0, 0};
  int lengthIndex = 0;
  uint32_t expectedLen = 0;
  uint32_t receivedLen = 0;
  uint32_t lastByteAt = 0;
  uint8_t buffer[kFrameBytes] = {0};
} rx;

void displaySetup() {
  HUB75_I2S_CFG mxconfig(panelResX, panelResY, panel_chain);
  mxconfig.gpio.e = 18;
  mxconfig.clkphase = false;
  mxconfig.driver = HUB75_I2S_CFG::FM6124;

  dma_display = new MatrixPanel_I2S_DMA(mxconfig);
  dma_display->begin();
  dma_display->setBrightness8(180);
  dma_display->fillScreen(dma_display->color565(0, 0, 0));
}

uint16_t rgb888ToRgb565(uint8_t r, uint8_t g, uint8_t b) {
  return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3);
}

void showStatusMessage(const char *label, int code) {
  dma_display->fillScreen(dma_display->color565(0, 0, 0));
  dma_display->setTextColor(dma_display->color565(255, 255, 255));
  dma_display->setTextSize(2);
  dma_display->setCursor(4, 6);
  dma_display->print(label);

  dma_display->setTextSize(3);
  dma_display->setCursor(20, 30);
  dma_display->print(code);
}

void showErrorCode(int code) {
  switch (code) {
    case 1: showStatusMessage("EMPTY", 1); break;
    case 2: showStatusMessage("BIG", 2); break;
    case 3: showStatusMessage("SIZE", 3); break;
    case 11: showStatusMessage("TIME", 11); break;
  }
}

bool readFrameFromSerial(uint8_t *outBuffer, uint32_t maxLen, uint32_t &actualLen) {
  actualLen = 0;

  if ((rx.lengthIndex > 0 || rx.expectedLen > 0)
      && millis() - rx.lastByteAt > kRxTimeoutMs) {
    showErrorCode(11);
    rx.lengthIndex = 0;
    rx.expectedLen = 0;
    rx.receivedLen = 0;
  }

  while (Serial.available() > 0) {
    uint8_t ch = (uint8_t)Serial.read();
    rx.lastByteAt = millis();

    if (rx.expectedLen == 0) {
      rx.lengthBuf[rx.lengthIndex++] = ch;
      if (rx.lengthIndex == 4) {
        rx.expectedLen = (uint32_t)rx.lengthBuf[0]
                      | ((uint32_t)rx.lengthBuf[1] << 8)
                      | ((uint32_t)rx.lengthBuf[2] << 16)
                      | ((uint32_t)rx.lengthBuf[3] << 24);
        rx.lengthIndex = 0;
        rx.receivedLen = 0;

        if (rx.expectedLen == 0) {
          showErrorCode(1);
          actualLen = 0;
          return true;
        }

        if (rx.expectedLen > maxLen) {
          showErrorCode(2);
          rx.expectedLen = 0;
          return false;
        }
      }
      continue;
    }

    rx.buffer[rx.receivedLen++] = ch;
    if (rx.receivedLen >= rx.expectedLen) {
      memcpy(outBuffer, rx.buffer, rx.expectedLen);
      actualLen = rx.expectedLen;
      rx.expectedLen = 0;
      rx.receivedLen = 0;
      return true;
    }
  }

  return false;
}

void drawRgbFrame(const uint8_t *rgb888Buffer, uint32_t len) {
  if (len != kFrameBytes) {
    showErrorCode(3);
    return;
  }

  for (uint32_t i = 0; i < kPixels; ++i) {
    uint32_t base = i * 3;
    uint8_t r = rgb888Buffer[base + 0];
    uint8_t g = rgb888Buffer[base + 1];
    uint8_t b = rgb888Buffer[base + 2];
    rgb565Frame[i] = rgb888ToRgb565(r, g, b);
  }

  dma_display->drawRGBBitmap(0, 0, rgb565Frame, 64, 64);
}

void setup() {
  Serial.setRxBufferSize(16 * 1024);
  Serial.begin(115200);
  displaySetup();
}

void loop() {
  static uint8_t frame[kFrameBytes] = {0};
  uint32_t actualLen = 0;

  if (readFrameFromSerial(frame, sizeof(frame), actualLen)) {
    if (actualLen > 0) {
      drawRgbFrame(frame, actualLen);
    }
  }
}
