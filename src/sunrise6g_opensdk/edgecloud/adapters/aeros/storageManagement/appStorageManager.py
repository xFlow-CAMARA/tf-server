"""
# Class: AppStorageManager
# Abstract base class for application storage backends.
# This module defines the interface for managing application storage,
#"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union

from sunrise6g_opensdk.edgecloud.core.camara_schemas import AppInstanceInfo
from sunrise6g_opensdk.edgecloud.core.gsma_schemas import (
    AppInstance,
    AppInstanceStatus,
    ApplicationModel,
    Artefact,
)


class AppStorageManager(ABC):
    """Abstract base class for application storage backends."""

    # ------------------------------------------------------------------------
    # aerOS Domain → Zone mapping
    # ------------------------------------------------------------------------
    @abstractmethod
    def store_zones(self, zones: Dict[str, Dict]) -> None:
        """Store or update the aerOS domain → zone info mapping."""

    @abstractmethod
    def list_zones(self) -> List[Dict]:
        """Return a list of all stored zone records (values)."""

    @abstractmethod
    def resolve_domain_id_by_zone_uuid(self, zone_uuid: str) -> Optional[str]:
        """Return the aerOS domain id (key) for a given edgeCloudZoneId (UUID)."""

    # ------------------------------------------------------------------------
    # CAMARA
    # ------------------------------------------------------------------------

    @abstractmethod
    def store_app(self, app_id: str, manifest: Dict) -> None:
        pass

    @abstractmethod
    def get_app(self, app_id: str) -> Optional[Dict]:
        pass

    @abstractmethod
    def app_exists(self, app_id: str) -> bool:
        pass

    @abstractmethod
    def list_apps(self) -> List[Dict]:
        pass

    @abstractmethod
    def delete_app(self, app_id: str) -> None:
        pass

    @abstractmethod
    def store_deployment(self, app_instance: AppInstanceInfo) -> None:
        pass

    @abstractmethod
    def get_deployments(self, app_id: Optional[str] = None) -> Dict[str, List[str]]:
        pass

    @abstractmethod
    def find_deployments(
        self,
        app_id: Optional[str] = None,
        app_instance_id: Optional[str] = None,
        region: Optional[str] = None,
    ) -> List[AppInstanceInfo]:
        pass

    @abstractmethod
    def remove_deployment(self, app_instance_id: str) -> Optional[str]:
        """Removes the given instance ID and returns the corresponding app_id, if found."""
        pass

    @abstractmethod
    def store_stopped_instance(self, app_id: str, app_instance_id: str) -> None:
        pass

    @abstractmethod
    def get_stopped_instances(
        self, app_id: Optional[str] = None
    ) -> List[str] | Dict[str, List[str]]:
        pass

    @abstractmethod
    def remove_stopped_instances(self, app_id: str) -> None:
        pass

    # ------------------------------------------------------------------------
    # GSMA
    # ------------------------------------------------------------------------
    @abstractmethod
    def store_app_gsma(self, app_id: str, model: ApplicationModel) -> None:
        """Implement in subclass."""
        raise NotImplementedError

    @abstractmethod
    def get_app_gsma(self, app_id: str) -> Optional[ApplicationModel]:
        """Implement in subclass."""
        raise NotImplementedError

    @abstractmethod
    def list_apps_gsma(self) -> List[ApplicationModel]:
        """Implement in subclass."""
        raise NotImplementedError

    @abstractmethod
    def delete_app_gsma(self, app_id: str) -> None:
        """Implement in subclass."""
        raise NotImplementedError

    @abstractmethod
    def store_deployment_gsma(
        self,
        app_id: str,
        inst: AppInstance,
        status: Optional[AppInstanceStatus] = None,  # optional future use
    ) -> None:
        """Implement in subclass."""
        raise NotImplementedError

    @abstractmethod
    def get_deployments_gsma(self, app_id: Optional[str] = None) -> Dict[str, List[str]]:
        """Implement in subclass."""
        raise NotImplementedError

    @abstractmethod
    def find_deployments_gsma(
        self,
        app_id: Optional[str] = None,
        app_instance_id: Optional[str] = None,
        zone_id: Optional[str] = None,
    ) -> List[AppInstance]:
        """Implement in subclass."""
        raise NotImplementedError

    @abstractmethod
    def remove_deployment_gsma(self, app_instance_id: str) -> Optional[str]:
        """Implement in subclass."""
        raise NotImplementedError

    @abstractmethod
    def store_stopped_instance_gsma(self, app_id: str, app_instance_id: str) -> None:
        """Implement in subclass."""
        raise NotImplementedError

    @abstractmethod
    def get_stopped_instances_gsma(
        self, app_id: Optional[str] = None
    ) -> Union[List[str], Dict[str, List[str]]]:
        """Implement in subclass."""
        raise NotImplementedError

    @abstractmethod
    def remove_stopped_instances_gsma(self, app_id: str) -> None:
        """Implement in subclass."""
        raise NotImplementedError

    # --- GSMA Artefacts ---
    @abstractmethod
    def store_artefact_gsma(self, artefact: Artefact) -> None:
        """Implement in subclass."""
        raise NotImplementedError

    @abstractmethod
    def get_artefact_gsma(self, artefact_id: str) -> Optional[Artefact]:
        """Implement in subclass."""
        raise NotImplementedError

    @abstractmethod
    def list_artefacts_gsma(self) -> List[Artefact]:
        """Implement in subclass."""
        raise NotImplementedError

    @abstractmethod
    def delete_artefact_gsma(self, artefact_id: str) -> None:
        """Implement in subclass."""
        raise NotImplementedError
