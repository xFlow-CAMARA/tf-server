# -*- coding: utf-8 -*-
##
# This file is part of the TF SDK
#
# Contributors:
#   - Adrián Pino Martínez (adrian.pino@i2cat.net)
#   - Sergio Giménez (sergio.gimenez@i2cat.net)
#   - César Cajas (cesar.cajas@i2cat.net)
##
"""
EdgeCloud adapters Integration Tests

Validates the complete application lifecycle:
1. Infrastructure (zone discovery)
2. Artefact management (create/delete)
3. Application lifecycle (onboard/deploy/undeploy/delete app onboarded)

Key features:
- Tests all client implementations (parametrized via test_cases)
- Tests configuration available in test_config.py
- Ensures proper resource cleanup
- Uses shared test constants and CAMARA-compliant manifests
- Includes artefact unit tests where needed
"""
import time

import pytest
from requests import Response

from sunrise6g_opensdk.common.sdk import Sdk as sdkclient
from sunrise6g_opensdk.edgecloud.adapters.aeros.client import (
    EdgeApplicationManager as aerosClient,
)
from sunrise6g_opensdk.edgecloud.adapters.errors import EdgeCloudPlatformError
from sunrise6g_opensdk.edgecloud.adapters.i2edge.client import (
    EdgeApplicationManager as I2EdgeClient,
)
from sunrise6g_opensdk.edgecloud.core import gsma_schemas
from tests.edgecloud.test_cases import test_cases
from tests.edgecloud.test_config_gsma import CONFIG


@pytest.fixture(scope="module", name="edgecloud_client")
def instantiate_edgecloud_client(request):
    """Fixture to create and share an edgecloud client across tests"""
    adapter_specs = request.param
    client_name = adapter_specs["edgecloud"]["client_name"]
    adapters = sdkclient.create_adapters_from(adapter_specs)
    client = adapters.get("edgecloud")
    client.client_name = client_name
    return client


def id_func(val):
    return val["edgecloud"]["client_name"]


@pytest.mark.parametrize("edgecloud_client", test_cases, ids=id_func, indirect=True)
def test_config_gsma_compliance(edgecloud_client):
    """Validate that all test configurations are GSMA-compliant"""
    config = CONFIG[edgecloud_client.client_name]

    try:
        # Validate ARTEFACT is GSMA-compliant
        if "ARTEFACT_GSMA" in config:
            artefact_manifest = config["ARTEFACT_GSMA"]
            gsma_schemas.Artefact(**artefact_manifest)

        # Validate APP_ONBOARD_MANIFEST_GSMA is GSMA-compliant
        if "APP_ONBOARD_MANIFEST_GSMA" in config:
            app_manifest = config["APP_ONBOARD_MANIFEST_GSMA"]
            gsma_schemas.AppOnboardManifestGSMA(**app_manifest)

        # Validate APP_DEPLOY_PAYLOAD_GSMA is GSMA-compliant
        if "APP_DEPLOY_PAYLOAD_GSMA" in config:
            deploy_payload = config["APP_DEPLOY_PAYLOAD_GSMA"]
            gsma_schemas.AppDeployPayloadGSMA(**deploy_payload)

        # Validate PATCH_ONBOARDED_APP_GSMA is GSMA-compliant
        if "PATCH_ONBOARDED_APP_GSMA" in config:
            patch_payload = config["PATCH_ONBOARDED_APP_GSMA"]
            gsma_schemas.PatchOnboardedAppGSMA(**patch_payload)

        # Validate ARTEFACT creation payload is GSMA-compliant
        if "ARTEFACT_PAYLOAD_GSMA" in config:
            artefact_payload = config["ARTEFACT_PAYLOAD_GSMA"]
            gsma_schemas.Artefact(**artefact_payload)

    except Exception as e:
        pytest.fail(f"Configuration is not GSMA-compliant for {edgecloud_client.client_name}: {e}")


@pytest.mark.parametrize("edgecloud_client", test_cases, ids=id_func, indirect=True)
def test_get_edge_cloud_zones_list_gsma(edgecloud_client):
    config = CONFIG[edgecloud_client.client_name]
    try:
        response = edgecloud_client.get_edge_cloud_zones_list_gsma()
        assert isinstance(response, Response)
        assert response.status_code == 200
        zones = response.json()
        assert isinstance(zones, list)

        # GSMA schema validation for each zone
        validated_zones = []
        for zone in zones:
            validated_zone = gsma_schemas.ZoneDetails(**zone)
            validated_zones.append(validated_zone)

        # Logical validation: verify our expected zone is in the list
        expected_zone_id = config["ZONE_ID"]
        found_expected_zone = any(str(zone.zoneId) == expected_zone_id for zone in validated_zones)
        assert found_expected_zone, f"Expected zone {expected_zone_id} not found in returned zones"

    except EdgeCloudPlatformError as e:
        pytest.fail(f"Failed to retrieve zones: {e}")
    except Exception as e:
        pytest.fail(f"Unexpected error during zone validation: {e}")


@pytest.mark.parametrize("edgecloud_client", test_cases, ids=id_func, indirect=True)
def test_get_edge_cloud_zones_gsma(edgecloud_client):
    config = CONFIG[edgecloud_client.client_name]
    try:
        response = edgecloud_client.get_edge_cloud_zones_gsma()
        assert isinstance(response, Response)
        assert response.status_code == 200
        zones = response.json()
        assert isinstance(zones, list)

        # GSMA schema validation for each zone
        validated_zones = []
        for zone in zones:
            validated_zone = gsma_schemas.ZoneRegisteredData(**zone)
            validated_zones.append(validated_zone)

        # Logical validation: verify our expected zone is in the list
        expected_zone_id = config["ZONE_ID"]
        found_expected_zone = any(str(zone.zoneId) == expected_zone_id for zone in validated_zones)
        assert found_expected_zone, f"Expected zone {expected_zone_id} not found in returned zones"

    except EdgeCloudPlatformError as e:
        pytest.fail(f"Failed to retrieve zones details: {e}")
    except Exception as e:
        pytest.fail(f"Unexpected error during zone validation: {e}")


@pytest.mark.parametrize("edgecloud_client", test_cases, ids=id_func, indirect=True)
def test_get_edge_cloud_zone_details_gsma(edgecloud_client):
    config = CONFIG[edgecloud_client.client_name]
    expected_zone_id = config["ZONE_ID"]
    try:
        response = edgecloud_client.get_edge_cloud_zone_details_gsma(expected_zone_id)
        assert isinstance(response, Response)
        assert response.status_code == 200
        zone = response.json()
        assert isinstance(zone, dict)

        # GSMA schema validation for zone
        validated_zone = gsma_schemas.ZoneRegisteredData(**zone)

        # Logical validation: verify our expected zone is in the dict
        assert (
            str(validated_zone.zoneId) == expected_zone_id
        ), f"Expected zoneId {expected_zone_id}, got {validated_zone.zoneId}"

    except EdgeCloudPlatformError as e:
        pytest.fail(f"Failed to retrieve zones details: {e}")
    except Exception as e:
        pytest.fail(f"Unexpected error during zone validation: {e}")


@pytest.mark.parametrize("edgecloud_client", test_cases, ids=id_func, indirect=True)
def test_artefact_methods_gsma(edgecloud_client):
    config = CONFIG[edgecloud_client.client_name]
    if isinstance(edgecloud_client, I2EdgeClient):
        try:
            artefact_manifest = config["ARTEFACT_GSMA"]
            response = edgecloud_client.create_artefact_gsma(artefact_manifest)
            assert response.status_code == 200
        except EdgeCloudPlatformError as e:
            pytest.fail(f"Artefact creation failed: {e}")


@pytest.mark.parametrize("edgecloud_client", test_cases, ids=id_func, indirect=True)
def test_artefact_create_gsma(edgecloud_client):
    config = CONFIG[edgecloud_client.client_name]
    if isinstance(edgecloud_client, aerosClient):
        try:
            response = edgecloud_client.create_artefact_gsma(
                request_body=config["ARTEFACT_PAYLOAD_GSMA"]
            )
            assert response.status_code == 201
        except EdgeCloudPlatformError as e:
            pytest.fail(f"Artefact creation failed: {e}")


@pytest.mark.parametrize("edgecloud_client", test_cases, ids=id_func, indirect=True)
def test_get_artefact_gsma(edgecloud_client):
    config = CONFIG[edgecloud_client.client_name]
    expected_artefact_id = config["ARTEFACT_GSMA"]["artefactId"]
    try:
        response = edgecloud_client.get_artefact_gsma(expected_artefact_id)
        assert isinstance(response, Response)
        assert response.status_code == 200
        artefact = response.json()
        assert isinstance(artefact, dict)

        # GSMA schema validation for artefact
        validated_artefact = gsma_schemas.ArtefactRetrieve(**artefact)

        # Logical validation: verify our expected artefact_id is in the dict
        assert (
            str(validated_artefact.artefactId) == expected_artefact_id
        ), f"Expected artefactId {expected_artefact_id}, got {validated_artefact.artefactId}"

    except EdgeCloudPlatformError as e:
        pytest.fail(f"Failed to retrieve artefact: {e}")
    except Exception as e:
        pytest.fail(f"Unexpected error during artefact validation: {e}")


@pytest.mark.parametrize("edgecloud_client", test_cases, ids=id_func, indirect=True)
def test_onboard_app_gsma(edgecloud_client):
    config = CONFIG[edgecloud_client.client_name]
    try:
        response = edgecloud_client.onboard_app_gsma(config["APP_ONBOARD_MANIFEST_GSMA"])
        assert isinstance(response, Response)
        assert response.status_code == 200

    except EdgeCloudPlatformError as e:
        pytest.fail(f"App onboarding failed: {e}")
    except Exception as e:
        pytest.fail(f"Unexpected error during app onboarding: {e}")


@pytest.mark.parametrize("edgecloud_client", test_cases, ids=id_func, indirect=True)
def test_get_onboarded_app_gsma(edgecloud_client):
    config = CONFIG[edgecloud_client.client_name]
    app_id = config["APP_ONBOARD_MANIFEST_GSMA"]["appId"]
    try:
        response = edgecloud_client.get_onboarded_app_gsma(app_id)
        assert isinstance(response, Response)
        assert response.status_code == 200

        onboarded_app = response.json()
        assert isinstance(onboarded_app, dict)

        # GSMA schema validation for onboarded_app
        validated_schema = gsma_schemas.ApplicationModel(**onboarded_app)

        # Logical validation: verify our expected app_id is in the dict
        assert (
            str(validated_schema.appId) == app_id
        ), f"Expected appId {app_id}, got {validated_schema.appId}"
    except EdgeCloudPlatformError as e:
        pytest.fail(f"Failed to retrieve app: {e}")
    except Exception as e:
        pytest.fail(f"Unexpected error validating app: {e}")


@pytest.fixture(scope="module")
def app_instance_id_gsma(edgecloud_client):
    config = CONFIG[edgecloud_client.client_name]
    try:
        # Use standardized GSMA structure for all adapters
        deploy_payload = config["APP_DEPLOY_PAYLOAD_GSMA"]

        response = edgecloud_client.deploy_app_gsma(deploy_payload)

        assert isinstance(response, Response)
        assert (
            response.status_code == 202
        ), f"Expected 202, got {response.status_code}: {response.text}"

        response_data = response.json()
        instance_info = gsma_schemas.AppInstance(**response_data)

        # Extract appInstIdentifier from the validated object
        app_instance_id_gsma = instance_info.appInstIdentifier

        assert app_instance_id_gsma is not None
        yield app_instance_id_gsma
    finally:
        pass


@pytest.mark.parametrize("edgecloud_client", test_cases, ids=id_func, indirect=True)
def test_deploy_app_gsma(app_instance_id_gsma):
    assert app_instance_id_gsma is not None


@pytest.mark.parametrize("edgecloud_client", test_cases, ids=id_func, indirect=True)
def test_timer_wait_10_seconds(edgecloud_client):
    time.sleep(10)


@pytest.mark.parametrize("edgecloud_client", test_cases, ids=id_func, indirect=True)
def test_get_all_deployed_apps_gsma(edgecloud_client):
    """Test retrieving all deployed application instances"""
    try:
        response = edgecloud_client.get_all_deployed_apps_gsma()
        assert isinstance(response, Response)
        assert response.status_code == 200

        instances_data = response.json()
        assert isinstance(instances_data, list)

        validated_instances = []
        for instance_data in instances_data:
            validated_instance = gsma_schemas.ZoneIdentifier(**instance_data)
            validated_instances.append(validated_instance)

    except EdgeCloudPlatformError as e:
        pytest.fail(f"Failed to get all deployed apps: {e}")


@pytest.mark.parametrize("edgecloud_client", test_cases, ids=id_func, indirect=True)
def test_get_deployed_app_gsma(edgecloud_client, app_instance_id_gsma):
    """Test retrieving a specific deployed application instance"""
    config = CONFIG[edgecloud_client.client_name]
    app_id = config["APP_DEPLOY_PAYLOAD_GSMA"]["appId"]
    zone_id = config["APP_DEPLOY_PAYLOAD_GSMA"]["zoneInfo"]["zoneId"]
    try:
        response = edgecloud_client.get_deployed_app_gsma(app_id, app_instance_id_gsma, zone_id)
        assert isinstance(response, Response)
        assert response.status_code == 200

        instance_data = response.json()
        assert isinstance(instance_data, dict)
        assert "appInstanceState" in instance_data

        gsma_schemas.AppInstanceStatus(**instance_data)

    except EdgeCloudPlatformError as e:
        pytest.fail(f"Failed to get deployed app: {e}")


@pytest.mark.parametrize("edgecloud_client", test_cases, ids=id_func, indirect=True)
def test_undeploy_app_gsma(edgecloud_client, app_instance_id_gsma):
    config = CONFIG[edgecloud_client.client_name]
    app_id = config["APP_DEPLOY_PAYLOAD_GSMA"]["appId"]
    zone_id = config["APP_DEPLOY_PAYLOAD_GSMA"]["zoneInfo"]["zoneId"]
    try:
        response = edgecloud_client.undeploy_app_gsma(app_id, app_instance_id_gsma, zone_id)
        assert isinstance(response, Response)
        assert response.status_code == 200
    except EdgeCloudPlatformError as e:
        pytest.fail(f"App undeployment failed: {e}")


@pytest.mark.parametrize("edgecloud_client", test_cases, ids=id_func, indirect=True)
def test_timer_wait_10_seconds_2(edgecloud_client):
    time.sleep(10)


@pytest.mark.parametrize("edgecloud_client", test_cases, ids=id_func, indirect=True)
def test_patch_onboarded_app_gsma(edgecloud_client):
    config = CONFIG[edgecloud_client.client_name]
    app_id = config["APP_ONBOARD_MANIFEST_GSMA"]["appId"]
    try:
        payload = config["PATCH_ONBOARDED_APP_GSMA"]
        response = edgecloud_client.patch_onboarded_app_gsma(app_id, payload)
        assert isinstance(response, Response)
        assert response.status_code == 200
    except EdgeCloudPlatformError as e:
        pytest.fail(f"Failed to patch onboarded app: {e}")


@pytest.mark.parametrize("edgecloud_client", test_cases, ids=id_func, indirect=True)
def test_delete_onboarded_app_gsma(edgecloud_client):
    config = CONFIG[edgecloud_client.client_name]
    try:
        app_id = config["APP_ONBOARD_MANIFEST_GSMA"]["appId"]
        response = edgecloud_client.delete_onboarded_app_gsma(app_id)
        assert isinstance(response, Response)
        assert response.status_code == 200
    except EdgeCloudPlatformError as e:
        pytest.fail(f"App onboarding deletion failed: {e}")


@pytest.mark.parametrize("edgecloud_client", test_cases, ids=id_func, indirect=True)
def test_delete_artefact_gsma(edgecloud_client):
    config = CONFIG[edgecloud_client.client_name]

    if isinstance(edgecloud_client, I2EdgeClient):
        try:
            response = edgecloud_client.delete_artefact_gsma(config["ARTEFACT_GSMA"]["artefactId"])
            assert isinstance(response, Response)
            assert response.status_code == 200
        except EdgeCloudPlatformError as e:
            pytest.fail(f"Artefact deletion failed: {e}")
