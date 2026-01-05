##
# This file is part of the TF SDK
#
# Contributors:
#   - Vasilis Pitsilis (vpitsilis@dat.demokritos.gr, vpitsilis@iit.demokritos.gr)
#   - Andreas Sakellaropoulos (asakellaropoulos@iit.demokritos.gr)
##
"""
aerOS help methods
"""
import string
import uuid

from requests.exceptions import HTTPError, RequestException, Timeout

import sunrise6g_opensdk.edgecloud.adapters.aeros.config as config
import sunrise6g_opensdk.edgecloud.adapters.aeros.errors as errors
from sunrise6g_opensdk.logger import setup_logger

_HEX = "0123456789abcdef"
_ALLOWED = set(
    string.ascii_letters + string.digits
)  # no underscore here; underscore is always escaped
_PREFIX = "A0_"  # ensures name starts with a letter; stripped during decode


def encode_app_instance_name(original: str, *, max_len: int = 64) -> str:
    """
    aerOS to CAMARA AppInstanceName encoder.
    Reversibly encode `original` into a string matching ^[A-Za-z][A-Za-z0-9_]{1,63}$.
    Uses underscore + two hex digits to escape any non [A-Za-z0-9] chars, including '_' itself.
    If the encoded result would exceed `max_len`, raise ValueError (reversibility would be lost otherwise).
    """
    out = []
    for ch in original:
        if ch in _ALLOWED:
            out.append(ch)
        elif ch == "_":
            out.append("_5f")
        else:
            # escape any other byte as _hh (lowercase hex)
            out.append("_" + format(ord(ch), "02x"))

    enc = "".join(out)

    # must start with a letter
    if not enc or enc[0] not in string.ascii_letters:
        enc = _PREFIX + enc

    if len(enc) > max_len:
        raise ValueError(
            f"Encoded name exceeds {max_len} chars; cannot keep reversibility without external mapping."
        )
    return enc


def decode_app_instance_name(encoded: str) -> str:
    """
    CAMARA AppInstanceName to aerOS original app_id decoder.
    Reverse of encode_app_instance_name. Restores the exact original string.
    """
    s = encoded
    if s.startswith(_PREFIX):
        s = s[len(_PREFIX) :]

    # walk and decode _hh sequences; underscores never appear unescaped in the encoding
    i = 0
    out = []
    while i < len(s):
        ch = s[i]
        if ch != "_":
            out.append(ch)
            i += 1
            continue

        # expect two hex digits after underscore
        if i + 2 >= len(s):
            raise ValueError("Invalid escape at end of string.")
        h1 = s[i + 1].lower()
        h2 = s[i + 2].lower()
        if h1 not in _HEX or h2 not in _HEX:
            raise ValueError(f"Invalid escape sequence: _{h1}{h2}")
        code = int(h1 + h2, 16)
        out.append(chr(code))
        i += 3

    return "".join(out)


def urn_to_uuid(urn: str) -> uuid.UUID:
    """Convert a (ngsi-ld) URN string to a deterministic UUID."""
    return uuid.uuid5(uuid.NAMESPACE_URL, urn)


def map_aeros_service_status_to_gsma(status: str) -> str:
    """
    Map aerOS service lifecycle states to GSMA-compliant status values.

    aerOS → GSMA
      DEPLOYING       → PENDING
      DESTROYING      → TERMINATING
      DEPLOYED        → DEPLOYED
      FINISHED        → No_Match
      No_Match        → READY
      urn:ngsi-ld:null → No Match
    """
    mapping = {
        "DEPLOYING": "PENDING",
        "DESTROYING": "TERMINATING",
        "DEPLOYED": "DEPLOYED",
        "FINISHED": "READY",
        # "urn:ngsi-ld:null": "READY",
    }
    if not status:
        return "FAILED"
    return mapping.get(status.strip().upper(), "FAILED")


def catch_requests_exceptions(func):
    """
    Decorator to catch and translate requests exceptions into custom app errors.
    """
    logger = setup_logger(__name__, is_debug=True, file_name=config.LOG_FILE)

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)

        except HTTPError as e:
            response = getattr(e, "response", None)
            status_code = getattr(response, "status_code", None)
            logger.error("HTTPError occurred: %s", e)

            if status_code == 401:
                raise errors.UnauthenticatedError("Unauthorized access") from e
            elif status_code == 403:
                raise errors.PermissionDeniedError("Forbidden access") from e
            elif status_code == 404:
                raise errors.ResourceNotFoundError("Resource not found") from e
            elif status_code == 400:
                raise errors.InvalidArgumentError("Bad request") from e
            elif status_code == 503:
                raise errors.ServiceUnavailableError("Service unavailable") from e

            raise errors.EdgeCloudPlatformError(f"Unhandled HTTP error: {status_code}") from e

        except Timeout as e:
            logger.warning("Timeout occurred: %s", e)
            raise errors.ServiceUnavailableError("Request timed out") from e

        except ConnectionError as e:
            logger.warning("Connection error (e.g., DNS): %s", e)
            raise errors.ServiceUnavailableError("Connection issue") from e

        except RequestException as e:
            # Catch other unclassified request exceptions (non-HTTP)
            logger.error("Request failed: %s", str(e))

            if e.response is not None:
                logger.error("Status Code: %s", e.response.status_code)
                logger.error("Response Body (raw): %s", e.response.text)

                try:
                    json_data = e.response.json()
                    logger.debug("Parsed JSON response: %s", json_data)
                except ValueError:
                    logger.warning("Response body is not valid JSON.")

            if e.request is not None:
                logger.error("Request URL: %s", e.request.url)
                logger.error("Request Method: %s", e.request.method)
                logger.error("Request Headers: %s", e.request.headers)
                logger.error("Request Body: %s", e.request.body)

            raise errors.EdgeCloudPlatformError("Unhandled request error") from e

    return wrapper
