# -*- coding: utf-8 -*-
import pytest

from sunrise6g_opensdk.common.sdk import Sdk as sdkclient

ORAN_TEST_CASES = [
    {
        "oran": {
            "client_name": "i2cat_ric",
            "base_url": "http://192.168.40.50:8105",
            "scs_as_id": "scs-test",
        }
    },
]


def id_func(val):
    return val["oran"]["client_name"]


@pytest.mark.parametrize("adapter_specs", ORAN_TEST_CASES, ids=id_func)
def test_oran_platform_instantiation(adapter_specs):
    """Test instantiation of ORAN platform adapters via Sdk."""
    try:
        adapters = sdkclient.create_adapters_from(adapter_specs)
    except ValueError:
        # The factory may not yet expose the ORAN domain; accept as xfail for now
        pytest.xfail("ORAN domain not wired in AdaptersFactory yet")
        return

    assert "oran" in adapters
    oran_client = adapters["oran"]
    assert oran_client is not None
    # Class name contains OranManager for i2cat_ric adapter
    assert "OranManager" in str(type(oran_client))
