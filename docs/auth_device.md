# Dedicated Auth Device

Aeon-V1 Layer 7 exposes `AuthProvider` as the plug-in point for hardware approval. The ESP32-S3 auth device in `firmware/esp32s3-auth-device/` fills that planned role with a one-button USB token.

The device is deliberately small: the PC sends one pending staging proposal id over USB serial, and the device emits an approval JSON line only after the hardware button is held for one second. It never receives secrets, never executes commands, and never approves unarmed requests.

## Flow

1. `ApprovalAgent` loads a staging proposal with status `approved_for_review`.
2. `ESP32S3AuthProvider` sends `approval_request` to the USB device with the exact `trace_id` or proposal id.
3. The operator reviews the PC-side prompt and holds the ESP32-S3 button.
4. The firmware returns `approval` for the same id.
5. `ApprovalAgent` marks the proposal `approved_for_commit` and writes the normal audit log entry.

## Usage

```python
from aeon_v1 import ApprovalAgent, Config, ESP32S3AuthProvider

config = Config()
auth = ESP32S3AuthProvider(port="COM5")  # omit port for auto-discovery
agent = ApprovalAgent(config, auth_provider=auth)
agent.process_queue()
```

Install the optional serial dependency:

```bash
pip install pyserial
```

## Protocol Shape

Example host request:

```json
{"type":"approval_request","id":"proposal-trace-id","summary":"semantic memory write","expires_ms":30000}
```

Example device approval:

```json
{"type":"approval","id":"proposal-trace-id","approved":true,"method":"button_hold","held_ms":1007}
```

This preserves the Layer 7 safety rule: there is still no auto-approval path. The hardware token is only a physical human decision source behind `AuthProvider`.
