# -*- coding: utf-8 -*-
##
#
# This file is part of the Open SDK, based on sunrise6g_opensdk.network.core.adapters.open5gs.client
#
# Contributors:
#   - Miguel Catalan Cid (miguel.catalan@i2cat.net)
##
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

from pydantic import ValidationError

from sunrise6g_opensdk import logger
from sunrise6g_opensdk.oran.core.base_oran_client import BaseOranClient

from ...core import common as oran_common
from ...core import schemas
from ...core.common import OranHttpError, requires_capability
from . import mappings as mappings_module
from .mappings import flow_id_mapping, policy_mapping, qos_prio_to_oran_prio

log = logger.get_logger(__name__)


class OranManager(BaseOranClient):
    """
    This client implements the BaseOranClient and translates the
    CAMARA APIs into specific HTTP requests understandable by the i2CAT ORAN NEF API.
    """

    capabilities = {"oran-qod", "oran-performance"}

    def __init__(self, base_url: str, scs_as_id):
        """
        Initializes the OranNEFClient Client.
        """
        try:
            # Set required attributes without invoking BaseOranClient.__init__
            self.base_url = base_url
            self.scs_as_id = scs_as_id
            # Read mappings on-demand; no background thread
            log.info(
                f"Initialized OranNEFClient with base_url: {self.base_url} "
                f"and scs_as_id: {self.scs_as_id}"
            )
        except Exception as e:
            log.error(f"Failed to initialize OranNEFClient: {e}")
            raise e

    def oran_specific_qod_validation(self, session_info: schemas.CreateSession):
        if session_info.qosProfile.root not in qos_prio_to_oran_prio.keys():
            raise ValidationError(
                f"OranNEFClient only supports these qos-profiles: {', '.join(qos_prio_to_oran_prio.keys())}"
            )

    def _load_ip_mapping_from_file(self) -> Dict[str, Dict[str, Any]]:
        base_dir = Path(__file__).parent
        cfg_path = base_dir / "ip_to_plmn_gnb_mapping.json"
        if not cfg_path.exists():
            # No file present; nothing to load
            return {}

        try:
            with cfg_path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as exc:
            log.warning(f"Failed to parse mapping file {cfg_path.name}: {exc}")
            return {}

        if not isinstance(raw, dict):
            log.warning(f"Mapping file root must be an object/dict: {cfg_path.name}")
            return {}

        parsed: Dict[str, Dict[str, Any]] = {}
        for ip, entry in raw.items():
            if not isinstance(ip, str) or not isinstance(entry, dict):
                continue
            try:
                mcc = entry.get("mcc")
                mnc = entry.get("mnc")
                gnb_length = entry.get("gnb_length")
                gnb_id = entry.get("gnb_id")
                ran_ue_id = entry.get("ran_ue_id")

                if (
                    mcc is None
                    or mnc is None
                    or gnb_length is None
                    or gnb_id is None
                    or ran_ue_id is None
                ):
                    raise ValueError("missing required keys")

                # Coerce types
                mcc_str = str(mcc)
                mnc_str = str(mnc)
                gnb_length_int = int(gnb_length)
                gnb_id_int = int(gnb_id)
                ran_ue_id_str = str(ran_ue_id)

                parsed[ip] = {
                    "mcc": mcc_str,
                    "mnc": mnc_str,
                    "gnb_length": gnb_length_int,
                    "gnb_id": gnb_id_int,
                    "ran_ue_id": ran_ue_id_str,
                }
            except Exception:
                # Skip invalid entries
                continue
        return parsed

    def _get_ip_mapping(self) -> Dict[str, Dict[str, Any]]:
        """Return latest IP->PLMN/gNB mapping, reading file each time if present.

        Falls back to in-module defaults when the external file is missing or invalid.
        """
        new_map = self._load_ip_mapping_from_file()
        if new_map:
            return new_map
        return mappings_module.ip_to_plmn_gnb_mapping

    @requires_capability("oran-qod")
    def create_qod_session(self, session_info: Dict, return_on_error: bool = False) -> Dict:
        """Translate CAMARA QoD session into ORAN policy and submit it."""
        candidates = self._extract_device_ip_candidates(session_info)
        scope = self._resolve_scope_from_candidates(candidates)
        qos_profile, qos_prio, flow_id = self._normalize_qos_profile(session_info)
        scope_with_flow = {**scope, "flow_id": flow_id}
        expiry = self._parse_expiry(session_info)
        notification_uri = self._extract_notification_uri(session_info)
        policy = self._build_policy(scope_with_flow, qos_prio, expiry, notification_uri)

        resp = self._post_policy(policy, return_on_error)
        # If return_on_error and there was an error, _post_policy returns a camara-like UNAVAILABLE
        if resp.get("qosStatus") == "UNAVAILABLE" and "sessionId" not in resp:
            return resp

        policy_id = (
            (resp or {}).get("policy_id") or (resp or {}).get("policyId") or (resp or {}).get("id")
        )
        if not policy_id:
            raise ValueError("ORAN policy creation did not return an ID")

        return self._build_camara_create_response(
            session_info=session_info,
            policy_id=policy_id,
            qos_profile=qos_profile,
            notification_uri=notification_uri,
            expiry=expiry,
        )

    def _extract_device_ip_candidates(self, session_info: Dict) -> list[str]:
        device = session_info.get("device") or {}
        ipv4 = device.get("ipv4Address") if isinstance(device, dict) else None
        candidates: list[str] = []
        if isinstance(ipv4, dict):
            pub_ip = ipv4.get("publicAddress")
            prv_ip = ipv4.get("privateAddress")
            if isinstance(pub_ip, str) and pub_ip:
                candidates.append(pub_ip)
            if isinstance(prv_ip, str) and prv_ip and prv_ip not in candidates:
                candidates.append(prv_ip)
        elif isinstance(ipv4, str) and ipv4:
            candidates.append(ipv4)
        if not candidates:
            raise ValueError("device.ipv4Address (public/private) must be provided")
        return candidates

    def _resolve_scope_from_candidates(self, candidates: list[str]) -> Dict[str, Any]:
        ip_map = self._get_ip_mapping()
        for ip in candidates:
            scope = ip_map.get(ip)
            if scope:
                return scope
        raise ValueError(f"No PLMN/gNB/UE mapping found for device IPs {', '.join(candidates)}")

    def _normalize_qos_profile(self, session_info: Dict) -> tuple[str, int, int]:
        qos_profile = session_info.get("qosProfile")
        if isinstance(qos_profile, dict):
            qos_profile = qos_profile.get("root") or qos_profile.get("value")
        if qos_profile not in qos_prio_to_oran_prio:
            raise ValidationError(
                f"Unsupported qosProfile '{qos_profile}'. Allowed: {', '.join(qos_prio_to_oran_prio.keys())}"
            )
        qos_prio = qos_prio_to_oran_prio[qos_profile]
        try:
            flow_id = flow_id_mapping[qos_profile]
        except KeyError:
            raise ValidationError(f"No flow_id mapping found for qosProfile '{qos_profile}'")
        return qos_profile, qos_prio, flow_id

    def _parse_expiry(self, session_info: Dict) -> int | None:
        expiry = session_info.get("duration")
        try:
            return int(expiry) if expiry is not None else None
        except Exception:
            return None

    def _extract_notification_uri(self, session_info: Dict) -> str | None:
        return session_info.get("notificationDestination") or None

    def _build_policy(
        self,
        scope_with_flow: Dict[str, Any],
        qos_prio: int,
        expiry: int | None,
        notification_uri: str | None,
    ) -> schemas.OranPolicy:
        return schemas.OranPolicy(
            policyType=policy_mapping["oran-qod"],
            policyScope=scope_with_flow,
            policyStatement={"qos_prio": qos_prio},
            expiry=expiry,
            notificationUri=notification_uri,
        )

    def _post_policy(self, policy: schemas.OranPolicy, return_on_error: bool) -> Dict[str, Any]:
        try:
            return oran_common.oran_policy_post(self.base_url, self.scs_as_id, policy)
        except OranHttpError as e:
            if return_on_error:
                # Map HTTP error to CAMARA StatusInfo when returning UNAVAILABLE
                status_info = None
                if e.status_code is not None:
                    if e.status_code >= 500 or e.status_code in (408, 504):
                        status_info = "NETWORK_TERMINATED"
                    elif e.status_code == 410:
                        status_info = "DELETE_REQUESTED"

                # Align error payload with CAMARA ErrorInfo {status, code, message}
                body = e.body if isinstance(e.body, dict) else None
                if isinstance(body, dict) and {
                    "status",
                    "code",
                    "message",
                }.issubset(body.keys()):
                    error_info = {
                        "status": body.get("status"),
                        "code": body.get("code"),
                        "message": body.get("message"),
                    }
                else:
                    # Best-effort default mapping when backend doesn't provide CAMARA ErrorInfo
                    code_map = {
                        400: "INVALID_ARGUMENT",
                        401: "UNAUTHENTICATED",
                        403: "PERMISSION_DENIED",
                        404: "NOT_FOUND",
                        409: "CONFLICT",
                        410: "GONE",
                        413: "REQUEST_TOO_LARGE",
                        415: "UNSUPPORTED_MEDIA_TYPE",
                        422: "UNPROCESSABLE_ENTITY",
                        429: "TOO_MANY_REQUESTS",
                    }
                    error_info = {
                        "status": e.status_code,
                        "code": code_map.get(e.status_code or 0, "INTERNAL_ERROR"),
                        "message": (
                            (body or {}).get("message") if isinstance(body, dict) else str(e)
                        ),
                    }

                return {
                    "qosStatus": "UNAVAILABLE",
                    "statusInfo": status_info,
                    "error": error_info,
                }
            raise

    def _build_camara_create_response(
        self,
        *,
        session_info: Dict,
        policy_id: Any,
        qos_profile: str,
        notification_uri: str | None,
        expiry: int | None,
    ) -> Dict[str, Any]:
        return {
            "sessionId": str(policy_id),
            "qosStatus": "REQUESTED",
            "duration": expiry if isinstance(expiry, int) else session_info.get("duration"),
            "device": session_info.get("device"),
            "applicationServer": session_info.get("applicationServer"),
            "devicePorts": session_info.get("devicePorts"),
            "applicationServerPorts": session_info.get("applicationServerPorts"),
            "qosProfile": qos_profile,
            "sink": notification_uri,
        }

    @requires_capability("oran-qod")
    def get_qod_session(
        self,
        session_id: str,
        original_session: Dict | None = None,
        fallback_unavailable: bool = False,
    ) -> Dict:
        """Return CAMARA SessionInfo-style data for a QoD session.

        Fetches the underlying ORAN policy to determine liveness and ID but
        intentionally shapes the response to CAMARA fields only, not leaking
        ORAN-specific attributes (policyScope, policyStatement, etc.).
        """
        try:
            resp: Dict[str, Any] = oran_common.oran_policy_get(
                self.base_url, self.scs_as_id, session_id
            )
        except OranHttpError:
            if fallback_unavailable:
                # Return a minimal CAMARA-like UNAVAILABLE response instead of raising
                return {
                    "sessionId": str(session_id),
                    "qosStatus": "UNAVAILABLE",
                }
            raise

        # Determine policy/session identifier from ORAN response, fallback to provided session_id
        policy_id = (
            (resp or {}).get("policy_id")
            or (resp or {}).get("policyId")
            or (resp or {}).get("id")
            or session_id
        )

        # Build a fresh CAMARA-shaped response without ORAN internals
        camara_resp: Dict[str, Any] = {
            "sessionId": str(policy_id),
            "qosStatus": "AVAILABLE",
        }

        # Always include startedAt; include expiresAt only if a duration is known
        now = datetime.now(timezone.utc)
        camara_resp["startedAt"] = now.isoformat().replace("+00:00", "Z")

        expiry_val = (resp or {}).get("expiry")
        duration_sec: int | None = None
        if isinstance(original_session, dict) and isinstance(original_session.get("duration"), int):
            duration_sec = int(original_session.get("duration"))
        elif isinstance(expiry_val, int):
            duration_sec = int(expiry_val)
        if isinstance(duration_sec, int):
            camara_resp["expiresAt"] = (
                (now + timedelta(seconds=duration_sec)).isoformat().replace("+00:00", "Z")
            )

        # sink: map ORAN notification URI to CAMARA 'sink'
        notif = (resp or {}).get("notificationUri")
        if isinstance(notif, str) and notif:
            camara_resp["sink"] = notif

        # Enrich with original requested session fields when available (CAMARA keys only)
        if isinstance(original_session, dict):
            for key in (
                "device",
                "applicationServer",
                "devicePorts",
                "applicationServerPorts",
                "qosProfile",
            ):
                val = original_session.get(key)
                if camara_resp.get(key) is None and val is not None:
                    camara_resp[key] = val
            # Map legacy key
            if camara_resp.get("sink") is None and original_session.get("notificationDestination"):
                camara_resp["sink"] = original_session.get("notificationDestination")

        return camara_resp

    @requires_capability("oran-qod")
    def delete_qod_session(self, session_id: str) -> None:
        """Delete an ORAN policy by ID (maps to QoD session delete)."""
        oran_common.oran_policy_delete(self.base_url, self.scs_as_id, session_id)

    def notification_to_camara_session(
        self, notification: Dict[str, Any], original_session: Dict | None = None
    ) -> Dict[str, Any]:
        """Translate an ORAN notification payload into a CAMARA SessionInfo-like dict.

        Example notification payload:
          {
            "info_type": "policy_ue_prb_priority",
            "subscription_id": "<uuid>",
            "data": {
              "policy_status": "ENFORCED",
              ...
            }
          }

        Returns a response shaped like our GET mapping and enriches fields
        using the provided CAMARA `original_session` when available.
        """
        session_id = (
            notification.get("subscription_id")
            or notification.get("sessionId")
            or notification.get("id")
        )
        data = notification.get("data") or {}
        policy_status = str(data.get("policy_status") or "").upper()

        # Map policy status to CAMARA qosStatus
        qos_status = "AVAILABLE" if policy_status == "ENFORCED" else "UNAVAILABLE"

        camara_resp: Dict[str, Any] = {
            "sessionId": str(session_id) if session_id is not None else None,
            "qosStatus": qos_status,
        }

        # Always include startedAt; add expiresAt only if original_session carries a duration
        now = datetime.now(timezone.utc)
        camara_resp["startedAt"] = now.isoformat().replace("+00:00", "Z")
        if isinstance(original_session, dict) and isinstance(original_session.get("duration"), int):
            duration_sec = int(original_session.get("duration"))
            camara_resp["expiresAt"] = (
                (now + timedelta(seconds=duration_sec)).isoformat().replace("+00:00", "Z")
            )

        # Enrich with original CAMARA fields if provided
        if isinstance(original_session, dict):
            for key in (
                "device",
                "applicationServer",
                "devicePorts",
                "applicationServerPorts",
                "qosProfile",
            ):
                val = original_session.get(key)
                if camara_resp.get(key) is None and val is not None:
                    camara_resp[key] = val
            sink = original_session.get("sink") or original_session.get("notificationDestination")
            if sink and camara_resp.get("sink") is None:
                camara_resp["sink"] = sink

        return camara_resp
