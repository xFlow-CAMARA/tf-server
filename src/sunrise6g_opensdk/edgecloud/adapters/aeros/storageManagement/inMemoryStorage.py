"""
Class: InMemoryAppStorage
Process-wide singleton, thread-safe with a single RLock.
Keeps CAMARA and GSMA stores separate to avoid schema confusion.
"""

from abc import ABCMeta
from threading import RLock
from typing import Dict, List, Optional, Union

from sunrise6g_opensdk.edgecloud.adapters.aeros import config
from sunrise6g_opensdk.edgecloud.adapters.aeros.storageManagement.appStorageManager import (
    AppStorageManager,
)
from sunrise6g_opensdk.edgecloud.core.camara_schemas import AppInstanceInfo
from sunrise6g_opensdk.edgecloud.core.gsma_schemas import (
    AppInstance,
    AppInstanceStatus,
    ApplicationModel,
    Artefact,
)
from sunrise6g_opensdk.logger import setup_logger


class SingletonMeta(ABCMeta):
    """Thread-safe Singleton metaclass (process-wide)."""

    _instances: Dict[type, object] = {}
    _lock = RLock()

    def __call__(cls, *args, **kwargs):
        # Double-checked locking
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class InMemoryAppStorage(AppStorageManager, metaclass=SingletonMeta):
    """
    In-memory implementation of the AppStorageManager interface.
    CAMARA and GSMA data are stored in separate namespaces.
    """

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        # Always have a logger; gate noisy messages by DEBUG
        self.logger = setup_logger()
        if config.DEBUG:
            self.logger.info("Using InMemoryStorage (singleton)")

        self._lock = RLock()

        # aerOS Domain → Zone mapping
        self._zones: Dict[str, Dict] = {}  # {aeros_domain_id: camara_zone_dict}

        # CAMARA stores
        self._apps: Dict[str, Dict] = {}  # app_id -> manifest (CAMARA dict)
        self._deployed: Dict[str, List[AppInstanceInfo]] = {}  # app_id -> [AppInstanceInfo]
        self._stopped: Dict[str, List[str]] = {}  # app_id -> [stopped instance ids]

        # GSMA stores
        self._apps_gsma: Dict[str, ApplicationModel] = {}  # app_id -> ApplicationModel
        self._deployed_gsma: Dict[str, List[AppInstance]] = {}  # app_id -> [AppInstance]
        self._stopped_gsma: Dict[str, List[str]] = {}  # app_id -> [stopped instance ids]

        self._artefacts_gsma: Dict[str, Artefact] = {}  # artefact_id -> Artefact

        self._initialized = True

    # ------------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------------
    def reset(self) -> None:
        """Helper for tests to clear global state."""
        with self._lock:
            # CAMARA
            self._apps.clear()
            self._deployed.clear()
            self._stopped.clear()
            # GSMA
            self._apps_gsma.clear()
            self._deployed_gsma.clear()
            self._stopped_gsma.clear()

    # ------------------------------------------------------------------------
    # aerOS Domain → Zone mapping
    # ------------------------------------------------------------------------

    def store_zones(self, zones: Dict[str, Dict]) -> None:
        """
        Directly store a mapping of aerOS domain_id -> zone_info dict.
        Example:
            {
                "urn:ngsi-ld:Domain:Athens": {
                    "edgeCloudZoneId": "550e8400-e29b-41d4-a716-446655440000",
                    "edgeCloudZoneName": "Athens",
                    "edgeCloudProvider": "aeros_dev",
                    "status": "active",
                    "geographyDetails": "NOT_USED",
                },
                ...
            }
        """
        with self._lock:
            self._zones.update(zones)

    def list_zones(self) -> List[Dict]:
        """Return all zone records as a list of dicts."""
        with self._lock:
            return [dict(v) for v in self._zones.values()]

    def resolve_domain_id_by_zone_uuid(self, zone_uuid: str) -> Optional[str]:
        """
        Given the edgeCloudZoneId (UUID string), return the original aerOS domain id.
        Performs a simple scan — fine for small to medium sets.
        """
        with self._lock:
            for domain_id, zone in self._zones.items():
                if zone.get("edgeCloudZoneId") == zone_uuid:
                    return domain_id
            return None

    # ------------------------------------------------------------------------
    # CAMARA
    # ------------------------------------------------------------------------
    def store_app(self, app_id: str, manifest: Dict) -> None:
        with self._lock:
            self._apps[app_id] = manifest

    def get_app(self, app_id: str) -> Optional[Dict]:
        with self._lock:
            return self._apps.get(app_id)

    def app_exists(self, app_id: str) -> bool:
        with self._lock:
            return app_id in self._apps

    def list_apps(self) -> List[Dict]:
        with self._lock:
            # shallow copies to avoid external mutation of nested dicts
            return [dict(m) for m in self._apps.values()]

    def delete_app(self, app_id: str) -> None:
        with self._lock:
            self._apps.pop(app_id, None)

    def store_deployment(self, app_instance: AppInstanceInfo) -> None:
        with self._lock:
            # Ensure the key is a plain string
            aid = getattr(app_instance.appId, "root", str(app_instance.appId))
            self._deployed.setdefault(aid, []).append(app_instance)

    def get_deployments(self, app_id: Optional[str] = None) -> Dict[str, List[str]]:
        with self._lock:
            if app_id:
                ids = [str(i.appInstanceId) for i in self._deployed.get(app_id, [])]
                return {app_id: ids}
            return {
                aid: [str(i.appInstanceId) for i in insts] for aid, insts in self._deployed.items()
            }

    def find_deployments(
        self,
        app_id: Optional[str] = None,
        app_instance_id: Optional[str] = None,
        region: Optional[str] = None,
    ) -> List[AppInstanceInfo]:
        with self._lock:
            # Fast path by instance id
            if app_instance_id:
                for insts in self._deployed.values():
                    for inst in insts:
                        if str(inst.appInstanceId.root) == app_instance_id:
                            if app_id and str(inst.appId) != app_id:
                                return []
                            if region is not None and getattr(inst, "region", None) != region:
                                return []
                            return [inst]
                return []

            results: List[AppInstanceInfo] = []
            for aid, insts in self._deployed.items():
                if app_id and aid != app_id:
                    continue
                for inst in insts:
                    if region is not None and getattr(inst, "region", None) != region:
                        continue
                    results.append(inst)
            return results

    def remove_deployment(self, app_instance_id: str) -> Optional[str]:
        with self._lock:
            for aid, insts in list(self._deployed.items()):
                for idx, inst in enumerate(insts):
                    # Compare using the instance id string
                    inst_id = getattr(inst.appInstanceId, "root", str(inst.appInstanceId))
                    if inst_id == app_instance_id:
                        insts.pop(idx)
                        if not insts:
                            self._deployed.pop(aid, None)
                        # Return a plain string app_id
                        aid_str = getattr(aid, "root", str(aid))
                        return aid_str
            return None

    def store_stopped_instance(self, app_id: str, app_instance_id: str) -> None:
        with self._lock:
            lst = self._stopped.setdefault(app_id, [])
            if app_instance_id not in lst:
                lst.append(app_instance_id)

    def get_stopped_instances(
        self, app_id: Optional[str] = None
    ) -> Union[List[str], Dict[str, List[str]]]:
        with self._lock:
            if app_id:
                return list(self._stopped.get(app_id, []))
            return {aid: list(ids) for aid, ids in self._stopped.items()}

    def remove_stopped_instances(self, app_id: str) -> None:
        with self._lock:
            self._stopped.pop(app_id, None)

    # ------------------------------------------------------------------------
    # GSMA
    # ------------------------------------------------------------------------
    def store_app_gsma(self, app_id: str, model: ApplicationModel) -> None:
        with self._lock:
            self._apps_gsma[app_id] = model

    def get_app_gsma(self, app_id: str) -> Optional[ApplicationModel]:
        with self._lock:
            return self._apps_gsma.get(app_id)

    def list_apps_gsma(self) -> List[ApplicationModel]:
        with self._lock:
            return list(self._apps_gsma.values())

    def delete_app_gsma(self, app_id: str) -> None:
        with self._lock:
            self._apps_gsma.pop(app_id, None)

    def store_deployment_gsma(
        self,
        app_id: str,
        inst: AppInstance,
        status: Optional[AppInstanceStatus] = None,  # not persisted yet
    ) -> None:
        with self._lock:
            self._deployed_gsma.setdefault(app_id, []).append(inst)
            # If you later want to persist status per instance, keep a side map:
            # self._status_gsma[inst.appInstIdentifier] = status

    def get_deployments_gsma(self, app_id: Optional[str] = None) -> Dict[str, List[str]]:
        with self._lock:
            if app_id:
                ids = [str(i.appInstIdentifier) for i in self._deployed_gsma.get(app_id, [])]
                return {app_id: ids}
            return {
                aid: [str(i.appInstIdentifier) for i in insts]
                for aid, insts in self._deployed_gsma.items()
            }

    def find_deployments_gsma(
        self,
        app_id: Optional[str] = None,
        app_instance_id: Optional[str] = None,
        zone_id: Optional[str] = None,
    ) -> List[AppInstance]:
        with self._lock:
            # Limit the search space if app_id is provided
            iter_lists = (
                [self._deployed_gsma.get(app_id, [])] if app_id else self._deployed_gsma.values()
            )

            # Fast path: instance id provided
            if app_instance_id:
                target_id = str(app_instance_id)
                for insts in iter_lists:
                    for inst in insts:
                        if str(inst.appInstIdentifier) != target_id:
                            continue
                        if zone_id is not None and inst.zoneId != zone_id:
                            continue
                        return [inst]
                return []

            # General filtering
            results: List[AppInstance] = []
            for insts in iter_lists:
                for inst in insts:
                    if zone_id is not None and inst.zoneId != zone_id:
                        continue
                    results.append(inst)
            return results

    def remove_deployment_gsma(self, app_instance_id: str) -> Optional[str]:
        with self._lock:
            for aid, insts in list(self._deployed_gsma.items()):
                for idx, inst in enumerate(insts):
                    if str(inst.appInstIdentifier) == app_instance_id:
                        insts.pop(idx)
                        if not insts:
                            self._deployed_gsma.pop(aid, None)
                        return aid
            return None

    def store_stopped_instance_gsma(self, app_id: str, app_instance_id: str) -> None:
        with self._lock:
            lst = self._stopped_gsma.setdefault(app_id, [])
            if app_instance_id not in lst:
                lst.append(app_instance_id)

    def get_stopped_instances_gsma(
        self, app_id: Optional[str] = None
    ) -> Union[List[str], Dict[str, List[str]]]:
        with self._lock:
            if app_id:
                return list(self._stopped_gsma.get(app_id, []))
            return {aid: list(ids) for aid, ids in self._stopped_gsma.items()}

    def remove_stopped_instances_gsma(self, app_id: str) -> None:
        with self._lock:
            self._stopped_gsma.pop(app_id, None)

    # ------------------------------------------------------------------------
    # GSMA Artefacts
    # ------------------------------------------------------------------------
    def store_artefact_gsma(self, artefact: Artefact) -> None:
        with self._lock:
            self._artefacts_gsma[artefact.artefactId] = artefact

    def get_artefact_gsma(self, artefact_id: str) -> Optional[Artefact]:
        with self._lock:
            return self._artefacts_gsma.get(artefact_id)

    def list_artefacts_gsma(self) -> List[Artefact]:
        with self._lock:
            return list(self._artefacts_gsma.values())

    def delete_artefact_gsma(self, artefact_id: str) -> None:
        with self._lock:
            self._artefacts_gsma.pop(artefact_id, None)
