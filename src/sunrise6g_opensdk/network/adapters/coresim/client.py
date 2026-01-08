# -*- coding: utf-8 -*-
##
# This file is part of the TF SDK
#
# Contributors:
#   - Auto-generated for CoreSim support
##
import uuid
from typing import Dict, Optional

import requests
from pydantic import ValidationError

from sunrise6g_opensdk import logger
from sunrise6g_opensdk.network.adapters.errors import NetworkPlatformError
from sunrise6g_opensdk.network.core.base_network_client import (
    BaseNetworkClient,
    build_flows,
)
from sunrise6g_opensdk.network.core import schemas, common

log = logger.get_logger(__name__)


class NetworkManager(BaseNetworkClient):
    """
    This client implements the BaseNetworkClient and translates the
    CAMARA APIs into specific HTTP requests understandable by the CoreSim 5G Core Simulator.
    
    CoreSim Architecture:
    - CoreSim runs on ports 8080 (SBI APIs) and 8081 (OAM APIs)
    - NEF (Network Exposure Function) services integrate with CoreSim via 3GPP APIs
    - Core-Network-Service subscribes to AMF/SMF events from CoreSim
    - Data persists in Redis (port 6379 in docker network, 6380 externally)
    - UE IPs are allocated from 12.1.0.0/16 subnet by CoreSim IPAM
    
    3GPP APIs supported:
    - Nsmf_EventExposure (TS 29.502) - Session management
    - Namf_Events (TS 29.518) - UE mobility and registration
    - Npcf_PolicyAuthorization (TS 29.514) - Policy control
    
    Known Constraints:
    - QoD payloads must include 'dnn' field (required by NEF)
    - QoD payloads must include 'flowInfo' with flowId and flowDescriptions array
    - UE IPs must be from 12.1.0.0/16 range (CoreSim's IPAM allocation subnet)
    """

    capabilities = {"qod", "location_retrieval", "traffic_influence", "core_control"}

    def __init__(
        self,
        base_url: str = "http://core-simulator:8080",
        scs_as_id: str = "nef",
        oam_port: int = 8081,
        metrics_port: int = 9090,
        redis_addr: str = "redis:6379",
        nef_callback_url: str = "http://core-network-service:9090/eventsubscriptions",
        qod_base_url: str = "http://localhost:8100",
        location_base_url: str = "http://localhost:8102",
        ti_base_url: str = "http://localhost:8101",
        ue_identity_base_url: str = "http://localhost:8103",
    ):
        """
        Initializes the CoreSim Network Manager for NEF integration.
        
        Args:
            base_url: CoreSim SBI base URL (default: docker internal http://core-simulator:8080)
            scs_as_id: NEF service identifier (default: nef)
            oam_port: CoreSim OAM API port (default: 8081)
            metrics_port: CoreSim Prometheus metrics port (default: 9090)
            redis_addr: Redis service address for data persistence
            nef_callback_url: Callback URL for event notifications
            qod_base_url: NEF QoD service base URL (default: http://localhost:8100)
            location_base_url: NEF Location monitoring service base URL (default: http://localhost:8102)
            ti_base_url: NEF Traffic Influence service base URL (default: http://localhost:8101)
            ue_identity_base_url: NEF UE Identity service base URL (default: http://localhost:8103)
        """
        try:
            self.base_url = base_url
            self.scs_as_id = scs_as_id
            self.oam_port = oam_port
            self.metrics_port = metrics_port
            self.redis_addr = redis_addr
            self.nef_callback_url = nef_callback_url
            
            # NEF CAMARA API service URLs
            self.qod_base_url = qod_base_url
            self.location_base_url = location_base_url
            self.ti_base_url = ti_base_url
            self.ue_identity_base_url = ue_identity_base_url
            
            # Extract host from base_url for OAM and metrics APIs
            self.oam_base_url = base_url.rsplit(":", 1)[0] + f":{oam_port}"
            self.metrics_url = base_url.rsplit(":", 1)[0] + f":{metrics_port}/metrics"
            
            log.info(
                f"Initialized CoreSim NetworkManager for NEF\n"
                f"  SBI base_url: {self.base_url}\n"
                f"  OAM base_url: {self.oam_base_url}\n"
                f"  QoD service: {self.qod_base_url}\n"
                f"  Location service: {self.location_base_url}\n"
                f"  Traffic Influence service: {self.ti_base_url}\n"
                f"  UE Identity service: {self.ue_identity_base_url}\n"
                f"  Redis: {self.redis_addr}\n"
                f"  Callback: {self.nef_callback_url}"
            )
        except Exception as e:
            log.error(f"Failed to initialize CoreSim NetworkManager: {e}")
            raise e

    def _oam_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """
        Make a request to the CoreSim OAM API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Optional request body
            
        Returns:
            Response JSON as dictionary
            
        Raises:
            NetworkPlatformError: On HTTP or connection errors
        """
        url = f"{self.oam_base_url}/core-simulator/v1{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        try:
            response = requests.request(method, url, headers=headers, json=data)
            response.raise_for_status()
            if response.content:
                return response.json()
            return {}
        except requests.exceptions.HTTPError as e:
            raise NetworkPlatformError(f"CoreSim OAM API error: {e}") from e
        except requests.exceptions.ConnectionError as e:
            raise NetworkPlatformError(f"Failed to connect to CoreSim OAM API: {e}") from e

    def get_status(self) -> Dict:
        """
        Get the current CoreSim simulation status.
        
        Returns:
            Dictionary containing simulation status (e.g., CONFIGURED, RUNNING, STOPPED)
        """
        try:
            status = self._oam_request("GET", "/status")
            log.info(f"CoreSim status: {status}")
            return status
        except Exception as e:
            log.error(f"Failed to get CoreSim status: {e}")
            raise

    def start_simulation(self) -> Dict:
        """
        Start the CoreSim simulation and trigger NEF service subscriptions.
        
        Returns:
            Dictionary with start response
        """
        try:
            # Check current status
            status = self.get_status()
            current_state = status.get('Status', 'UNKNOWN')
            
            # If already started, just return
            if current_state == 'STARTED':
                log.info("CoreSim simulation already running")
                return status
            
            # Try to start - if it fails, might need container restart
            response = self._oam_request("POST", "/start")
            log.info("CoreSim simulation started - NEF services subscribing to events")
            return response
        except Exception as e:
            log.error(f"Failed to start CoreSim simulation: {e}")
            raise

    def stop_simulation(self) -> Dict:
        """
        Stop the CoreSim simulation.
        
        Returns:
            Dictionary with stop response
        """
        try:
            response = self._oam_request("POST", "/stop")
            log.info("CoreSim simulation stopped")
            return response
        except Exception as e:
            log.error(f"Failed to stop CoreSim simulation: {e}")
            raise

    def configure_simulation(self, config: Dict) -> Dict:
        """
        Configure CoreSim simulation parameters before starting.
        
        Args:
            config: Configuration dictionary with PLMN, DNN, slice info, UE/gNB counts, etc.
            
        Returns:
            Dictionary with configure response
        """
        try:
            response = self._oam_request("POST", "/configure", data=config)
            log.info(f"CoreSim configured: {response}")
            return response
        except Exception as e:
            log.error(f"Failed to configure CoreSim: {e}")
            raise

    # CAMARA Number Verification API support
    def get_msisdn_by_ip(self, ip_address: str) -> str:
        """
        Get the MSISDN (phone number) for a UE by its IP address.
        
        This method queries the UE Identity Service to resolve IP → MSISDN.
        Used by CAMARA Number Verification API.
        
        Args:
            ip_address: The UE's IP address (e.g., "12.1.0.2")
            
        Returns:
            MSISDN in E.164 format (e.g., "+33612345678")
            
        Raises:
            NetworkPlatformError: If the MSISDN cannot be found
        """
        try:
            url = f"{self.ue_identity_base_url}/msisdn?ip={ip_address}"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            msisdn = data.get("Msisdn")
            if not msisdn:
                raise NetworkPlatformError(f"No MSISDN found for IP {ip_address}")
            log.info(f"Resolved IP {ip_address} to MSISDN {msisdn}")
            return msisdn
        except requests.exceptions.HTTPError as e:
            raise NetworkPlatformError(f"Failed to resolve MSISDN for IP {ip_address}: {e}") from e
        except requests.exceptions.ConnectionError as e:
            raise NetworkPlatformError(f"Failed to connect to UE Identity Service: {e}") from e

    def _get_ue_profile_from_metrics(self, ip_address: str) -> Optional[Dict]:
        """
        Fallback method: Get UE profile from CoreSim metrics.
        
        This is used when ue-identity-service and ue-profile-service don't have the UE data.
        Parses the Prometheus metrics from CoreSim to find UE info and returns a simulated profile.
        
        Args:
            ip_address: The UE's IP address
            
        Returns:
            Dictionary with simulated UE profile, or None if UE not found
        """
        import re
        
        try:
            # Query CoreSim metrics
            metrics_url = f"{self.metrics_url}"
            response = requests.get(metrics_url, timeout=5)
            
            if response.status_code != 200:
                return None
            
            metrics_text = response.text
            
            # Parse ue_ip_info metric to find UE by IP
            # Format: ue_ip_info{imsi="001010000000001",ip="12.1.0.1",...} 1
            pattern = r'ue_ip_info\{imsi="([^"]+)",ip="([^"]+)"[^}]*\}\s+1'
            
            for match in re.finditer(pattern, metrics_text):
                imsi = match.group(1)
                ip = match.group(2)
                
                if ip == ip_address:
                    # Found the UE - return simulated profile
                    # For CoreSim, assume all UEs are registered and connected
                    log.info(f"Found UE in CoreSim metrics: IMSI={imsi}, IP={ip}")
                    
                    # Generate MSISDN from IMSI (CoreSim convention)
                    msisdn = f"+336{imsi[-8:]}"
                    
                    return {
                        "Supi": imsi,
                        "Msisdn": msisdn,
                        "IpAddress": ip_address,
                        "RegistrationStatus": "REGISTERED",
                        "ConnectionStatus": "CONNECTED",
                        "Plmn": {"mcc": "001", "mnc": "06"},
                        "PduSessions": {"default": {"dnn": "internet", "state": "active"}}
                    }
            
            return None
            
        except Exception as e:
            log.warning(f"Failed to get UE profile from metrics: {e}")
            return None

    # CAMARA Device Status API support
    def get_ue_profile_by_ip(self, ip_address: str) -> Dict:
        """
        Get UE profile (status, registration, PLMN) by IP address.
        
        Used by CAMARA Device Status API to check reachability and roaming status.
        
        Args:
            ip_address: The UE's IP address (e.g., "12.1.0.1")
            
        Returns:
            Dictionary with UE profile data including:
            - Supi: IMSI identifier
            - RegistrationStatus: "REGISTERED" or "DEREGISTERED"
            - ConnectionStatus: "CONNECTED" or "IDLE"
            - Plmn: {"mcc": "xxx", "mnc": "xx"}
            - PduSessions: Active PDU session info
            
        Raises:
            NetworkPlatformError: If UE profile cannot be found
        """
        # Try ue-identity-service first
        try:
            # First resolve IP to SUPI via ue-identity-service
            url = f"{self.ue_identity_base_url}/ue-identity/v1/supi?ip={ip_address}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                supi = data.get("Supi") or data.get("supi")
                
                if supi:
                    return self.get_ue_profile_by_supi(supi)
            
            # Fallback: Try to get profile from Redis/CoreSim directly
            # Query ue-identity-service for full profile
            url = f"{self.ue_identity_base_url}/ue-identity/v1/profile?ip={ip_address}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                return response.json()
                
        except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            log.debug(f"UE Identity Service not available, trying metrics fallback: {e}")
        
        # Fallback: Check CoreSim metrics for UE existence and return simulated profile
        profile = self._get_ue_profile_from_metrics(ip_address)
        if profile:
            return profile
        
        raise NetworkPlatformError(f"No UE profile found for IP {ip_address}")

    def get_ue_profile_by_supi(self, supi: str) -> Dict:
        """
        Get UE profile by SUPI (IMSI).
        
        Args:
            supi: IMSI identifier (e.g., "001010000000001")
            
        Returns:
            Dictionary with UE profile data
            
        Raises:
            NetworkPlatformError: If UE profile cannot be found
        """
        try:
            # Try ue-profile-service first (if available)
            ue_profile_url = "http://ue-profile-service:8080"
            url = f"{ue_profile_url}/ue-profile/v1/profiles/{supi}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                return response.json()
            
            # Fallback: Query ue-identity-service
            url = f"{self.ue_identity_base_url}/ue-identity/v1/profile?supi={supi}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                return response.json()
            
            raise NetworkPlatformError(f"No UE profile found for SUPI {supi}")
            
        except requests.exceptions.HTTPError as e:
            raise NetworkPlatformError(f"Failed to get UE profile for SUPI {supi}: {e}") from e
        except requests.exceptions.ConnectionError as e:
            raise NetworkPlatformError(f"Failed to connect to profile service: {e}") from e

    def get_ue_profile_by_msisdn(self, msisdn: str) -> Dict:
        """
        Get UE profile by MSISDN (phone number).
        
        Args:
            msisdn: Phone number in E.164 format (e.g., "+33612345678")
            
        Returns:
            Dictionary with UE profile data
            
        Raises:
            NetworkPlatformError: If UE profile cannot be found
        """
        try:
            # Query ue-identity-service for SUPI by MSISDN
            url = f"{self.ue_identity_base_url}/ue-identity/v1/supi?msisdn={msisdn}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                supi = data.get("Supi") or data.get("supi")
                if supi:
                    return self.get_ue_profile_by_supi(supi)
            
            raise NetworkPlatformError(f"No UE profile found for MSISDN {msisdn}")
            
        except requests.exceptions.HTTPError as e:
            raise NetworkPlatformError(f"Failed to get UE profile for MSISDN {msisdn}: {e}") from e
        except requests.exceptions.ConnectionError as e:
            raise NetworkPlatformError(f"Failed to connect to UE Identity Service: {e}") from e

    def get_device_reachability_status(self, ip_address: str) -> Dict:
        """
        Get device reachability status for CAMARA Device Status API.
        
        Args:
            ip_address: The UE's IP address
            
        Returns:
            Dictionary with:
            - reachabilityStatus: "CONNECTED_DATA", "CONNECTED_SMS", or "NOT_CONNECTED"
            - lastStatusTime: ISO 8601 timestamp
        """
        from datetime import datetime, timezone
        
        try:
            profile = self.get_ue_profile_by_ip(ip_address)
            
            conn_status = profile.get("ConnectionStatus", "").upper()
            reg_status = profile.get("RegistrationStatus", "").upper()
            
            # Map to CAMARA ConnectivityStatus
            if reg_status in ["DEREGISTERED", "NOT_REGISTERED"]:
                status = "NOT_CONNECTED"
            elif conn_status == "CONNECTED":
                pdu_sessions = profile.get("PduSessions", {})
                if pdu_sessions and len(pdu_sessions) > 0:
                    status = "CONNECTED_DATA"
                else:
                    status = "CONNECTED_SMS"
            elif conn_status == "IDLE":
                status = "CONNECTED_SMS"
            else:
                status = "NOT_CONNECTED"
            
            return {
                "reachabilityStatus": status,
                "lastStatusTime": datetime.now(timezone.utc).isoformat()
            }
            
        except NetworkPlatformError:
            return {
                "reachabilityStatus": "NOT_CONNECTED",
                "lastStatusTime": datetime.now(timezone.utc).isoformat()
            }

    def get_device_roaming_status(self, ip_address: str, home_mcc: str = "001", home_mnc: str = "06") -> Dict:
        """
        Get device roaming status for CAMARA Device Status API.
        
        Args:
            ip_address: The UE's IP address
            home_mcc: Home PLMN MCC (default: "001" for test network)
            home_mnc: Home PLMN MNC (default: "06")
            
        Returns:
            Dictionary with:
            - roaming: bool
            - countryCode: ISO 3166-1 alpha-2 code (optional)
            - countryName: List of country names (optional)
        """
        MCC_COUNTRY_MAP = {
            "001": {"code": "XX", "name": "Test Network"},
            "208": {"code": "FR", "name": "France"},
            "310": {"code": "US", "name": "United States"},
            "311": {"code": "US", "name": "United States"},
            "234": {"code": "GB", "name": "United Kingdom"},
            "262": {"code": "DE", "name": "Germany"},
            "222": {"code": "IT", "name": "Italy"},
            "214": {"code": "ES", "name": "Spain"},
            "505": {"code": "AU", "name": "Australia"},
            "440": {"code": "JP", "name": "Japan"},
            "450": {"code": "KR", "name": "South Korea"},
            "460": {"code": "CN", "name": "China"},
        }
        
        try:
            profile = self.get_ue_profile_by_ip(ip_address)
            
            plmn = profile.get("Plmn", {})
            current_mcc = plmn.get("mcc", "") or plmn.get("Mcc", "")
            current_mnc = plmn.get("mnc", "") or plmn.get("Mnc", "")
            
            if not current_mcc:
                return {"roaming": False}
            
            # Check if roaming (different from home PLMN)
            is_roaming = (current_mcc != home_mcc) or (current_mnc != home_mnc)
            
            # Get country info
            country_info = MCC_COUNTRY_MAP.get(current_mcc, {"code": "XX", "name": "Unknown"})
            
            return {
                "roaming": is_roaming,
                "countryCode": country_info["code"],
                "countryName": [country_info["name"]]
            }
            
        except NetworkPlatformError:
            return {"roaming": False}

    def verify_phone_number(self, ip_address: str, phone_number: str = None, hashed_phone_number: str = None) -> bool:
        """
        Verify if the provided phone number matches the UE's actual phone number.
        
        Used by CAMARA Number Verification API.
        
        Args:
            ip_address: The UE's IP address (from network authentication)
            phone_number: Phone number in E.164 format to verify (optional)
            hashed_phone_number: SHA-256 hash of phone number to verify (optional)
            
        Returns:
            True if the phone number matches, False otherwise
            
        Raises:
            ValueError: If neither phone_number nor hashed_phone_number is provided
            NetworkPlatformError: On connection/lookup errors
        """
        import hashlib
        
        if not phone_number and not hashed_phone_number:
            raise ValueError("Either phone_number or hashed_phone_number must be provided")
        
        # Get the actual MSISDN from network
        actual_msisdn = self.get_msisdn_by_ip(ip_address)
        
        if phone_number:
            # Direct comparison
            return actual_msisdn == phone_number
        
        if hashed_phone_number:
            # Hash comparison
            actual_hash = hashlib.sha256(actual_msisdn.encode('utf-8')).hexdigest()
            return actual_hash.lower() == hashed_phone_number.lower()
        
        return False

    # CAMARA QoD API support (inherited from BaseNetworkClient)
    def add_core_specific_qod_parameters(
        self,
        session_info: schemas.CreateSession,
        subscription: schemas.AsSessionWithQoSSubscription,
    ) -> None:
        """
        Add CoreSim-specific QoD parameters.
        CoreSim supports flexible QoD profiles aligned with 3GPP standards.
        """
        # CoreSim supports all standard QoS profiles
        # Add support for monitoring and metrics collection
        subscription.supportedFeatures = schemas.SupportedFeatures("0C")
        
        # Build flow information for CoreSim (3GPP aligned)
        flow_id = 1  # Default flow ID for CoreSim
        subscription.flowInfo = self._build_coresim_flows(flow_id, session_info)

    def core_specific_qod_validation(self, session_info: schemas.CreateSession) -> None:
        """
        Validate CoreSim-specific QoD requirements.
        CoreSim is flexible with QoD parameters as it supports 3GPP standards.
        """
        if session_info.qosProfile is None:
            raise ValidationError("QoS profile is required")
        
        # CoreSim supports standard 5QI values
        valid_profiles = ["qos-e", "qos-s", "qos-m", "qos-l"]
        if session_info.qosProfile.root not in valid_profiles:
            log.warning(f"Non-standard QoS profile: {session_info.qosProfile.root}")

    def _build_coresim_flows(self, flow_id: int, session_info: schemas.CreateSession):
        """
        Build flow descriptors compatible with CoreSim's 3GPP implementation.
        """
        from sunrise6g_opensdk.network.core.base_network_client import build_flows
        return build_flows(flow_id, session_info)

    # CAMARA Location API support
    def add_core_specific_location_parameters(
        self, retrieve_location_request: schemas.RetrievalLocationRequest
    ) -> schemas.MonitoringEventSubscriptionRequest:
        """
        Add CoreSim-specific location monitoring parameters.
        CoreSim implements 3GPP location reporting aligned with TS 29.518 (Namf_Events).
        """
        device = retrieve_location_request.device
        
        # Extract device identifiers
        msisdn = None
        if hasattr(device, 'phoneNumber') and device.phoneNumber:
            msisdn = device.phoneNumber.root.lstrip("+")
        
        external_id = getattr(device, 'networkAccessIdentifier', None)
        if external_id:
            external_id = external_id.root if hasattr(external_id, 'root') else str(external_id)
        
        return schemas.MonitoringEventSubscriptionRequest(
            msisdn=msisdn,
            externalId=external_id,
            notificationDestination="http://127.0.0.1:8001",
            monitoringType=schemas.MonitoringType.LOCATION_REPORTING,
            # locationType is not properly supported by NEF monitoring-event service (empty struct in Go)
            # locationType=schemas.LocationType.LAST_KNOWN,
        )

    def core_specific_monitoring_event_validation(
        self, retrieve_location_request: schemas.RetrievalLocationRequest
    ) -> None:
        """
        Validate CoreSim-specific monitoring event requirements.
        CoreSim requires device identifiers for location tracking.
        """
        device = retrieve_location_request.device
        if device is None:
            raise ValidationError("Device information is required for location monitoring")
        
        # At least one identifier required
        has_msisdn = hasattr(device, 'phoneNumber') and device.phoneNumber
        has_nai = hasattr(device, 'networkAccessIdentifier') and device.networkAccessIdentifier
        
        if not (has_msisdn or has_nai):
            raise ValidationError(
                "CoreSim requires either phoneNumber or networkAccessIdentifier for location monitoring"
            )

    # CAMARA Traffic Influence API support
    def add_core_specific_ti_parameters(
        self,
        traffic_influence_info: schemas.CreateTrafficInfluence,
        subscription: schemas.TrafficInfluSub,
    ) -> None:
        """
        Add CoreSim-specific traffic influence parameters.
        CoreSim supports traffic routing and policy enforcement aligned with 3GPP TS 29.514.
        """
        # CoreSim can track additional metadata for traffic influence
        # Ensure proper flow descriptors are set
        if not subscription.trafficFilters or not subscription.trafficFilters[0].flowDescriptions:
            # Build default flow descriptor
            device_ip = traffic_influence_info.retrieve_ue_ipv4()
            server_ip = traffic_influence_info.appInstanceId
            flow_descriptor = f"permit out ip from {device_ip}/32 to {server_ip}/32"
            subscription.add_flow_descriptor(flow_descriptor=flow_descriptor)
        
        # Add edge zone information
        if traffic_influence_info.edgeCloudZoneId:
            subscription.add_traffic_route(dnai=traffic_influence_info.edgeCloudZoneId)

    def core_specific_traffic_influence_validation(
        self, traffic_influence_info: schemas.CreateTrafficInfluence
    ) -> None:
        """
        Validate CoreSim-specific traffic influence requirements.
        CoreSim requires app and device information for traffic steering.
        """
        if traffic_influence_info.appId is None:
            raise ValidationError("Application ID is required for traffic influence")
        
        if traffic_influence_info.appInstanceId is None:
            raise ValidationError("Application instance ID (server IP) is required")
        
        device_ip = traffic_influence_info.retrieve_ue_ipv4()
        if device_ip is None:
            raise ValidationError("Device IP address is required for traffic influence")
        
        log.info(
            f"Traffic influence validation passed: "
            f"app={traffic_influence_info.appId}, "
            f"device={device_ip}, "
            f"server={traffic_influence_info.appInstanceId}"
        )

    # Override QoD subscription builder for CoreSim-specific requirements
    def _build_qod_subscription(self, session_info: Dict) -> schemas.AsSessionWithQoSSubscription:
        """
        Override parent's QoD subscription builder to match NEF/CoreSim requirements.
        
        CoreSim-specific constraints:
        1. UE IPs must be from 12.1.0.0/16 subnet (CoreSim IPAM allocation)
        2. DNN (Data Network Name) is required by NEF
        3. FlowInfo with flowId and flowDescriptions array is mandatory
        4. UsageThreshold.duration is optional and removed by NEF
        
        This method adapts CAMARA session_info format to 3GPP TS 29.122 format.
        """
        valid_session_info = schemas.CreateSession.model_validate(session_info)
        device_ipv4 = None
        if valid_session_info.device.ipv4Address:
            # Handle different DeviceIpv4Addr formats (DeviceIpv4Addr1, DeviceIpv4Addr2, DeviceIpv4Addr3)
            ipv4_addr = valid_session_info.device.ipv4Address
            if hasattr(ipv4_addr, 'root') and hasattr(ipv4_addr.root, 'publicAddress'):
                public_addr = ipv4_addr.root.publicAddress
                device_ipv4 = str(public_addr.root if hasattr(public_addr, 'root') else public_addr)
            else:
                device_ipv4 = str(ipv4_addr)
        
        # CoreSim IPAM constraint: IPs must be from 12.1.0.0/16
        if device_ipv4:
            ip_parts = device_ipv4.split('.')
            if ip_parts[0:2] != ['12', '1']:
                log.warning(
                    f"CoreSim adapter: Device IP {device_ipv4} is outside CoreSim IPAM subnet (12.1.0.0/16). "
                    f"Using 12.1.0.1 as fallback."
                )
                device_ipv4 = "12.1.0.1"
        else:
            # Default to first UE IP in CoreSim allocation range
            device_ipv4 = "12.1.0.1"
        
        self.core_specific_qod_validation(valid_session_info)
        
        # Build flow descriptors - NEF requires flowInfo with flowId and flowDescriptions array
        flow_descriptors = ["permit ip 0.0.0.0 0.0.0.0"]  # Default: allow all traffic
        if valid_session_info.applicationServer:
            server_ip = str(valid_session_info.applicationServer.ipv4Address)
            flow_descriptors = [f"permit ip {device_ipv4}/32 to {server_ip}/32"]
        
        flow_info = schemas.FlowInfo(
            flowId=1,
            flowDescriptions=flow_descriptors
        )
        
        # Build subscription with required NEF fields
        # Note: usageThreshold.duration is not included as NEF ignores it
        subscription = schemas.AsSessionWithQoSSubscription(
            notificationDestination=str(valid_session_info.sink),
            qosReference=valid_session_info.qosProfile.root,
            ueIpv4Addr=device_ipv4,
            ueIpv6Addr=valid_session_info.device.ipv6Address,
            flowInfo=[flow_info],
            dnn="internet",  # NEF requires DNN - default to 'internet'
        )
        self.add_core_specific_qod_parameters(valid_session_info, subscription)
        return subscription

    # Override CAMARA API methods to use separate NEF service URLs
    def create_qod_session(self, session_info: Dict) -> Dict:
        """
        Creates a QoS session using the NEF QoD service (exposed on separate port).
        """
        subscription = self._build_qod_subscription(session_info)
        log.debug(f"QoD subscription JSON: {subscription.model_dump_json(exclude_none=True, by_alias=True)}")
        
        response = common.as_session_with_qos_post(self.qod_base_url, self.scs_as_id, subscription)
        log.debug(f"NEF QoD response type: {type(response)}, content: {response}")
        
        # Handle response - extract 'self' field which contains the subscription ID
        if isinstance(response, dict):
            subscription_id = response.get('self') or response.get('subscription_id')
            if not subscription_id:
                log.error(f"No subscription ID in NEF response: {response}")
                raise NetworkPlatformError("Failed to extract subscription ID from NEF response")
            log.debug(f"Extracted subscription ID: {subscription_id}")
        else:
            log.error(f"Unexpected response type from NEF: {type(response)}, content: {response}")
            raise NetworkPlatformError(f"Invalid response type from NEF QoD service")

        try:
            session_id_obj = schemas.SessionId(uuid.UUID(str(subscription_id)))
        except (ValueError, TypeError) as e:
            log.error(f"Failed to parse subscription ID as UUID: {subscription_id}, error: {e}")
            raise NetworkPlatformError(f"Invalid subscription ID format from NEF: {subscription_id}")

        # Re-validate the original session_info to extract required fields
        try:
            valid_session_info = schemas.CreateSession.model_validate(session_info)
        except Exception as e:
            log.error(f"Failed to validate session_info: {e}")
            raise
        
        try:
            session_info_response = schemas.SessionInfo(
                sessionId=session_id_obj,
                qosStatus=schemas.QosStatus.REQUESTED,
                device=valid_session_info.device,
                applicationServer=valid_session_info.applicationServer,
                qosProfile=valid_session_info.qosProfile,
                duration=valid_session_info.duration,
            )
            log.debug(f"SessionInfo created successfully: {session_info_response}")
        except Exception as e:
            log.error(f"Failed to create SessionInfo: {e}", exc_info=True)
            raise
        
        try:
            result = session_info_response.model_dump(mode="json", by_alias=True)
            log.debug(f"SessionInfo serialization successful")
            return result
        except Exception as e:
            log.error(f"Failed to serialize SessionInfo: {e}", exc_info=True)
            raise

    def get_qod_session(self, session_id: str) -> Dict:
        """
        Retrieves details of a QoS session from the NEF QoD service.
        """
        response = common.as_session_with_qos_get(self.qod_base_url, self.scs_as_id, session_id)
        return response

    def delete_qod_session(self, session_id: str) -> Dict:
        """
        Deletes a QoS session from the NEF QoD service.
        """
        response = common.as_session_with_qos_delete(self.qod_base_url, self.scs_as_id, session_id)
        return response

    def create_monitoring_event_subscription(
        self, retrieve_location_request: schemas.RetrievalLocationRequest
    ) -> schemas.Location:
        """
        Creates a Monitoring Event subscription using the NEF Location service.
        """
        subscription = self._build_monitoring_event_subscription(retrieve_location_request)
        response = common.monitoring_event_post(self.location_base_url, self.scs_as_id, subscription)

        monitoring_event_report = schemas.MonitoringEventReport(**response)
        if monitoring_event_report.locationInfo is None:
            log.error("Failed to retrieve location information from monitoring event report")
            raise NetworkPlatformError("Location information not found in monitoring event report")
        log.debug(f"Location info: {monitoring_event_report.locationInfo}")
        log.debug(f"Location info dict: {monitoring_event_report.locationInfo.model_dump() if hasattr(monitoring_event_report.locationInfo, 'model_dump') else vars(monitoring_event_report.locationInfo)}")
        geo_area = monitoring_event_report.locationInfo.geographicArea
        log.debug(f"Geographic area: {geo_area}")
        log.debug(f"Geographic area type: {type(geo_area)}")
        if hasattr(geo_area, 'polygon'):
            log.debug(f"Polygon attribute: {geo_area.polygon}")
        
        # CoreSim only provides cell-based location (NCGI), not GPS coordinates
        # If geographicArea is missing, create a mock polygon based on cell ID
        if geo_area is None or (hasattr(geo_area, 'polygon') and geo_area.polygon is None):
            log.warning("Geographic area with coordinates not available from CoreSim. Using mock coordinates based on cell ID.")
            # Mock coordinates for cell 000000001 (center of Paris as example)
            mock_lat, mock_lon = 48.8566, 2.3522
            camara_point_list = [
                schemas.Point(latitude=mock_lat + 0.001, longitude=mock_lon + 0.001),
                schemas.Point(latitude=mock_lat + 0.001, longitude=mock_lon - 0.001),
                schemas.Point(latitude=mock_lat - 0.001, longitude=mock_lon - 0.001),
                schemas.Point(latitude=mock_lat - 0.001, longitude=mock_lon + 0.001),
            ]
            camara_polygon = schemas.Polygon(
                areaType=schemas.AreaType.polygon,
                boundary=schemas.PointList(camara_point_list),
            )
        else:
            # Use actual coordinates from geographicArea
            camara_point_list: list[schemas.Point] = []
            for point in geo_area.polygon.point_list.geographical_coords:
                camara_point_list.append(schemas.Point(latitude=point.lat, longitude=point.lon))
            camara_polygon = schemas.Polygon(
                areaType=schemas.AreaType.polygon,
                boundary=schemas.PointList(camara_point_list),
            )
        
        report_event_time = monitoring_event_report.eventTime
        age_of_location_info = None
        if monitoring_event_report.locationInfo.ageOfLocationInfo is not None:
            age_of_location_info = monitoring_event_report.locationInfo.ageOfLocationInfo.duration
        last_location_time = self._compute_camara_last_location_time(
            report_event_time, age_of_location_info
        )
        log.debug(f"Last Location time is {last_location_time}")
        
        camara_location = schemas.Location(area=camara_polygon, lastLocationTime=last_location_time)

        return camara_location

    def _build_ti_subscription(self, traffic_influence_info: Dict) -> schemas.TrafficInfluSub:
        """
        Override to build Traffic Influence subscription with CoreSim/NEF-specific requirements.
        
        NEF requires TS 29.122 format with:
        - afAppId: Application ID (required by 3GPP spec)
        - ipv4Addr: UE IP (must be from 12.1.0.0/16 CoreSim IPAM range)
        - dnn: Data Network Name (required)
        - trafficFilters: Array with flowId and flowDescriptions
        - trafficRoutes: Array with dnai for edge zone routing
        - notificationDestination: Callback URL for events
        """
        traffic_influence_data = schemas.CreateTrafficInfluence.model_validate(
            traffic_influence_info
        )
        self.core_specific_traffic_influence_validation(traffic_influence_data)

        device_ip = traffic_influence_data.retrieve_ue_ipv4()
        
        # CoreSim IPAM constraint: IPs must be from 12.1.0.0/16
        if device_ip:
            ip_parts = str(device_ip).split('.')
            if ip_parts[0:2] != ['12', '1']:
                log.warning(
                    f"CoreSim adapter: Device IP {device_ip} is outside CoreSim IPAM subnet (12.1.0.0/16). "
                    f"Using 12.1.0.1 as fallback."
                )
                device_ip = "12.1.0.1"
        else:
            device_ip = "12.1.0.1"
        
        app_id = traffic_influence_data.appId
        server_ip = traffic_influence_data.appInstanceId
        sink_url = traffic_influence_data.notificationUri
        edge_zone = traffic_influence_data.edgeCloudZoneId or "DNAI1"

        # Build flow descriptor in OAI format for NEF
        flow_descriptor = f"permit ip {device_ip}/32 to {server_ip}/32"

        # Create NEF TS 29.122 format subscription
        subscription = schemas.TrafficInfluSub(
            afAppId=app_id,
            ipv4Addr=str(device_ip),
            dnn="internet",  # NEF requires DNN field
            notificationDestination=sink_url,
        )
        subscription.add_flow_descriptor(flow_descriptor=flow_descriptor)
        subscription.add_traffic_route(dnai=edge_zone)

        self.add_core_specific_ti_parameters(traffic_influence_data, subscription)
        return subscription

    def create_traffic_influence_resource(self, traffic_influence_info: Dict) -> Dict:
        """
        Creates a traffic influence resource using the NEF Traffic Influence service.
        """
        subscription = self._build_ti_subscription(traffic_influence_info)
        response = common.traffic_influence_post(self.ti_base_url, self.scs_as_id, subscription)
        
        # Extract subscription ID from 'self' field (similar to QoD)
        if isinstance(response, dict):
            subscription_id = response.get('self')
            if subscription_id:
                response['trafficInfluenceID'] = subscription_id
                log.debug(f"Extracted Traffic Influence subscription ID: {subscription_id}")
        
        return response

    def put_traffic_influence_resource(self, session_id: str, traffic_influence_info: Dict) -> Dict:
        """
        Updates a traffic influence resource in the NEF Traffic Influence service.
        """
        subscription = self._build_ti_subscription(traffic_influence_info)
        response = common.traffic_influence_put(
            self.ti_base_url, self.scs_as_id, session_id, subscription
        )
        
        # PUT operations typically don't return content, so return the input data with ID
        traffic_influence_info["trafficInfluenceID"] = session_id
        return traffic_influence_info

    def delete_traffic_influence_resource(self, session_id: str) -> Dict:
        """
        Deletes a traffic influence resource from the NEF Traffic Influence service.
        """
        response = common.traffic_influence_delete(self.ti_base_url, self.scs_as_id, session_id)
        return response

    def get_individual_traffic_influence_resource(self, session_id: str) -> Dict:
        """
        Retrieves a specific traffic influence resource from the NEF Traffic Influence service.
        Returns the resource as a dictionary.
        """
        response = common.traffic_influence_get(self.ti_base_url, self.scs_as_id, session_id)
        
        # If response is a list (which shouldn't happen for individual get), get first element
        if isinstance(response, list) and len(response) > 0:
            log.warning(f"NEF returned list for individual resource get. Using first element.")
            return response[0]
        
        return response

    def get_all_traffic_influence_resource(self) -> list[Dict]:
        """
        Retrieves all traffic influence resources from the NEF Traffic Influence service.
        """
        response = common.traffic_influence_get_all(self.ti_base_url, self.scs_as_id)
        return response

    # Helper method to compute last location time (from base client)
    def _compute_camara_last_location_time(self, event_time, age_of_location_info_min: int = None):
        """Delegate to base client implementation"""
        from datetime import datetime, timedelta, timezone
        if age_of_location_info_min is not None:
            last_location_time = event_time - timedelta(minutes=age_of_location_info_min)
            return last_location_time.replace(tzinfo=timezone.utc)
        else:
            return event_time.replace(tzinfo=timezone.utc)
