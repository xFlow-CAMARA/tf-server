# -*- coding: utf-8 -*-
##
#
# This file is part of the TF SDK
#
# Contributors:
#   - Ferran Cañellas (ferran.canellas@i2cat.net)
#   - Panagiotis Pavlidis (p.pavlidis@iit.demokritos.gr)
##
from pydantic import ValidationError

from sunrise6g_opensdk import logger
from sunrise6g_opensdk.network.core.base_network_client import (
    BaseNetworkClient,
    build_flows,
)

from ...core import schemas

log = logger.get_logger(__name__)

flow_id_mapping = {"qos-e": 3, "qos-s": 4, "qos-m": 5, "qos-l": 6}


class NetworkManager(BaseNetworkClient):
    """
    This client implements the BaseNetworkClient and translates the
    CAMARA APIs into specific HTTP requests understandable by the Open5GS NEF API.
    """

    capabilities = {"qod", "location_retrieval"}

    def __init__(self, base_url: str, scs_as_id):
        """
        Initializes the Open5GS Client.
        """
        try:
            self.base_url = base_url
            self.scs_as_id = scs_as_id
            log.info(
                f"Initialized Open5GSClient with base_url: {self.base_url} "
                f"and scs_as_id: {self.scs_as_id}"
            )
        except Exception as e:
            log.error(f"Failed to initialize Open5GSClient: {e}")
            raise e

    def core_specific_qod_validation(self, session_info: schemas.CreateSession):
        if session_info.qosProfile.root not in flow_id_mapping.keys():
            raise ValidationError(
                f"Open5Gs only supports these qos-profiles: {', '.join(flow_id_mapping.keys())}"
            )

    def add_core_specific_qod_parameters(
        self,
        session_info: schemas.CreateSession,
        subscription: schemas.AsSessionWithQoSSubscription,
    ) -> None:
        subscription.supportedFeatures = schemas.SupportedFeatures("003C")
        flow_id = flow_id_mapping[session_info.qosProfile.root]
        subscription.flowInfo = build_flows(flow_id, session_info)

    def core_specific_monitoring_event_validation(
        self, retrieve_location_request: schemas.RetrievalLocationRequest
    ) -> None:
        """Check core specific elements that required for location retrieval in NEF."""
        if retrieve_location_request.device is None:
            raise ValidationError(
                "Open5GS requires a device to be specified for location retrieval in NEF."
            )

    def add_core_specific_location_parameters(
        self, retrieve_location_request: schemas.RetrievalLocationRequest
    ) -> schemas.MonitoringEventSubscriptionRequest:
        """Add core specific location parameters to support location retrieval scenario in NEF."""
        return schemas.MonitoringEventSubscriptionRequest(
            msisdn=retrieve_location_request.device.phoneNumber.root.lstrip("+"),
            notificationDestination="http://127.0.0.1:8001",
            monitoringType=schemas.MonitoringType.LOCATION_REPORTING,
            locationType=schemas.LocationType.LAST_KNOWN,
        )
        # subscription.msisdn = retrieve_location_request.device.phoneNumber.root.lstrip('+')
        # monitoringType = schemas.MonitoringType.LOCATION_REPORTING
        # locationType = schemas.LocationType.LAST_KNOWN
        # locationType = schemas.LocationType.CURRENT_LOCATION
        # maximumNumberOfReports = 1
        # repPeriod = schemas.DurationSec(root=20)
