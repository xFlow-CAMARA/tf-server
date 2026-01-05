# -*- coding: utf-8 -*-
import time
from pprint import pformat

import pytest

from sunrise6g_opensdk.common.sdk import Sdk as sdkclient
from sunrise6g_opensdk.oran.core.base_oran_client import BaseOranClient
from sunrise6g_opensdk.oran.core.common import OranHttpError
from tests.oran.test_cases import test_cases


@pytest.fixture(scope="module", name="oran_client")
def instantiate_oran_client(request):
    """Fixture to create and share an ORAN client across tests"""
    adapter_specs = request.param
    adapters = sdkclient.create_adapters_from(adapter_specs)
    return adapters.get("oran")


def id_func(val):
    return val["oran"]["client_name"]


@pytest.mark.parametrize("oran_client", test_cases, ids=id_func, indirect=True)
def test_qod_policy_lifecycle_with_expiry(oran_client: BaseOranClient):
    """
    Create a policy with a short duration, confirm it exists, then
    wait for expiry and confirm it no longer exists.
    """
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
    }

    # Create policy
    print("\n===== [Test] CREATE QoD policy =====")
    print("[Test] Payload:")
    print(pformat(camara_session))
    response = oran_client.create_qod_session(camara_session)
    print("\n----- [Test] Create response -----")
    print(pformat(response))
    session_id = response.get("sessionId")
    assert session_id, "Session ID not returned by create_qod_session"

    # Immediately check it exists
    try:
        print("\n===== [Test] GET after create =====")
        # Provide original CAMARA response to enrich GET mapping
        get_resp = oran_client.get_qod_session(session_id, original_session=dict(response))
        print(f"[Test] policy_id={session_id}")
        print(pformat(get_resp))
    except OranHttpError as e:
        pytest.fail(f"Policy should exist right after creation: {e}")

    # Wait slightly longer than the duration to ensure expiry
    buffer_seconds = 5
    wait_secs = duration_seconds + buffer_seconds
    print("\n===== [Test] WAIT for expiry =====")
    print(f"[Test] Sleeping {wait_secs}s")
    time.sleep(wait_secs)

    # After expiry, the policy should not exist anymore (expect OranHttpError/404)
    print("\n===== [Test] GET after expiry (expect error) =====")
    print(f"[Test] session_id={session_id}")
    with pytest.raises(OranHttpError) as excinfo:
        oran_client.get_qod_session(session_id)
    print(f"[Test] Received expected error: {excinfo.value}")
