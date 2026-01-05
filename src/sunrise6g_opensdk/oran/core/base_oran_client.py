#!/usr/bin/env python3
# -*- coding: utf-8 -*-
##
# This file is part of the Open SDK, based on sunrise6g_opensdk.network.base_network_client
#
# Contributors:
#
#   - Miguel Catalán Cid (miguel.catalan@i2cat.net)
##
import threading
import uuid
from typing import Dict

from sunrise6g_opensdk import logger

# from sunrise6g_opensdk.oran.adapters.errors import OranPlatformError
from sunrise6g_opensdk.oran.core import common, schemas
from sunrise6g_opensdk.oran.core.common import requires_capability

log = logger.get_logger(__name__)


class BaseOranClient:
    """
    Class for Oran Resource Management.

    This class provides shared logic and extension points for different
    ORAN frameworks (e.g., i2CAT based on OSC, Juniper RIC) interacting with
    O-RAN NEF-like platforms or rapps using CAMARA APIs.
    """

    base_url: str
    scs_as_id: str
    _refresh_thread: threading.Thread | None = None
    _refresh_stop_event: threading.Event | None = None

    @requires_capability("oran-qod")
    def add_oran_specific_qod_parameters(
        self,
        session_info: schemas.CreateSession,
        subscription: schemas.AsSessionWithQoSSubscription,
    ):
        """
        Placeholder for adding core-specific parameters to the subscription.
        This method should be overridden by subclasses to implement specific logic.
        """
        pass

    @requires_capability("oran-qod")
    def core_specific_qod_validation(self, session_info: schemas.CreateSession) -> None:
        """
        Validates core-specific parameters for the session creation.

        args:
            session_info: The session information to validate.

        raises:
            ValidationError: If the session information does not meet core-specific requirements.
        """
        # Placeholder for core-specific validation logic
        # This method should be overridden by subclasses if needed
        pass

    # Periodic dynamic mappings refresh
    def refresh_dynamic_mappings(self) -> None:
        """
        Hook for subclasses to refresh dynamic mappings/config from external sources.
        Default implementation is a no-op.
        """
        return

    def _periodic_refresh_loop(self, interval_seconds: int, run_immediately: bool) -> None:
        if not run_immediately:
            # Initial delay before first refresh
            if self._refresh_stop_event and self._refresh_stop_event.wait(interval_seconds):
                return
        while self._refresh_stop_event and not self._refresh_stop_event.is_set():
            try:
                self.refresh_dynamic_mappings()
            except Exception as exc:
                log.warning(f"Periodic refresh failed: {exc}")
            # Wait for next interval or stop event
            if self._refresh_stop_event.wait(interval_seconds):
                break

    def start_periodic_refresh(
        self, interval_seconds: int = 60, run_immediately: bool = True
    ) -> None:
        """
        Starts a background thread that periodically calls `refresh_dynamic_mappings`.
        If already running, it will be restarted with the new parameters.
        """
        # Stop any existing loop
        self.stop_periodic_refresh()
        self._refresh_stop_event = threading.Event()
        self._refresh_thread = threading.Thread(
            target=self._periodic_refresh_loop,
            args=(interval_seconds, run_immediately),
            daemon=True,
        )
        self._refresh_thread.start()
        log.info(
            f"Started periodic refresh every {interval_seconds}s (immediate={run_immediately})"
        )

    def stop_periodic_refresh(self) -> None:
        """
        Stops the background periodic refresh thread if running.
        """
        if self._refresh_stop_event is not None:
            self._refresh_stop_event.set()
        if self._refresh_thread is not None and self._refresh_thread.is_alive():
            self._refresh_thread.join(timeout=2)
        self._refresh_thread = None
        self._refresh_stop_event = None

    @requires_capability("qod")
    def create_qod_session(self, session_info: Dict) -> Dict:
        """
        Creates a QoS session based on CAMARA QoD API input.

        args:
            session_info: Dictionary containing session details conforming to
                          the CAMARA QoD session creation parameters.

        returns:
            dictionary containing the created session details, including its ID.
        """
        subscription = self._build_qod_subscription(session_info)
        response = common.as_session_with_qos_post(self.base_url, self.scs_as_id, subscription)
        subscription_info: schemas.AsSessionWithQoSSubscription = (
            schemas.AsSessionWithQoSSubscription(**response)
        )

        session_info = schemas.SessionInfo(
            sessionId=schemas.SessionId(uuid.UUID(subscription_info.subscription_id)),
            qosStatus=schemas.QosStatus.REQUESTED,
            **session_info,
        )
        return session_info.model_dump(mode="json", by_alias=True)

    @requires_capability("qod")
    def get_qod_session(self, session_id: str) -> Dict:
        """
        Retrieves details of a specific Quality on Demand (QoS) session.

        args:
            session_id: The unique identifier of the QoS session.

        returns:
            Dictionary containing the details of the requested QoS session.
        """
        response = common.as_session_with_qos_get(
            self.base_url, self.scs_as_id, session_id=session_id
        )
        subscription_info = schemas.AsSessionWithQoSSubscription(**response)
        flowDesc = subscription_info.flowInfo[0].flowDescriptions[0]
        serverIp = flowDesc.split("to ")[1].split("/")[0]
        session_info = schemas.SessionInfo(
            sessionId=schemas.SessionId(uuid.UUID(subscription_info.subscription_id)),
            duration=subscription_info.usageThreshold.duration.root,
            sink=subscription_info.notificationDestination.root,
            qosProfile=subscription_info.qosReference,
            device=schemas.Device(
                ipv4Address=schemas.DeviceIpv4Addr1(
                    publicAddress=subscription_info.ueIpv4Addr,
                    privateAddress=subscription_info.ueIpv4Addr,
                ),
            ),
            applicationServer=schemas.ApplicationServer(
                ipv4Address=schemas.ApplicationServerIpv4Address(serverIp)
            ),
            qosStatus=schemas.QosStatus.AVAILABLE,
        )
        return session_info.model_dump(mode="json", by_alias=True)

    @requires_capability("qod")
    def delete_qod_session(self, session_id: str) -> None:
        """
        Deletes a specific Quality on Demand (QoS) session.

        args:
            session_id: The unique identifier of the QoS session to delete.

        returns:
            None
        """
        common.as_session_with_qos_delete(self.base_url, self.scs_as_id, session_id=session_id)
        log.info(f"QoD session deleted successfully [id={session_id}]")

    # Placeholder for additional CAMARA APIs
