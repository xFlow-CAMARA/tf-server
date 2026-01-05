# -*- coding: utf-8 -*-

import requests
from pydantic import BaseModel

from sunrise6g_opensdk import logger

log = logger.get_logger(__name__)


def _make_request(method: str, url: str, data=None):
    try:
        headers = None
        if method == "POST" or method == "PUT":
            headers = {
                "Content-Type": "application/json",
                "accept": "application/json",
            }
        elif method == "GET":
            headers = {
                "accept": "application/json",
            }
        response = requests.request(method, url, headers=headers, data=data)
        response.raise_for_status()
        if response.content:
            return response.json()
    except requests.exceptions.HTTPError as e:
        status = None
        body = None
        try:
            if e.response is not None:
                status = e.response.status_code
                try:
                    body = e.response.json()
                except Exception:
                    body = e.response.text
        except Exception:
            pass
        raise OranHttpError(str(e), status_code=status, body=body) from e
    except requests.exceptions.ConnectionError as e:
        raise OranHttpError("connection error", status_code=None, body=None) from e


class CapabilityNotSupported(Exception):
    """Raised when a requested capability is not supported by the core."""

    pass


def requires_capability(feature: str):
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            if feature not in self.capabilities:
                # Client name is derived from the module
                module_path = self.__module__.split(".")
                try:
                    client_name = module_path[module_path.index("adapters") + 1]
                except (ValueError, IndexError):
                    client_name = self.__class__.__name__

                raise CapabilityNotSupported(
                    f"Functionality '{feature}' is nos supported by {client_name}"
                )
            return func(self, *args, **kwargs)

        return wrapper

    return decorator


class OranHttpError(Exception):
    def __init__(
        self, message: str, status_code: int | None = None, body: dict | str | None = None
    ):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


# Subscription Event Methods
def oran_subscription_post(base_url: str, scs_as_id: str, model_payload: BaseModel) -> dict:
    data = model_payload.model_dump_json(exclude_none=True, by_alias=True)
    url = oran_subscription_build(base_url, scs_as_id)
    return _make_request("POST", url, data=data)


def oran_subscription_build(base_url: str, scs_as_id: str, session_id: str = None):
    url = f"{base_url}/{scs_as_id}/subscriptions"
    if session_id is not None and len(session_id) > 0:
        return f"{url}/{session_id}"
    else:
        return url


# Policy methods
def oran_policy_post(base_url: str, scs_as_id: str, model_payload: BaseModel) -> dict:
    data = model_payload.model_dump_json(exclude_none=True, by_alias=True)
    url = oran_policy_build_url(base_url, scs_as_id)
    return _make_request("POST", url, data=data)


def oran_policy_get(base_url: str, scs_as_id: str, session_id: str) -> dict:
    url = oran_policy_build_url(base_url, scs_as_id, session_id)
    return _make_request("GET", url)


def oran_policy_delete(base_url: str, scs_as_id: str, session_id: str):
    url = oran_policy_build_url(base_url, scs_as_id, session_id)
    return _make_request("DELETE", url)


def oran_policy_build_url(base_url: str, scs_as_id: str, session_id: str = None):
    url = f"{base_url}/{scs_as_id}/oran-policies"
    if session_id is not None and len(session_id) > 0:
        return f"{url}/{session_id}"
    else:
        # Collection URL should end with a trailing slash to match FastAPI route
        return f"{url}/"
