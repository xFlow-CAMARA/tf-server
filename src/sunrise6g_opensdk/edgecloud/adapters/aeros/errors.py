"""
Custom aerOS adapter exceptions on top of EdgeCloudPlatformError
"""

from sunrise6g_opensdk.edgecloud.adapters.errors import EdgeCloudPlatformError


class InvalidArgumentError(EdgeCloudPlatformError):
    """400 Bad Request"""

    pass


class UnauthenticatedError(EdgeCloudPlatformError):
    """401 Unauthorized"""

    pass


class PermissionDeniedError(EdgeCloudPlatformError):
    """403 Forbidden"""

    pass


class ResourceNotFoundError(EdgeCloudPlatformError):
    """404 Not Found"""

    pass


class ServiceUnavailableError(EdgeCloudPlatformError):
    """503 Service Unavailable"""

    pass
