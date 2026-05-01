# ESP32-S3 Auth Device

Firmware for a one-button USB approval device for Aeon-V1 Layer 7.

The device does not execute actions and does not approve anything by itself. It only returns a physical approval message after the PC has sent a specific pending proposal id and the user holds the hardware button.

## Hardware

- ESP32-S3 board with native USB.
- One push button from `GPIO0` to `GND` using the internal pull-up. On many dev boards this is the built-in `BOOT` button.
- Optional status LED on `GPIO48`. Change `LED_PIN` in `src/main.cpp` if your board differs.

## Build And Flash

```bash
cd firmware/esp32s3-auth-device
pio run -t upload
pio device monitor
```

The PlatformIO config enables native USB CDC:

```ini
-DARDUINO_USB_MODE=1
-DARDUINO_USB_CDC_ON_BOOT=1
```

## USB Protocol

Messages are newline-delimited JSON over USB serial at `115200`.

Device announces itself:

```json
{"type":"hello","device":"aeon-v1-auth","version":"1.0.0","button_pin":0,"capabilities":["physical_approval","button_hold"]}
```

PC arms a specific approval request:

```json
{"type":"approval_request","id":"proposal-trace-id","summary":"Approve semantic memory write","expires_ms":30000}
```

Device confirms it is waiting for the button:

```json
{"type":"armed","id":"proposal-trace-id","expires_ms":30000}
```

Hold the button for one second to approve:

```json
{"type":"approval","id":"proposal-trace-id","approved":true,"method":"button_hold","held_ms":1004}
```

Other accepted host messages:

```json
{"type":"status"}
{"type":"cancel","id":"proposal-trace-id"}
{"type":"hello"}
```

## Aeon-V1 Integration

Use `ESP32S3AuthProvider` as the `ApprovalAgent` auth provider:

```python
from aeon_v1 import ApprovalAgent, Config, ESP32S3AuthProvider

agent = ApprovalAgent(
    Config(),
    auth_provider=ESP32S3AuthProvider(port="COM5"),
)
agent.process_queue()
```

If `port` is omitted, the provider scans serial ports for a `hello` response from `aeon-v1-auth`.

Install the optional PC-side serial dependency with:

```bash
pip install pyserial
```

## Safety Contract

- Approval is tied to one host-provided proposal id.
- Button presses are ignored unless a request is active.
- Requests expire automatically.
- A one-second hold is required to reduce accidental taps.
- The firmware emits approval records only; `ApprovalAgent` still owns proposal status changes and audit logging.
