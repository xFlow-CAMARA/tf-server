# -*- coding: utf-8 -*-
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pprint import pformat
from socketserver import ThreadingMixIn
from typing import List

import pytest

from sunrise6g_opensdk.common.sdk import Sdk as sdkclient
from sunrise6g_opensdk.oran.core.base_oran_client import BaseOranClient
from sunrise6g_opensdk.oran.core.common import OranHttpError
from tests.oran.test_cases import test_cases


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def _make_handler(storage: List[dict]):
    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length > 0 else b""
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                payload = {"raw": body.decode("utf-8", errors="ignore")}
            record = {
                "path": self.path,
                "headers": dict(self.headers),
                "payload": payload,
                "ts": time.time(),
            }
            storage.append(record)
            # Verbose output of received callback
            try:
                print("\n----- [Notify] Incoming Callback -----")
                print("[Notify] Received POST", record["path"])  # status set below
                print("[Notify] Headers:", pformat(record["headers"]))
                print("[Notify] Payload:", json.dumps(record["payload"], ensure_ascii=False))
            except Exception:
                print("[Notify] Received callback at", record["path"])  # best-effort
            self.send_response(204)
            self.end_headers()

        def log_message(self, fmt, *args):
            # Silence server logs during tests
            return

    return _Handler


@pytest.fixture(scope="module")
def notification_server():
    """Spin up a tiny HTTP server to capture ORAN NEF callbacks.

    Binds to the host used in test_cases; callback URL is printed for visibility.
    """
    host, port = "192.168.40.50", 40000
    received: List[dict] = []
    handler = _make_handler(received)
    httpd = _ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    server = {
        "url": f"http://{host}:{port}/callback",
        "received": received,
    }
    print("\n===== [Notify] SERVER START =====")
    print(f"[Notify] Listening at {server['url']}")
    try:
        yield server
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


@pytest.fixture(scope="module", name="oran_client")
def instantiate_oran_client(request):
    """Fixture to create and share an ORAN client across tests"""
    adapter_specs = request.param
    adapters = sdkclient.create_adapters_from(adapter_specs)
    return adapters.get("oran")


def id_func(val):
    return val["oran"]["client_name"]


def _wait_for_callbacks(store: List[dict], min_new: int, timeout: float, start_len: int = 0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if len(store) - start_len >= min_new:
            print(f"[Notify] Callback(s) arrived: new={len(store) - start_len}, total={len(store)}")
            return True
        time.sleep(0.2)
    return False


@pytest.mark.parametrize("oran_client", test_cases, ids=id_func, indirect=True)
def test_qod_session_with_duration_notification(oran_client: BaseOranClient, notification_server):
    """Create a short-lived policy and expect at least one callback, then expiry notification."""
    duration_seconds = 15
    camara_session = {
        "duration": duration_seconds,
        "device": {
            "ipv4Address": {
                "publicAddress": "10.45.0.10",
                "privateAddress": "10.45.0.10",
            }
        },
        "applicationServer": {"ipv4Address": "192.168.1.10"},
        "devicePorts": {"ranges": [{"from": 0, "to": 65535}]},
        "applicationServerPorts": {"ranges": [{"from": 0, "to": 65535}]},
        "qosProfile": "qos-e",
        "notificationDestination": notification_server["url"],
    }

    print("\n===== [Test] CREATE QoD policy (with notifications) =====")
    print("[Test] Payload:")
    print(pformat(camara_session))
    start_len = len(notification_server["received"])
    response = oran_client.create_qod_session(camara_session)
    print("\n----- [Test] Create response -----")
    print(pformat(response))
    camara_session_info = dict(response)
    session_id = response.get("sessionId")
    assert session_id, "Session ID not returned by create_qod_session"

    # Expect at least one callback shortly after creation
    print("\n===== [Test] WAIT for creation callback =====")
    assert _wait_for_callbacks(
        notification_server["received"], 1, timeout=10, start_len=start_len
    ), "Did not receive any callback after creation"
    if len(notification_server["received"]) > start_len:
        print("\n----- [Test] New callback(s) after create -----")
        for rec in notification_server["received"][start_len:]:
            print(pformat(rec))
            try:
                transformed = oran_client.notification_to_camara_session(
                    rec["payload"], original_session=camara_session_info
                )
                print("[Notify] Transformed to CAMARA:")
                print(pformat(transformed))
            except Exception as exc:
                print(f"[Notify] Transform error: {exc}")

    # Wait until after expiry
    wait_secs = duration_seconds + 5
    print("\n===== [Test] WAIT for expiry =====")
    print(f"[Test] Sleeping {wait_secs}s")
    time.sleep(wait_secs)

    # After expiry, policy should be gone
    print("\n===== [Test] GET after expiry (expect error) =====")
    print(f"[Test] session_id={session_id}")
    with pytest.raises(OranHttpError):
        oran_client.get_qod_session(session_id)

    # Expect at least one additional callback (e.g., expiry)
    print("\n===== [Test] WAIT for expiry callback =====")
    assert _wait_for_callbacks(
        notification_server["received"], 2, timeout=10, start_len=start_len
    ), "Did not receive post-expiry callback"
    if len(notification_server["received"]) > start_len:
        print("\n----- [Test] Callbacks collected -----")
        for rec in notification_server["received"][start_len:]:
            print(pformat(rec))
            try:
                transformed = oran_client.notification_to_camara_session(
                    rec["payload"], original_session=camara_session_info
                )
                print("[Notify] Transformed to CAMARA:")
                print(pformat(transformed))
            except Exception as exc:
                print(f"[Notify] Transform error: {exc}")
