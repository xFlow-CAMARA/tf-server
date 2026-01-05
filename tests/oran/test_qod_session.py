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
def test_create_wait_get_delete_then_missing(oran_client: BaseOranClient):
    """
    Create a QoD policy, wait 10s, verify it exists, delete it, then
    verify it is no longer retrievable.
    """
    camara_session = {
        "device": {
            "ipv4Address": {
                "publicAddress": "10.45.0.10",
                "privateAddress": "10.45.0.10",
            }
        },
        "applicationServer": {"ipv4Address": "192.168.1.10"},
        "devicePorts": {"ranges": [{"from": 0, "to": 65535}]},
        "applicationServerPorts": {"ranges": [{"from": 0, "to": 65535}]},
        "qosProfile": "qos-s",
    }

    # Create policy
    print("\n===== [Test] CREATE QoD policy =====")
    print("[Test] Payload:")
    print(pformat(camara_session))
    response = oran_client.create_qod_session(camara_session)
    print("\n----- [Test] Create response -----")
    print(pformat(response))
    # Save CAMARA-style session info to enrich subsequent GET mapping
    camara_session_info = dict(response)
    policy_id = response.get("sessionId") or response.get("policy_id") or response.get("policyId")
    assert policy_id, "Session ID not returned by create_qod_session"

    # Wait 10 seconds
    print("\n===== [Test] WAIT before GET =====")
    print("[Test] Sleeping 10s")
    time.sleep(10)

    # Verify policy exists
    try:
        print("\n===== [Test] GET policy =====")
        print(f"[Test] policy_id={policy_id}")
        # Pass original CAMARA session info so GET can return CAMARA-compliant data
        get_resp = oran_client.get_qod_session(policy_id, original_session=camara_session_info)
        print("[Test] GET response:")
        print(pformat(get_resp))
    except OranHttpError as e:
        pytest.fail(f"Policy should exist before deletion: {e}")

    # Delete policy
    try:
        print("\n===== [Test] DELETE policy =====")
        print(f"[Test] policy_id={policy_id}")
        delete_resp = oran_client.delete_qod_session(policy_id)
        # CAMARA r3.2 specifies 204 No Content for delete
        assert delete_resp is None
    except OranHttpError as e:
        pytest.fail(f"Failed to delete oran policy: {e}")

    # Optional short wait to allow backend cleanup
    print("\n===== [Test] WAIT after DELETE =====")
    print("[Test] Sleeping 5s")
    time.sleep(5)

    # Verify deletion (expect a failure on get)
    print("\n===== [Test] GET after DELETE (expect error) =====")
    print(f"[Test] policy_id={policy_id}")
    with pytest.raises(OranHttpError) as excinfo:
        oran_client.get_qod_session(policy_id)
    print(f"[Test] Received expected error: {excinfo.value}")
