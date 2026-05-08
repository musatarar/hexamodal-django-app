# Hexamodal

A Django REST Framework application that ingests IoT device payloads, decodes sensor data, and tracks device status.

---

## Prerequisites

- Python 3.9+
- pip

---

## Setup

**1. Clone and create a virtual environment**
```bash
git clone <repo-url>
cd Hexamodal
python -m venv venv
source venv/bin/activate
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Configure environment variables**

Create a `.env` file in the project root:
```
AUTH_TOKEN=your-secret-token
```

**4. Run migrations**
```bash
python manage.py migrate
```

**5. Start the development server**
```bash
python manage.py runserver
```

---

## API

All endpoints require an `AUTH_TOKEN` header matching the value set in `.env`.

### POST `/api/payload/`
Ingest a payload from an IoT device.

**Request**
```json
{
  "fCnt": 100,
  "devEUI": "abcdabcdabcdabcd",
  "data": "AQ==",
  "rxInfo": [{"gatewayID": "1234123412341234", "rssi": -57}],
  "txInfo": {"frequency": 86810000}
}
```

**Response `201`** — new payload accepted
```json
{
  "devEUI": "abcdabcdabcdabcd",
  "fCnt": 100,
  "data": "01",
  "passing": true
}
```

**Response `200`** — duplicate payload (fCnt already seen)
```json
{ "status": "duplicate" }
```

- `data` is Base64-decoded and stored as hexadecimal
- A payload is **passing** if the decoded data equals `0x01`, otherwise **failing**
- The sending device is created automatically on first contact
- Duplicate detection uses `fCnt`: payloads with a counter equal to or below the device's latest are rejected

### GET `/api/payload/` — list all payloads
### GET/PUT/DELETE `/api/payload/<id>/` — retrieve, update, or delete a payload
### GET `/api/device/` — list all devices
### GET/PUT/DELETE `/api/device/<id>/` — retrieve, update, or delete a device

---

## Running Tests

```bash
AUTH_TOKEN=testtoken python manage.py test approot
```

---

## Considerations & Future Work

### Authentication
The current implementation uses a **single shared token** set via the `AUTH_TOKEN` environment variable. This is validated against the `AUTH_TOKEN` header on every request. While sufficient for a basic integration, a production system would benefit from the following improvements:

**Per-device secrets**
Each device could carry its own pre-shared key, sent alongside `devEUI` in the request. The authentication layer would look up the expected secret for that device and validate it before processing the payload. This would allow individual devices to be revoked without rotating a global token, and would make it possible to audit which device sent which payload.

**User authentication**
For a multi-tenant setup or an admin-facing API, DRF's built-in `TokenAuthentication` (via `rest_framework.authtoken`) or `JWT` authentication could be layered on top. The `rest_framework.authtoken` app is already installed — token generation and a login endpoint would be the next step. This would let users manage their own devices and payloads rather than sharing a single API credential.

**HTTPS**
Token-based auth over plain HTTP exposes credentials. In production the application should sit behind a TLS-terminating proxy (nginx, AWS ALB, etc.) with `SECURE_SSL_REDIRECT = True` set in Django settings.
