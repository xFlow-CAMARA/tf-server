# -*- coding: utf-8 -*-
import pytest

from sunrise6g_opensdk.common.sdk import Sdk as sdkclient

NETWORK_TEST_CASES = [
    {
        "network": {
            "client_name": "open5gs",
            "base_url": "http://test-open5gs.url",
            "scs_as_id": "scs1",
        }
    },
    {
        "network": {
            "client_name": "oai",
            "base_url": "http://test-oai.url",
            "scs_as_id": "scs2",
        }
    },
    {
        "network": {
            "client_name": "open5gcore",
            "base_url": "http://test-open5gcore.url",
            "scs_as_id": "scs3",
        }
    },
]


def id_func(val):
    return val["network"]["client_name"]


@pytest.mark.parametrize("adapter_specs", NETWORK_TEST_CASES, ids=id_func)
def test_network_platform_instantiation(adapter_specs):
    """Test instantiation of all network platform adapters"""
    adapters = sdkclient.create_adapters_from(adapter_specs)

    assert "network" in adapters
    network_client = adapters["network"]
    assert network_client is not None
    assert "NetworkManager" in str(type(network_client))
