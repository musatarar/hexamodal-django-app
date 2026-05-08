import json

from django.test import TestCase, override_settings

from ..models import Device, Payload
from ..constants import err_bad_base64


@override_settings(AUTH_TOKEN="testtoken")
class AuthenticatedTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client.defaults["AUTH_TOKEN"] = "testtoken"


class GetPayloadMethodTests(AuthenticatedTestCase):
    url = "/api/payload/"

    def test_get_returns_payload_list(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])


class GetPayloadValidationTests(AuthenticatedTestCase):
    url = "/api/payload/"
    base_payload = {
        "devEUI": "0102030405060708",
        "fCnt": 10,
        "data": "AQID",
    }

    def _post(self, payload, content_type="application/json"):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type=content_type,
        )

    def test_invalid_json(self):
        response = self.client.post(
            self.url, data="not-json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.json())

    def test_missing_dev_eui(self):
        payload = {k: v for k, v in self.base_payload.items() if k != "devEUI"}
        response = self._post(payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("devEUI", response.json())

    def test_missing_fcnt(self):
        payload = {k: v for k, v in self.base_payload.items() if k != "fCnt"}
        response = self._post(payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("fCnt", response.json())

    def test_missing_data(self):
        payload = {k: v for k, v in self.base_payload.items() if k != "data"}
        response = self._post(payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("data", response.json())

    def test_invalid_base64(self):
        payload = {**self.base_payload, "data": "AAAAA"}
        response = self._post(payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn(err_bad_base64(""), response.json()["data"][0])

    def test_fcnt_not_integer(self):
        payload = {**self.base_payload, "fCnt": "ten"}
        response = self._post(payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("fCnt", response.json())

    def test_fcnt_negative(self):
        payload = {**self.base_payload, "fCnt": -1}
        response = self._post(payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("fCnt", response.json())


class GetPayloadSuccessTests(AuthenticatedTestCase):
    url = "/api/payload/"
    base_payload = {
        "devEUI": "0102030405060708",
        "fCnt": 10,
        "data": "AQID",  # base64(\x01\x02\x03) → hex "010203"
        "rxInfo": [{"gatewayID": "aabbccdd", "rssi": -80}],
        "txInfo": {"frequency": 868000000},
    }
    expected_data_hex = "010203"

    def _post(self, payload=None):
        return self.client.post(
            self.url,
            data=json.dumps(payload or self.base_payload),
            content_type="application/json",
        )

    def test_new_device_created(self):
        response = self._post()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["devEUI"], self.base_payload["devEUI"])
        self.assertEqual(body["fCnt"], self.base_payload["fCnt"])
        self.assertEqual(body["data"], self.expected_data_hex)
        self.assertEqual(Device.objects.count(), 1)
        self.assertEqual(Payload.objects.count(), 1)

    def test_device_fcnt_updated(self):
        Device.objects.create(
            dev_eui=self.base_payload["devEUI"],
            fcnt_latest=5,
            passing=True,
        )
        response = self._post()
        self.assertEqual(response.status_code, 201)
        device = Device.objects.get(dev_eui=self.base_payload["devEUI"])
        self.assertEqual(device.fcnt_latest, self.base_payload["fCnt"])

    def test_optional_fields_omitted(self):
        payload = {
            "devEUI": "0a0b0c0d0e0f0102",
            "fCnt": 1,
            "data": "AQID",
        }
        response = self._post(payload)
        self.assertEqual(response.status_code, 201)
        stored = Payload.objects.get(device__dev_eui=payload["devEUI"])
        self.assertEqual(stored.rx_info, [])
        self.assertEqual(stored.tx_info, {})

    def test_data_decoded_correctly(self):
        response = self._post()
        self.assertEqual(response.json()["data"], self.expected_data_hex)
        stored = Payload.objects.get(device__dev_eui=self.base_payload["devEUI"])
        self.assertEqual(stored.data, self.expected_data_hex)


class GetPayloadDuplicateTests(AuthenticatedTestCase):
    url = "/api/payload/"
    base_payload = {
        "devEUI": "deadbeefcafebabe",
        "fCnt": 10,
        "data": "AQID",
    }

    def _post(self, payload=None):
        return self.client.post(
            self.url,
            data=json.dumps(payload or self.base_payload),
            content_type="application/json",
        )

    def test_replay_duplicate(self):
        # Device already has a higher fcnt_latest than the incoming fCnt
        Device.objects.create(
            dev_eui=self.base_payload["devEUI"],
            fcnt_latest=20,
            passing=True,
        )
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "duplicate")

    def test_db_level_duplicate(self):
        # Send the same payload twice; second hit triggers IntegrityError on (device, fcnt)
        self._post()
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "duplicate")
        self.assertEqual(Payload.objects.count(), 1)


# ---------------------------------------------------------------------------
# Tests against pre-existing devices (loaded from fixtures/devices.json)
# Edit device_a / device_b / device_c configs in fixtures/devices.json.
# ---------------------------------------------------------------------------


class ExistingDeviceTests(AuthenticatedTestCase):
    url = "/api/payload/"
    fixtures = ["devices"]

    # ── Device configs (mirrors fixtures/devices.json for payload building) ──
    device_a = {
        "dev_eui": "aaaa0000aaaa0000",
        "name": "Sensor Alpha",
        "fcnt_latest": 50,
        "passing": True,
    }
    device_b = {
        "dev_eui": "bbbb1111bbbb1111",
        "name": "Sensor Beta",
        "fcnt_latest": 3,
        "passing": True,
    }
    device_c = {
        "dev_eui": "cccc2222cccc2222",
        "name": "Sensor Charlie",
        "fcnt_latest": 20,
        "passing": False,
    }

    # ── Payloads (reference device configs above) ────────────────────────────
    payload_a_valid        = {"devEUI": device_a["dev_eui"], "fCnt": 51, "data": "AQID"}   # one ahead
    payload_b_valid        = {"devEUI": device_b["dev_eui"], "fCnt": 4,  "data": "AQID"}   # one ahead
    payload_c_valid        = {"devEUI": device_c["dev_eui"], "fCnt": 21, "data": "AQID"}   # one ahead
    payload_a_replay_exact = {"devEUI": device_a["dev_eui"], "fCnt": 50, "data": "AQID"}   # == fcnt_latest
    payload_a_replay_old   = {"devEUI": device_a["dev_eui"], "fCnt": 10, "data": "AQID"}   # well behind
    payload_b_replay_exact = {"devEUI": device_b["dev_eui"], "fCnt": 3,  "data": "AQID"}   # == fcnt_latest
    payload_b_replay_old   = {"devEUI": device_b["dev_eui"], "fCnt": 1,  "data": "AQID"}   # well behind
    payload_a_missing_data = {"devEUI": device_a["dev_eui"], "fCnt": 51}                    # no data field
    payload_a_bad_fcnt     = {"devEUI": device_a["dev_eui"], "fCnt": -5, "data": "AQID"}   # negative
    payload_a_bad_base64   = {"devEUI": device_a["dev_eui"], "fCnt": 51, "data": "AAAAA"}  # 5 chars → incorrect padding

    def setUp(self):
        super().setUp()
        self.dev_a = Device.objects.get(dev_eui=self.device_a["dev_eui"])
        self.dev_b = Device.objects.get(dev_eui=self.device_b["dev_eui"])
        self.dev_c = Device.objects.get(dev_eui=self.device_c["dev_eui"])

    def _post(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    # ── Happy path ───────────────────────────────────────────────────────────

    def test_device_a_located_and_fcnt_updated(self):
        response = self._post(self.payload_a_valid)
        self.assertEqual(response.status_code, 201)
        self.dev_a.refresh_from_db()
        self.assertEqual(self.dev_a.fcnt_latest, self.payload_a_valid["fCnt"])

    def test_device_b_located_and_fcnt_updated(self):
        response = self._post(self.payload_b_valid)
        self.assertEqual(response.status_code, 201)
        self.dev_b.refresh_from_db()
        self.assertEqual(self.dev_b.fcnt_latest, self.payload_b_valid["fCnt"])

    def test_device_a_update_does_not_affect_device_b(self):
        self._post(self.payload_a_valid)
        self.dev_b.refresh_from_db()
        self.assertEqual(self.dev_b.fcnt_latest, self.device_b["fcnt_latest"])

    def test_device_b_update_does_not_affect_device_a(self):
        self._post(self.payload_b_valid)
        self.dev_a.refresh_from_db()
        self.assertEqual(self.dev_a.fcnt_latest, self.device_a["fcnt_latest"])

    def test_device_a_payload_stored(self):
        self._post(self.payload_a_valid)
        self.assertEqual(Payload.objects.filter(device=self.dev_a).count(), 1)

    def test_device_b_payload_stored(self):
        self._post(self.payload_b_valid)
        self.assertEqual(Payload.objects.filter(device=self.dev_b).count(), 1)

    # ── Breaking / rejection tests ────────────────────────────────────────────

    def test_device_a_replay_exact_fcnt(self):
        # fCnt equal to fcnt_latest is still a duplicate
        response = self._post(self.payload_a_replay_exact)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "duplicate")
        self.dev_a.refresh_from_db()
        self.assertEqual(self.dev_a.fcnt_latest, self.device_a["fcnt_latest"])

    def test_device_a_replay_old_fcnt(self):
        response = self._post(self.payload_a_replay_old)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "duplicate")

    def test_device_b_replay_exact_fcnt(self):
        response = self._post(self.payload_b_replay_exact)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "duplicate")
        self.dev_b.refresh_from_db()
        self.assertEqual(self.dev_b.fcnt_latest, self.device_b["fcnt_latest"])

    def test_device_b_replay_old_fcnt(self):
        response = self._post(self.payload_b_replay_old)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "duplicate")

    def test_device_a_db_level_duplicate(self):
        # Same (device, fCnt) sent twice → second triggers IntegrityError
        self._post(self.payload_a_valid)
        response = self._post(self.payload_a_valid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "duplicate")
        self.assertEqual(Payload.objects.filter(device=self.dev_a).count(), 1)

    def test_device_a_missing_data_field(self):
        response = self._post(self.payload_a_missing_data)
        self.assertEqual(response.status_code, 400)
        self.assertIn("data", response.json())

    def test_device_a_negative_fcnt(self):
        response = self._post(self.payload_a_bad_fcnt)
        self.assertEqual(response.status_code, 400)
        self.assertIn("fCnt", response.json())

    def test_device_a_invalid_base64(self):
        response = self._post(self.payload_a_bad_base64)
        self.assertEqual(response.status_code, 400)
        self.assertIn(err_bad_base64(""), response.json()["data"][0])


# ---------------------------------------------------------------------------
# Tests for device passing / failing status transitions
# "AQ==" → b'\x01' → hex "01" → passing=True
# "AQID" → b'\x01\x02\x03' → hex "010203" → passing=False
# ---------------------------------------------------------------------------


class DeviceStatusTests(AuthenticatedTestCase):
    url = "/api/payload/"
    fixtures = ["devices"]

    data_passing = "AQ=="  # hex "01" → passing=True
    data_failing = "AQID"  # hex "010203" → passing=False

    def setUp(self):
        super().setUp()
        self.dev_a = Device.objects.get(dev_eui="aaaa0000aaaa0000")
        self.dev_c = Device.objects.get(dev_eui="cccc2222cccc2222")

    def _post(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    # ── device_c preset state ────────────────────────────────────────────────

    def test_device_c_preset_to_failing(self):
        self.assertFalse(self.dev_c.passing)

    # ── passing transitions ──────────────────────────────────────────────────

    def test_passing_data_sets_device_a_to_passing(self):
        response = self._post(
            {"devEUI": self.dev_a.dev_eui, "fCnt": 51, "data": self.data_passing}
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["passing"])
        self.dev_a.refresh_from_db()
        self.assertTrue(self.dev_a.passing)

    def test_device_c_updates_from_failing_to_passing(self):
        response = self._post(
            {"devEUI": self.dev_c.dev_eui, "fCnt": 21, "data": self.data_passing}
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["passing"])
        self.dev_c.refresh_from_db()
        self.assertTrue(self.dev_c.passing)

    # ── failing transitions ──────────────────────────────────────────────────

    def test_failing_data_sets_device_a_to_failing(self):
        response = self._post(
            {"devEUI": self.dev_a.dev_eui, "fCnt": 51, "data": self.data_failing}
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["passing"])
        self.dev_a.refresh_from_db()
        self.assertFalse(self.dev_a.passing)

    def test_device_c_stays_failing_on_failing_data(self):
        response = self._post(
            {"devEUI": self.dev_c.dev_eui, "fCnt": 21, "data": self.data_failing}
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["passing"])
        self.dev_c.refresh_from_db()
        self.assertFalse(self.dev_c.passing)

    # ── status does not bleed across devices ─────────────────────────────────

    def test_passing_update_to_a_does_not_affect_c(self):
        self._post(
            {"devEUI": self.dev_a.dev_eui, "fCnt": 51, "data": self.data_passing}
        )
        self.dev_c.refresh_from_db()
        self.assertFalse(self.dev_c.passing)

    def test_passing_update_to_c_does_not_affect_a(self):
        self._post(
            {"devEUI": self.dev_c.dev_eui, "fCnt": 21, "data": self.data_passing}
        )
        self.dev_a.refresh_from_db()
        self.assertTrue(self.dev_a.passing)
