# -*- coding: utf-8 -*-
##
# free5GC 5G Core Network Adapter for TF-SDK
#
# free5GC CAMARA API Support (via free5GC's own built-in NEF):
#   Supported:     traffic_influence   (NEF exposes /3gpp-traffic-influence/v1)
#   Not supported: qod, location_retrieval, number_verification, sim_swap, device_status
#
# free5GC's built-in NEF (NFs/nef/internal/sbi/api_ti.go) does NOT expose:
#   /3gpp-as-session-with-qos   → needed for QoD
#   /3gpp-monitoring-event      → needed for Location Retrieval
##
from sunrise6g_opensdk import logger
from sunrise6g_opensdk.network.core.base_network_client import BaseNetworkClient
from sunrise6g_opensdk.network.core import schemas

log = logger.get_logger(__name__)


class Free5GCValidationError(Exception):
    """Raised when free5GC-specific validation fails."""
    pass


class NetworkManager(BaseNetworkClient):
    """
    TF-SDK adapter for free5GC 5G Core.

    Uses free5GC's own built-in NEF for Traffic Influence via
    /3gpp-traffic-influence/v1 (api_ti.go).

    Not supported (free5GC's NEF lacks these SCEF routes):
      - QoD       — no /3gpp-as-session-with-qos
      - Location  — no /3gpp-monitoring-event
      - Number Verification, SIM Swap, Device Status
    """

    # free5GC's built-in NEF (NFs/nef) exposes:
    #   /3gpp-traffic-influence/v1   → supported ✅
    #   /3gpp-pfd-management/v1      → supported (not used by TF-SDK)
    # It does NOT expose:
    #   /3gpp-as-session-with-qos    → QoD ❌
    #   /3gpp-monitoring-event       → Location ❌
    capabilities = {"traffic_influence"}

    def __init__(
        self,
        base_url: str = "http://free5gc-nef:8000",
        scs_as_id: str = "camara-dashboard",
        dnn: str = "internet",
        plmn_mcc: str = "208",
        plmn_mnc: str = "93",
    ):
        """
        Initialise the free5GC adapter.

        free5GC's own NEF handles Traffic Influence via
        ``/3gpp-traffic-influence/v1`` (api_ti.go).  QoD and Location
        Retrieval are not exposed by free5GC's NEF, so those CAMARA APIs
        are not supported by this adapter.

        Args:
            base_url:  free5GC NEF SBI base URL (default: http://free5gc-nef:8000).
            scs_as_id: AF identifier sent as path param in TI subscriptions.
            dnn:       Data Network Name configured in free5GC SMF.
            plmn_mcc:  Mobile Country Code of the deployed PLMN.
            plmn_mnc:  Mobile Network Code of the deployed PLMN.
        """
        try:
            self.base_url = base_url
            self.scs_as_id = scs_as_id
            self.dnn = dnn
            self.plmn_mcc = plmn_mcc
            self.plmn_mnc = plmn_mnc

            log.info(
                f"Initialised free5GC NetworkManager\n"
                f"  NEF base_url : {self.base_url}\n"
                f"  scs_as_id    : {self.scs_as_id}\n"
                f"  DNN          : {self.dnn}\n"
                f"  PLMN         : {self.plmn_mcc}/{self.plmn_mnc}"
            )
        except Exception as e:
            log.error(f"Failed to initialise free5GC NetworkManager: {e}")
            raise

    # ------------------------------------------------------------------
    # Traffic Influence — free5GC NEF /3gpp-traffic-influence/v1 (api_ti.go)
    # QoD and Location are NOT supported (no /3gpp-as-session-with-qos or
    # /3gpp-monitoring-event routes in free5GC's built-in NEF).
    # ------------------------------------------------------------------

    def core_specific_traffic_influence_validation(
        self, traffic_influence_info: schemas.CreateTrafficInfluence
    ) -> None:
        if (
            traffic_influence_info.device is None
            or traffic_influence_info.device.ipv4Address is None
        ):
            raise Free5GCValidationError(
                "free5GC Traffic Influence requires UE IPv4 address"
            )

    def add_core_specific_ti_parameters(
        self,
        traffic_influence_info: schemas.CreateTrafficInfluence,
        subscription: schemas.TrafficInfluSub,
    ) -> None:
        """Map CAMARA Traffic Influence to free5GC NEF TI subscription.

        free5GC NEF registers /3gpp-traffic-influence/v1/{afID}/subscriptions
        (confirmed in NFs/nef/internal/sbi/api_ti.go and factory/config.go).
        The base_url is the NEF SBI endpoint; the common layer appends the
        correct path automatically.
        """
        subscription.dnn = self.dnn
        subscription.add_snssai(1, "000001")  # free5GC default slice (SST=1, SD=000001)
        subscription.afServiceId = self.scs_as_id
        # free5GC PCF requires non-empty SuppFeat in AppSessionContext (api_policyauthorization.go:112)
        if not subscription.suppFeat:
            subscription.suppFeat = "0"
        # free5GC PCF does session-binding for UE-specific policies (requires active PDU session).
        # In a lab environment without real UEs, use anyUeInd=True so the subscription is stored
        # and applies when any UE connects.  The UE IP is still used in the flow filter.
        subscription.anyUeInd = True
        subscription.ipv4Addr = None
        # free5GC NEF requires at least one trafficRoute; supply a default if none was built
        # (happens when the dashboard form doesn't set edgeCloudZoneId)
        if not subscription.trafficRoutes:
            subscription.add_traffic_route(dnai="DNAI1")
