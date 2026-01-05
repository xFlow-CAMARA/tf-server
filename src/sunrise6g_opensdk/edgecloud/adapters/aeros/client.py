##
# This file is part of the TF SDK
#
# Contributors:
#   - Vasilis Pitsilis (vpitsilis@dat.demokritos.gr, vpitsilis@iit.demokritos.gr)
#   - Andreas Sakellaropoulos (asakellaropoulos@iit.demokritos.gr)
##
import json
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional

from pydantic import ValidationError
from requests import Response

from sunrise6g_opensdk.edgecloud.adapters.aeros import config
from sunrise6g_opensdk.edgecloud.adapters.aeros.continuum_client import ContinuumClient
from sunrise6g_opensdk.edgecloud.adapters.aeros.converters import (
    aeros2gsma_zone_details,
    camara2aeros_converter,
    gsma2aeros_converter,
)
from sunrise6g_opensdk.edgecloud.adapters.aeros.errors import (
    InvalidArgumentError,
    ResourceNotFoundError,
)
from sunrise6g_opensdk.edgecloud.adapters.aeros.storageManagement import inMemoryStorage
from sunrise6g_opensdk.edgecloud.adapters.aeros.storageManagement.appStorageManager import (
    AppStorageManager,
)
from sunrise6g_opensdk.edgecloud.adapters.aeros.utils import (
    encode_app_instance_name,
    map_aeros_service_status_to_gsma,
    urn_to_uuid,
)
from sunrise6g_opensdk.edgecloud.adapters.errors import EdgeCloudPlatformError
from sunrise6g_opensdk.edgecloud.core import camara_schemas, gsma_schemas
from sunrise6g_opensdk.edgecloud.core.edgecloud_interface import (
    EdgeCloudManagementInterface,
)
from sunrise6g_opensdk.edgecloud.core.utils import build_custom_http_response
from sunrise6g_opensdk.logger import setup_logger


class EdgeApplicationManager(EdgeCloudManagementInterface):
    """
    aerOS Edge Application Manager Adapter implementing CAMARA and GSMA APIs.
    """

    def __init__(self, base_url: str, storage: Optional[AppStorageManager] = None, **kwargs):
        """
        storage can
        """
        self.base_url = base_url
        self.logger = setup_logger(__name__, is_debug=True, file_name=config.LOG_FILE)
        self.content_type_gsma = "application/json"
        self.encoding_gsma = "utf-8"
        self.storage = storage or inMemoryStorage.InMemoryAppStorage()

        # Overwrite config values if provided via kwargs
        if "aerOS_API_URL" in kwargs:
            config.aerOS_API_URL = kwargs["aerOS_API_URL"]
        if "aerOS_ACCESS_TOKEN" in kwargs:
            config.aerOS_ACCESS_TOKEN = kwargs["aerOS_ACCESS_TOKEN"]
        if "aerOS_HLO_TOKEN" in kwargs:
            config.aerOS_HLO_TOKEN = kwargs["aerOS_HLO_TOKEN"]

        if not config.aerOS_API_URL:
            raise ValueError("Missing 'aerOS_API_URL'")
        if not config.aerOS_ACCESS_TOKEN:
            raise ValueError("Missing 'aerOS_ACCESS_TOKEN'")
        if not config.aerOS_HLO_TOKEN:
            raise ValueError("Missing 'aerOS_HLO_TOKEN'")

    # ########################################################################
    # CAMARA EDGE CLOUD MANAGEMENT API
    # ########################################################################

    # ------------------------------------------------------------------------
    # Edge Cloud Zone Management (CAMARA)
    # ------------------------------------------------------------------------

    # Zones methods
    def get_edge_cloud_zones(
        self, region: Optional[str] = None, status: Optional[str] = None
    ) -> Response:
        """
        Retrieves a list of available Edge Cloud Zones.

        :param region: Filter by geographical region.
        :param status: Filter by status (active, inactive, unknown).
        :return: Response with list of Edge Cloud Zones in CAMARA format.
        """
        try:
            aeros_client = ContinuumClient(self.base_url)
            ngsild_params = "type=Domain&format=simplified"
            camara_response = aeros_client.query_entities(ngsild_params)
            aeros_domains = camara_response.json()
            if config.DEBUG:
                self.logger.debug("aerOS edge cloud zones: %s", aeros_domains)

            zone_list = []
            for domain in aeros_domains:
                domain_id = domain.get("id")
                if not domain_id:
                    continue

                # Normalize status
                raw_status = domain.get("domainStatus", "")
                status_token = raw_status.split(":")[-1].strip().lower()
                status = "Active" if status_token == "functional" else "Unknown"

                zone = {
                    "edgeCloudZoneId": str(urn_to_uuid(domain_id)),
                    "edgeCloudZoneName": domain_id,  # or domain_id.split(":")[-1] if you prefer short name
                    "edgeCloudProvider": (
                        domain.get("owner", ["unknown"])[0]
                        if isinstance(domain.get("owner"), list)
                        else domain.get("owner", "unknown")
                    ),
                    "status": status,
                    "geographyDetails": "NOT_USED",
                }
                zone_list.append(zone)

            # Store zones keyed by the aerOS domain id
            self.storage.store_zones({d["edgeCloudZoneName"]: d for d in zone_list})
            if config.DEBUG:
                self.logger.debug("aerOS Local domains store: %s", zone_list)
            return build_custom_http_response(
                status_code=camara_response.status_code,
                content=zone_list,
                headers={"Content-Type": "application/json"},
                encoding=camara_response.encoding,
                url=camara_response.url,
                request=camara_response.request,
            )
        except json.JSONDecodeError as e:
            self.logger.error("Invalid JSON in aerOS response: %s", e)
            raise
        except KeyError as e:
            self.logger.error("Missing expected field in aerOS data: %s", e)
            raise
        except EdgeCloudPlatformError as e:
            self.logger.error("Error retrieving edge cloud zones: %s", e)
            raise

    def get_edge_cloud_zones_details(self, zone_id: str, flavour_id: Optional[str] = None) -> Dict:
        """
        Get details of a specific edge cloud zone.
        :param zone_id: The ID of the edge cloud zone
        :param flavour_id: Optional flavour ID to filter the results
        :return: Details of the edge cloud zone
        """
        aeros_client = ContinuumClient(self.base_url)
        ngsild_params = f'format=simplified&type=InfrastructureElement&q=domain=="{zone_id}"'
        if config.DEBUG:
            self.logger.debug(
                "Querying infrastructure elements for zone %s with params: %s",
                zone_id,
                ngsild_params,
            )
        try:
            # Query the infrastructure elements for the specified zonese
            aeros_response = aeros_client.query_entities(ngsild_params)
            aeros_domain_ies = aeros_response.json()
            # Transform the infrastructure elements into the required format
            # and return the details of the edge cloud zone
            camara_response = self.transform_infrastructure_elements(
                domain_ies=aeros_domain_ies, domain=zone_id
            )
            if config.DEBUG:
                self.logger.debug("Transformed response: %s", camara_response)
            # Return the transformed response
            return build_custom_http_response(
                status_code=aeros_response.status_code,
                content=camara_response,
                headers={"Content-Type": "application/json"},
                encoding=aeros_response.encoding,
                url=aeros_response.url,
                request=aeros_response.request,
            )
        except json.JSONDecodeError as e:
            self.logger.error("Invalid JSON in aerOS response: %s", e)
            raise
        except KeyError as e:
            self.logger.error("Missing expected field in aerOS data: %s", e)
            raise
        except EdgeCloudPlatformError as e:
            self.logger.error("Error retrieving edge cloud zones: %s", e)
            raise

    def transform_infrastructure_elements(
        self, domain_ies: List[Dict[str, Any]], domain: str
    ) -> Dict[str, Any]:
        """
        Transform the infrastructure elements into a format suitable for the
        edge cloud zone details.
        :param domain_ies: List of infrastructure elements
        :param domain: The ID of the edge cloud zone
        :return: Transformed details of the edge cloud zone
        """
        total_cpu = 0
        total_ram = 0
        total_disk = 0
        total_available_ram = 0
        total_available_disk = 0

        flavours_supported = []

        for element in domain_ies:
            total_cpu += element.get("cpuCores", 0)
            total_ram += element.get("ramCapacity", 0)
            total_available_ram += element.get("availableRam", 0)
            total_disk += element.get("diskCapacity", 0)
            total_available_disk += element.get("availableDisk", 0)

            # Create a flavour per machine
            flavour = {
                "flavourId": f"{element.get('hostname')}-{element.get('containerTechnology')}",
                "cpuArchType": f"{element.get('cpuArchitecture')}",
                "supportedOSTypes": [
                    {
                        "architecture": f"{element.get('cpuArchitecture')}",
                        "distribution": f"{element.get('operatingSystem')}",  # assume
                        "version": "OS_VERSION_UBUNTU_2204_LTS",
                        "license": "OS_LICENSE_TYPE_FREE",
                    }
                ],
                "numCPU": element.get("cpuCores", 0),
                "memorySize": element.get("ramCapacity", 0),
                "storageSize": element.get("diskCapacity", 0),
            }
            flavours_supported.append(flavour)

        result = {
            "zoneId": domain,
            "reservedComputeResources": [
                {
                    "cpuArchType": "ISA_X86_64",
                    "numCPU": int(total_cpu),
                    "memory": total_ram,
                }
            ],
            "computeResourceQuotaLimits": [
                {
                    "cpuArchType": "ISA_X86_64",
                    "numCPU": int(total_cpu * 2),  # Assume quota is 2x total?
                    "memory": total_ram * 2,
                }
            ],
            "flavoursSupported": flavours_supported,
        }
        return result

    # ------------------------------------------------------------------------
    # Application Management (CAMARA-Compliant)
    # ------------------------------------------------------------------------

    # Onboarding methods
    def onboard_app(self, app_manifest: Dict) -> Response:
        # Validate CAMARA input
        camara_schemas.AppManifest(**app_manifest)

        app_id = app_manifest.get("appId")
        if not app_id:
            raise EdgeCloudPlatformError("Missing 'appId' in app manifest")

        if self.storage.get_app(app_id=app_id):
            raise EdgeCloudPlatformError(f"Application with id '{app_id}' already exists")

        self.storage.store_app(app_id, app_manifest)
        self.logger.debug("Onboarded application with id: %s", app_id)
        submitted_app = camara_schemas.SubmittedApp(appId=camara_schemas.AppId(app_id))
        return build_custom_http_response(
            status_code=201,
            content=submitted_app.model_dump(mode="json"),
            headers={"Content-Type": "application/json"},
            encoding="utf-8",
        )

    def get_all_onboarded_apps(self) -> Response:
        apps = self.storage.list_apps()
        self.logger.debug("Onboarded applications: %s", apps)
        return build_custom_http_response(
            status_code=200,
            content=apps,
            headers={"Content-Type": "application/json"},
            encoding="utf-8",
        )

    def get_onboarded_app(self, app_id: str) -> Response:
        app_data = self.storage.get_app(app_id)
        if not app_data:
            raise EdgeCloudPlatformError(f"Application with id '{app_id}' does not exist")
        self.logger.debug("Retrieved application with id: %s", app_id)

        app_manifest_response = {
            "appManifest": app_data
        }  # We already keep the app manifest when onboarding

        return build_custom_http_response(
            status_code=200,
            content=app_manifest_response,
            headers={"Content-Type": "application/json"},
            encoding="utf-8",
        )

    def delete_onboarded_app(self, app_id: str) -> Response:
        app = self.storage.get_app(app_id)
        if not app:
            raise EdgeCloudPlatformError(f"Application with id '{app_id}' does not exist")

        service_instances = self.storage.get_stopped_instances(app_id=app_id)
        if not service_instances:
            raise EdgeCloudPlatformError(
                f"Application with id '{app_id}' cannot be deleted — please stop it first"
            )
        self.logger.debug(
            "Deleting application with id: %s and instances: %s",
            app_id,
            service_instances,
        )
        for service_instance in service_instances:
            self._purge_deployed_app_from_continuum(service_instance)
            self.logger.debug("successfully purged service instance: %s", service_instance)

        self.storage.remove_stopped_instances(app_id)
        self.storage.delete_app(app_id)

        return build_custom_http_response(
            status_code=204,
            content=b"",  # absolutely no body for 204
            headers={"Content-Type": "application/json"},
            encoding="utf-8",
            # url=None,
            # request=None,
        )

    def _generate_service_id(self, app_id: str) -> str:
        """
        Generate a unique service ID for aerOS continuum.
        The service ID is in the format of a NGSI-LD URN with a random suffix.
        :param app_id: The application ID
        :return: The generated service ID
        """
        return f"{app_id}-{uuid.uuid4().hex[:4]}"

    def _generate_aeros_service_id(self, camara_app_instance_id: str) -> str:
        """
        Convert CAMARA appInstanceId to aerOS service ID.
        :param camara_app_instance_id: The CAMARA appInstanceId
        :return: The corresponding aerOS service ID
        """
        return f"urn:ngsi-ld:Service:{camara_app_instance_id}"

    # Instantiation methods
    def deploy_app(self, app_id: str, app_zones: List[Dict]) -> Response:
        # 1. Get app CAMARA manifest
        app_manifest = self.storage.get_app(app_id)
        if not app_manifest:
            raise EdgeCloudPlatformError(f"Application with id '{app_id}' does not exist")
        app_manifest = camara_schemas.AppManifest.model_validate(app_manifest)

        # 2. Generate unique service ID
        #    (aerOS) service id <=> CAMARA appInstanceId
        service_id = self._generate_service_id(app_id)

        # 3. Convert dict to YAML string
        # 3a. Get aerOS domain IDs from zones uuids
        aeros_domain_ids = [
            self.storage.resolve_domain_id_by_zone_uuid(z["EdgeCloudZone"]["edgeCloudZoneId"])
            for z in app_zones
            if z.get("EdgeCloudZone", {}).get("edgeCloudZoneId")
        ]
        tosca_str = camara2aeros_converter.generate_tosca(
            app_manifest=app_manifest, app_zones=aeros_domain_ids
        )
        if config.DEBUG:
            self.logger.info("Generated TOSCA YAML:")
            self.logger.info(tosca_str)

        # 4. Instantiate client and call continuum to deploy service
        try:
            aeros_client = ContinuumClient(self.base_url)
            aeros_response = aeros_client.onboard_and_deploy_service(
                self._generate_aeros_service_id(service_id), tosca_str
            )

            if "serviceId" not in aeros_response.json():
                raise EdgeCloudPlatformError(
                    "Invalid response from onboard_service: missing 'serviceId'"
                )

            # Build CAMARA-compliant info
            app_provider_id = app_manifest.appProvider.root
            zone_id = app_zones[0].get("EdgeCloudZone", {}).get("edgeCloudZoneId", "default-zone")
            app_instance_info = camara_schemas.AppInstanceInfo(
                name=camara_schemas.AppInstanceName(encode_app_instance_name(service_id)),
                appId=camara_schemas.AppId(app_id),
                appInstanceId=camara_schemas.AppInstanceId(service_id),
                appProvider=camara_schemas.AppProvider(app_provider_id),
                status=camara_schemas.Status.instantiating,
                edgeCloudZoneId=camara_schemas.EdgeCloudZoneId(zone_id),
            )

            # 5. Track deployment
            self.storage.store_deployment(app_instance=app_instance_info)

            # 6. Return expected format
            self.logger.info("App deployment request submitted successfully")

            # CAMARA spec requires appInstances array wrapper
            camara_response = app_instance_info.model_dump(mode="json")
            # Add mandatory Location header
            location_url = f"/appinstances/{service_id}"
            camara_headers = {"Content-Type": "application/json", "Location": location_url}

            return build_custom_http_response(
                status_code=aeros_response.status_code,
                content=camara_response,
                headers=camara_headers,
                encoding="utf-8",
                url=aeros_response.url,
                request=aeros_response.request,
            )
        except EdgeCloudPlatformError as ex:
            # Catch all platform-specific errors.
            # All custom exception types (InvalidArgumentError, UnauthenticatedError, etc.)
            # inherit from EdgeCloudPlatformError, so a single handler here will capture
            # any of them. We can further elaborate per eachone of needed.
            self.logger.error("Failed to deploy app '%s': %s", app_id, str(ex))
            raise

    def get_all_deployed_apps(
        self,
        app_id: Optional[str] = None,
        app_instance_id: Optional[str] = None,
        region: Optional[str] = None,
    ) -> Response:

        instances = self.storage.find_deployments(app_id, app_instance_id, region)

        # CAMARA spec format for multiple instances response
        camara_response = {
            "appInstances": [
                inst.model_dump(mode="json") if hasattr(inst, "model_dump") else inst
                for inst in instances
            ]
        }

        self.logger.info("All app instances retrieved successfully")
        if config.DEBUG:
            self.logger.debug("Onboarded applications: %s", camara_response)
        return build_custom_http_response(
            status_code=200,
            content=camara_response,
            headers={"Content-Type": "application/json"},
            encoding="utf-8",
            # url=response.url,
            # request=response.request,
        )

    def get_deployed_app(
        self, app_instance_id: str, app_id: Optional[str] = None, region: Optional[str] = None
    ) -> Response:
        """
        Placeholder implementation for CAMARA compliance.
        Retrieves information of a specific application instance.

        :param app_instance_id: Unique identifier of the application instance
        :param app_id: Optional filter by application ID
        :param region: Optional filter by Edge Cloud region
        :return: Response with application instance details
        """
        try:
            if not app_instance_id:
                raise InvalidArgumentError("app_instance_id is required")

            # Look up the instance in CAMARA storage (returns List[AppInstanceInfo])
            matches = self.storage.find_deployments(
                app_id=app_id,
                app_instance_id=app_instance_id,
                region=region,
            )
            if not matches:
                # Be explicit in the error so callers know what was used to filter
                scope = []
                scope.append(f"instance_id={app_instance_id}")
                if app_id:
                    scope.append(f"app_id={app_id}")
                if region:
                    scope.append(f"region={region}")
                raise ResourceNotFoundError(f"Deployed app not found ({', '.join(scope)})")

            # If multiple matched (shouldn't normally happen after filtering by instance id),
            # return the first deterministically.
            inst = matches[0]

            # Serialize to JSON-safe dict
            content = {"appInstance": inst.model_dump(mode="json")}

            return build_custom_http_response(
                status_code=200,
                content=content,
                headers={"Content-Type": "application/json"},
                encoding="utf-8",
            )

        except (InvalidArgumentError, ResourceNotFoundError):
            # Let well-typed domain errors propagate
            raise
        except EdgeCloudPlatformError:
            raise
        except Exception as e:
            # Defensive catch-all with context
            self.logger.exception(
                "Unhandled error retrieving deployed app instance '%s' (app_id=%s, region=%s): %s",
                app_instance_id,
                app_id,
                region,
                e,
            )
            raise EdgeCloudPlatformError(str(e))

    def _purge_deployed_app_from_continuum(self, app_id: str) -> None:
        """
        Purge the deployed application from aerOS continuum.
        :param app_id: The application ID to purge
        All instances of this app should be stopped
        """
        aeros_client = ContinuumClient(self.base_url)
        response = aeros_client.purge_service(self._generate_aeros_service_id(app_id))
        if response:
            self.logger.debug(
                "Purged deployed application with id: %s", self._generate_aeros_service_id(app_id)
            )
        else:
            raise EdgeCloudPlatformError(
                f"Failed to purge service with id from the continuum '{app_id}'"
            )

    def undeploy_app(self, app_instance_id: str) -> Response:
        # 1. Locate app_id corresponding to this instance and
        #    remove from deployed instances for this appId
        app_id = self.storage.remove_deployment(app_instance_id=app_instance_id)
        if not app_id:
            raise EdgeCloudPlatformError(
                f"No deployed app instance with ID '{app_instance_id}' found"
            )

        # 2. Call the external undeploy_service
        aeros_client = ContinuumClient(self.base_url)
        try:
            aeros_response = aeros_client.undeploy_service(
                self._generate_aeros_service_id(app_instance_id)
            )
        except Exception as e:
            raise EdgeCloudPlatformError(
                f"Failed to undeploy app instance '{app_instance_id}': {str(e)}"
            ) from e

        # We could do it here with a little wait but better all instances in the same app are purged at once
        # 3. Purge the deployed app from continuum
        # self._purge_deployed_app_from_continuum(app_instance_id)

        # 4. Clean up internal tracking
        self.storage.remove_deployment(app_instance_id)
        self.storage.store_stopped_instance(app_id, app_instance_id)
        return build_custom_http_response(
            status_code=204,
            content="",
            headers={"Content-Type": "application/json"},
            encoding="utf-8",
            url=aeros_response.url,
            request=aeros_response.request,
        )

    # ########################################################################
    # GSMA EDGE COMPUTING API (EWBI OPG) - FEDERATION
    # ########################################################################

    # ------------------------------------------------------------------------
    # Zone Management (GSMA)
    # ------------------------------------------------------------------------

    def get_edge_cloud_zones_list_gsma(self) -> Response:
        """
        Retrieves details of all Zones for GSMA federation.

        :return: Response with zone details in GSMA format.
        """
        try:
            aeros_client = ContinuumClient(self.base_url)
            ngsild_params = "type=Domain&format=simplified"
            aeros_response = aeros_client.query_entities(ngsild_params)
            aeros_domains = aeros_response.json()
            zone_list = [
                {
                    "zoneId": domain["id"],
                    "geolocation": "NOT_Available",
                    "geographyDetails": domain["description"],
                }
                for domain in aeros_domains
            ]
            return build_custom_http_response(
                status_code=aeros_response.status_code,
                content=zone_list,
                headers={"Content-Type": self.content_type_gsma},
                encoding=self.encoding_gsma,
                url=aeros_response.url,
                request=aeros_response.request,
            )
        except json.JSONDecodeError as e:
            self.logger.error("Invalid JSON in aerOS response: %s", e)
            raise
        except KeyError as e:
            self.logger.error("Missing expected field in aerOS data: %s", e)
            raise
        except EdgeCloudPlatformError as e:
            self.logger.error("Error retrieving edge cloud zones: %s", e)
            raise

    # AvailabilityZoneInfoSynchronization

    def get_edge_cloud_zones_gsma(self) -> Response:
        """
        Retrieves details of all Zones with compute resources and flavours for GSMA federation.

        :return: Response with zones and detailed resource information.
        """
        aeros_client = ContinuumClient(self.base_url)
        ngsild_params = "format=simplified&type=InfrastructureElement"

        try:
            # Query the infrastructure elements whithin the whole continuum
            aeros_response = aeros_client.query_entities(ngsild_params)
            aeros_ies = aeros_response.json()  # IEs as list of dicts

            # Create a dict that groups by "domain"
            grouped_by_domain = defaultdict(list)
            for item in aeros_ies:
                domain = item["domain"]
                grouped_by_domain[domain].append(item)

            # Transform the IEs to required format
            # per domain and append to response list
            gsma_response = []
            for domain, ies in grouped_by_domain.items():
                result = aeros2gsma_zone_details.transformer(domain_ies=ies, domain=domain)
                gsma_response.append(result)
            # Return the transformed response
            return build_custom_http_response(
                status_code=aeros_response.status_code,
                content=gsma_response,
                headers={"Content-Type": self.content_type_gsma},
                encoding=self.encoding_gsma,
                url=aeros_response.url,
                request=aeros_response.request,
            )
        except json.JSONDecodeError as e:
            self.logger.error("Invalid JSON in aerOS response: %s", e)
            raise
        except KeyError as e:
            self.logger.error("Missing expected field in aerOS data: %s", e)
            raise
        except EdgeCloudPlatformError as e:
            self.logger.error("Error retrieving edge cloud zones: %s", e)
            raise

    def get_edge_cloud_zone_details_gsma(self, zone_id: str) -> Response:
        """
        Retrieves details of a specific Edge Cloud Zone reserved
        for the specified zone by the partner OP using GSMA federation.

        :param zone_id: Unique identifier of the Edge Cloud Zone.
        :return: Response with Edge Cloud Zone details.
        """
        aeros_client = ContinuumClient(self.base_url)
        ngsild_params = f'format=simplified&type=InfrastructureElement&q=domain=="{zone_id}"'
        if config.DEBUG:
            self.logger.debug(
                "Querying infrastructure elements for zone %s with params: %s",
                zone_id,
                ngsild_params,
            )
        try:
            # Query the infrastructure elements for the specified zonese
            aeros_response = aeros_client.query_entities(ngsild_params)
            aeros_domain_ies = aeros_response.json()
            # Transform the infrastructure elements into the required format
            # and return the details of the edge cloud zone
            # camara_response = self.transform_infrastructure_elements(
            #     domain_ies=aeros_domain_ies, domain=zone_id)
            gsma_response = aeros2gsma_zone_details.transformer(
                domain_ies=aeros_domain_ies, domain=zone_id
            )
            if config.DEBUG:
                self.logger.debug("Transformed response: %s", gsma_response)
            # Return the transformed response
            return build_custom_http_response(
                status_code=aeros_response.status_code,
                content=gsma_response,
                headers={"Content-Type": "application/json"},
                encoding=aeros_response.encoding,
                url=aeros_response.url,
                request=aeros_response.request,
            )
        except json.JSONDecodeError as e:
            self.logger.error("Invalid JSON in aerOS response: %s", e)
            raise
        except KeyError as e:
            self.logger.error("Missing expected field in aerOS data: %s", e)
            raise
        except EdgeCloudPlatformError as e:
            self.logger.error("Error retrieving edge cloud zones: %s", e)
            raise

    # ------------------------------------------------------------------------
    # Artefact Management (GSMA)
    # ------------------------------------------------------------------------

    def create_artefact_gsma(self, request_body: dict) -> Response:
        """
        Uploads application artefact on partner OP. Artefact is a zip file
        containing scripts and/or packaging files like Terraform or Helm
        which are required to create an instance of an application

        :param request_body: Payload with artefact information.
        :return:
        """
        try:
            artefact = gsma_schemas.Artefact.model_validate(request_body)
            self.storage.store_artefact_gsma(artefact)
            return build_custom_http_response(
                status_code=201,
                content=artefact.model_dump(mode="json"),
                headers={"Content-Type": self.content_type_gsma},
                encoding=self.encoding_gsma,
            )
        except ValidationError as e:
            self.logger.error("Invalid GSMA artefact schema: %s", e)
            raise InvalidArgumentError(str(e))

    def get_artefact_gsma(self, artefact_id: str) -> Response:
        """
        Retrieves details about an artefact

        :param artefact_id: Unique identifier of the artefact.
        :return: Dictionary with artefact details.
        """
        art = self.storage.get_artefact_gsma(artefact_id)
        if not art:
            raise ResourceNotFoundError(f"GSMA artefact '{artefact_id}' not found")
        return build_custom_http_response(
            status_code=200,
            content=art.model_dump(mode="json"),
            headers={"Content-Type": self.content_type_gsma},
            encoding=self.encoding_gsma,
        )

    def list_artefacts_gsma(self):
        """List all GSMA Artefacts."""
        arts = [a.model_dump(mode="json") for a in self.storage.list_artefacts_gsma()]
        return build_custom_http_response(
            status_code=200,
            content=arts,
            headers={"Content-Type": self.content_type_gsma},
            encoding=self.encoding_gsma,
        )

    def delete_artefact_gsma(self, artefact_id: str) -> Response:
        """
        Removes an artefact from partners OP.

        :param artefact_id: Unique identifier of the artefact.
        :return:
        """
        if not self.storage.get_artefact_gsma(artefact_id):
            raise ResourceNotFoundError(f"GSMA artefact '{artefact_id}' not found")
        self.storage.delete_artefact_gsma(artefact_id)
        return build_custom_http_response(status_code=204, content=b"", headers={}, encoding=None)

    # ------------------------------------------------------------------------
    # Application Onboarding Management (GSMA)
    # ------------------------------------------------------------------------

    def _to_application_model(
        self, entry: gsma_schemas.AppOnboardManifestGSMA
    ) -> gsma_schemas.ApplicationModel:
        """Internal helper to convert GSMA onboarding entry into canonical ApplicationModel."""
        zones = [
            gsma_schemas.AppDeploymentZone(countryCode="XX", zoneInfo=z)
            for z in entry.appDeploymentZones
        ]
        return gsma_schemas.ApplicationModel(
            appId=entry.appId,
            appProviderId=entry.appProviderId,
            appDeploymentZones=zones,
            appMetaData=entry.appMetaData,
            appQoSProfile=entry.appQoSProfile,
            appComponentSpecs=entry.appComponentSpecs,
            onboardStatusInfo="ONBOARDED",
        )

    def onboard_app_gsma(self, request_body: dict):
        """
        Submits an application details to a partner OP.
        Based on the details provided, partner OP shall do bookkeeping,
        resource validation and other pre-deployment operations.

        :param request_body: Payload with onboarding info.
        :return: Response with onboarding confirmation.
        """
        try:
            # Validate input against GSMA schema
            entry = gsma_schemas.AppOnboardManifestGSMA.model_validate(request_body)
        except ValidationError as e:
            self.logger.error("Invalid GSMA input schema: %s", e)
            raise InvalidArgumentError(str(e))

        try:
            # Convert to ApplicationModel (canonical onboarded representation)
            app_model = self._to_application_model(entry)

            # Ensure uniqueness
            if self.storage.get_app_gsma(app_model.appId):
                raise InvalidArgumentError(f"GSMA app '{app_model.appId}' already exists")

            # Store in GSMA apps storage
            self.storage.store_app_gsma(app_model.appId, app_model)

            # Build and return confirmation response
            return build_custom_http_response(
                status_code=201,
                content=app_model.model_dump(mode="json"),
                headers={"Content-Type": self.content_type_gsma},
                encoding=self.encoding_gsma,
            )
        except EdgeCloudPlatformError as e:
            self.logger.error("Error during GSMA app onboarding: %s", e)
            raise
        except Exception as e:
            self.logger.exception("Unhandled error during GSMA onboarding: %s", e)
            raise EdgeCloudPlatformError(str(e))

    def get_onboarded_app_gsma(self, app_id: str) -> Dict:
        """
        Retrieves application details from partner OP

        :param app_id: Identifier of the application onboarded.
        :return: Dictionary with application details.
        """
        try:
            app = self.storage.get_app_gsma(app_id)
            if not app:
                raise ResourceNotFoundError(f"GSMA app '{app_id}' not found")

            return build_custom_http_response(
                status_code=200,
                content=app.model_dump(mode="json"),
                headers={"Content-Type": self.content_type_gsma},
                encoding=self.encoding_gsma,
            )
        except EdgeCloudPlatformError as e:
            self.logger.error("Error retrieving GSMA app '%s': %s", app_id, e)
            raise
        except Exception as e:
            self.logger.exception("Unhandled error retrieving GSMA app '%s': %s", app_id, e)
            raise EdgeCloudPlatformError(str(e))

    def patch_onboarded_app_gsma(self, app_id: str, request_body: dict):
        """
        Updates partner OP about changes in application compute resource requirements,
        QOS Profile, associated descriptor or change in associated components.

        :param app_id: Identifier of the application onboarded.
        :param request_body: Payload with updated onboarding info.
        :return: Response with updated application details.
        """
        try:
            patch = gsma_schemas.PatchOnboardedAppGSMA.model_validate(request_body)
        except ValidationError as e:
            self.logger.error("Invalid GSMA patch schema: %s", e)
            raise InvalidArgumentError(str(e))

        try:
            app = self.storage.get_app_gsma(app_id)
            if not app:
                raise ResourceNotFoundError(f"GSMA app '{app_id}' not found")

            upd = patch.appUpdQoSProfile

            # Update QoS profile fields
            if upd.latencyConstraints is not None:
                app.appQoSProfile.latencyConstraints = upd.latencyConstraints
            if upd.bandwidthRequired is not None:
                app.appQoSProfile.bandwidthRequired = upd.bandwidthRequired
            if upd.multiUserClients is not None:
                app.appQoSProfile.multiUserClients = upd.multiUserClients
            if upd.noOfUsersPerAppInst is not None:
                app.appQoSProfile.noOfUsersPerAppInst = upd.noOfUsersPerAppInst
            if upd.appProvisioning is not None:
                app.appQoSProfile.appProvisioning = upd.appProvisioning

            # mobilitySupport lives under AppMetaData
            if upd.mobilitySupport is not None:
                app.appMetaData.mobilitySupport = upd.mobilitySupport

            # Replace component specs if provided
            if patch.appComponentSpecs:
                app.appComponentSpecs = [
                    gsma_schemas.AppComponentSpec(
                        serviceNameNB=p.serviceNameNB,
                        serviceNameEW=p.serviceNameEW,
                        componentName=p.componentName,
                        artefactId=p.artefactId,
                    )
                    for p in patch.appComponentSpecs
                ]

            # Persist updated model
            self.storage.store_app_gsma(app_id, app)

            return build_custom_http_response(
                status_code=200,
                content=app.model_dump(mode="json"),
                headers={"Content-Type": self.content_type_gsma},
                encoding=self.encoding_gsma,
            )
        except EdgeCloudPlatformError as e:
            self.logger.error("Error updating GSMA app '%s': %s", app_id, e)
            raise
        except Exception as e:
            self.logger.exception("Unhandled error patching GSMA app '%s': %s", app_id, e)
            raise EdgeCloudPlatformError(str(e))

    def delete_onboarded_app_gsma(self, app_id: str):
        """
        Deboards an application from specific partner OP zones.

        :param app_id: Identifier of the application onboarded.
        :return: 204 No Content on success.
        """
        try:
            if not self.storage.get_app_gsma(app_id):
                raise ResourceNotFoundError(f"GSMA app '{app_id}' not found")

            # CHECKME: update for GSMA
            service_instances = self.storage.get_stopped_instances_gsma(app_id=app_id)
            if not service_instances:
                raise EdgeCloudPlatformError(
                    f"Application with id '{app_id}' cannot be deleted — please stop it first"
                )
            self.logger.debug(
                "Deleting application with id: %s and instances: %s",
                app_id,
                service_instances,
            )
            for service_instance in service_instances:
                self._purge_deployed_app_from_continuum_gsma(service_instance)
                self.logger.debug("successfully purged service instance: %s", service_instance)

            self.storage.remove_stopped_instances_gsma(app_id)

            self.storage.delete_app_gsma(app_id)

            return build_custom_http_response(
                status_code=204,
                content=b"",
                headers={},
                encoding=None,
            )
        except EdgeCloudPlatformError as e:
            self.logger.error("Error deleting GSMA app '%s': %s", app_id, e)
            raise
        except Exception as e:
            self.logger.exception("Unhandled error deleting GSMA app '%s': %s", app_id, e)
            raise EdgeCloudPlatformError(str(e))

    def _purge_deployed_app_from_continuum_gsma(self, app_instance_id: str) -> None:
        """
        Purge the deployed application from aerOS continuum.
        :param app_id: The application ID to purge
        All instances of this app should be stopped
        """
        aeros_client = ContinuumClient(self.base_url)
        response = aeros_client.purge_service(app_instance_id)
        if response:
            self.logger.debug("Purged deployed application with id: %s", app_instance_id)
        else:
            raise EdgeCloudPlatformError(
                f"Failed to purge service with id from the continuum '{app_instance_id}'"
            )

    # ------------------------------------------------------------------------
    # Application Deployment Management (GSMA)
    # ------------------------------------------------------------------------

    def deploy_app_gsma(self, request_body: dict) -> Dict:
        """
        Instantiates an application on a partner OP zone.

        :param request_body: Payload with deployment info.
        :return: Dictionary with deployment details.
        """
        try:
            payload = gsma_schemas.AppDeployPayloadGSMA.model_validate(request_body)
        except ValidationError as e:
            self.logger.error("Invalid GSMA deploy schema: %s", e)
            raise InvalidArgumentError(str(e))

        try:
            # Ensure app exists
            onboarded_app = self.storage.get_app_gsma(payload.appId)
            if not onboarded_app:
                raise ResourceNotFoundError(f"GSMA app '{payload.appId}' not found")

            # 2. Generate unique service ID
            #    (aerOS) service id <=> GSMA appInstanceId
            service_id = self._generate_aeros_service_id(
                self._generate_service_id(onboarded_app.appId)
            )

            # 3. Create TOSCA (yaml str) from GSMA onboarded_app + connected artefacts
            #    GSMA app corresponds to aerOS Service
            #    Each GSMA AppComponentSpec references an artefact which is mapped to aerOS Service Component
            tosca_yaml = gsma2aeros_converter.generate_tosca_from_gsma_with_artefacts(
                app_model=onboarded_app,
                zone_id=payload.zoneInfo.zoneId,
                artefact_resolver=self.storage.get_artefact_gsma,  # cleaner
            )
            self.logger.info("Generated TOSCA YAML:")
            self.logger.info(tosca_yaml)

            # 4. Instantiate client and call continuum to deploy servic
            aeros_client = ContinuumClient(self.base_url)
            aeros_response = aeros_client.onboard_and_deploy_service(
                service_id, tosca_str=tosca_yaml
            )

            if "serviceId" not in aeros_response.json():
                raise EdgeCloudPlatformError(
                    "Invalid response from onboard_service: missing 'serviceId'"
                )

            # 5. Track deployment (Store in GSMA deployment store)
            # Build AppInstance and optional status (if you want to persist status later)
            inst = gsma_schemas.AppInstance(
                zoneId=payload.zoneInfo.zoneId,
                appInstIdentifier=service_id,
            )
            status = gsma_schemas.AppInstanceStatus(
                appInstanceState="PENDING",
                accesspointInfo=[],
            )

            self.storage.store_deployment_gsma(onboarded_app.appId, inst, status=status)

            # 6. Return expected format (deployment details)
            body = inst.model_dump(mode="json")

            return build_custom_http_response(
                status_code=202,
                content=body,
                headers={"Content-Type": self.content_type_gsma},
                encoding=self.encoding_gsma,
                url=aeros_response.json().get("url", ""),
                request=aeros_response.request,
            )
        except EdgeCloudPlatformError as ex:
            self.logger.error("Failed to deploy app '%s': %s", onboarded_app.appId, str(ex))
            raise
        except Exception as e:
            self.logger.exception("Unhandled error during GSMA deploy: %s", e)
            raise EdgeCloudPlatformError(str(e))

    def get_deployed_app_gsma(self, app_id: str, app_instance_id: str, zone_id: str) -> Dict:
        """
        Retrieves an application instance details from partner OP.

        :param app_id: Identifier of the app.
        :param app_instance_id: Identifier of the deployed instance.
        :param zone_id: Identifier of the zone
        :return: Dictionary with application instance details
        """
        try:
            # Ensure app exists
            if not self.storage.get_app_gsma(app_id):
                raise ResourceNotFoundError(f"GSMA app '{app_id}' not found")

            # 4. Instantiate client and call continuum to deploy servic
            aeros_client = ContinuumClient(self.base_url)
            aeros_response = aeros_client.query_entity(
                entity_id=app_instance_id, ngsild_params="format=simplified"
            )

            response_json = aeros_response.json()
            content = gsma_schemas.AppInstanceStatus(
                appInstanceState=map_aeros_service_status_to_gsma(response_json.get("actionType")),
                accesspointInfo=[
                    {"service_status": f"{self.base_url}/entities/{app_instance_id}"},
                    {
                        "serviceComponents_status": f"{self.base_url}/hlo_fe/services//{app_instance_id}"
                    },
                ],
            )

            validated_data = gsma_schemas.AppInstanceStatus.model_validate(content)

            return build_custom_http_response(
                status_code=200,
                content=validated_data.model_dump(mode="json"),
                headers={"Content-Type": self.content_type_gsma},
                encoding=self.encoding_gsma,
                url=aeros_response.url,
                request=aeros_response.request,
            )
        except EdgeCloudPlatformError:
            raise
        except Exception as e:
            self.logger.exception(
                "Unhandled error retrieving GSMA deployment '%s' (%s/%s): %s",
                app_instance_id,
                app_id,
                zone_id,
                e,
            )
            raise EdgeCloudPlatformError(str(e))

    def get_all_deployed_apps_gsma(self) -> Response:
        """
        Retrieves all instances for a given application of partner OP

        :param app_id: Identifier of the app.
        :param app_provider: App provider
        :return: List with application instances details
        """
        try:
            insts = self.storage.find_deployments_gsma()
            body = [i.model_dump(mode="json") for i in insts]
            self.logger.info("All GSMA app instances retrieved successfully")
            self.logger.debug("Deployed GSMA applications: %s", body)

            return build_custom_http_response(
                status_code=200,
                content=body,
                headers={"Content-Type": self.content_type_gsma},
                encoding=self.encoding_gsma,
            )
        except EdgeCloudPlatformError:
            raise
        except Exception as e:
            self.logger.exception("Unhandled error listing GSMA deployments: '%s'", e)
            raise EdgeCloudPlatformError(str(e))

    def undeploy_app_gsma(self, app_id: str, app_instance_id: str, zone_id: str):
        """
        Terminate an application instance on a partner OP zone.

        :param app_id: Identifier of the app.
        :param app_instance_id: Identifier of the deployed app.
        :param zone_id: Identifier of the zone
        :return:
        """
        try:
            # Ensure app exists
            if not self.storage.get_app_gsma(app_id):
                raise ResourceNotFoundError(f"GSMA app '{app_id}' not found")

            # Ensure the (app_id, instance, zone) exists
            matches = self.storage.find_deployments_gsma(
                app_id=app_id, app_instance_id=app_instance_id, zone_id=zone_id
            )
            if not matches:
                raise ResourceNotFoundError(
                    f"Deployment not found (app_id={app_id}, instance={app_instance_id}, zone={zone_id})"
                )

            # 2. Call the external undeploy_service
            aeros_client = ContinuumClient(self.base_url)
            try:
                aeros_response = aeros_client.undeploy_service(app_instance_id)
            except Exception as e:
                raise EdgeCloudPlatformError(
                    f"Failed to undeploy app instance '{app_instance_id}': {str(e)}"
                ) from e

            # Remove from deployed and mark as stopped so it can be purged later
            removed_app_id = self.storage.remove_deployment_gsma(app_instance_id)
            if removed_app_id:
                self.storage.store_stopped_instance_gsma(removed_app_id, app_instance_id)

            # Async-friendly: 202 Accepted (termination in progress)
            body = {
                "appId": app_id,
                "appInstIdentifier": app_instance_id,
                "zoneId": zone_id,
                "state": "TERMINATING",
            }
            return build_custom_http_response(
                status_code=aeros_response.status_code,
                content=body,
                headers={"Content-Type": self.content_type_gsma},
                encoding=self.encoding_gsma,
            )
        except EdgeCloudPlatformError:
            raise
        except Exception as e:
            self.logger.exception(
                "Unhandled error undeploying GSMA app instance '%s' (app=%s zone=%s): %s",
                app_instance_id,
                app_id,
                zone_id,
                e,
            )
            raise EdgeCloudPlatformError(str(e))
