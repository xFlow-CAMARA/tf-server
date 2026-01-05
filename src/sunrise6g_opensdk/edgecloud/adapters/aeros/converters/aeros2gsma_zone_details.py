"""
aeros2gsma_zone_details.py
"""

from typing import Any, Dict, List


def transformer(domain_ies: List[Dict[str, Any]], domain: str) -> Dict[str, Any]:  # noqa: C901
    """
    Transform aerOS InfrastructureElements into GSMA ZoneRegisteredData structure.
    :param domain_ies: List of aerOS InfrastructureElement dicts
    :param domain: The ID of the edge cloud zone (zoneId)
    :return: Dict matching gsma_schemas.ZoneRegisteredData (JSON-serializable)
    """

    def map_cpu_arch_to_isa(urn: str) -> str:
        """
        Map aerOS cpuArchitecture URN to GSMA ISA_* literal.
        Examples:
          'urn:ngsi-ld:CpuArchitecture:x64'   -> 'ISA_X86_64'
          'urn:ngsi-ld:CpuArchitecture:arm64' -> 'ISA_ARM_64'
          'urn:ngsi-ld:CpuArchitecture:arm32' -> 'ISA_ARM_64' (closest)
          'urn:ngsi-ld:CpuArchitecture:x86'   -> 'ISA_X86'
        Fallback: 'ISA_X86_64'
        """
        if not isinstance(urn, str):
            return "ISA_X86_64"
        tail = urn.split(":")[-1].lower()
        if tail in ("x64", "x86_64", "amd64"):
            return "ISA_X86_64"
        if tail in ("x86", "i386", "i686"):
            return "ISA_X86"
        if tail in ("arm64", "aarch64"):
            return "ISA_ARM_64"
        if tail in ("arm32", "arm"):
            # GSMA only has ARM_64 vs X86/X86_64; pick closest
            return "ISA_ARM_64"
        return "ISA_X86_64"

    def map_cpu_arch_to_ostype_arch(urn: str) -> str:
        """
        Map aerOS cpuArchitecture URN to OSType.architecture literal: 'x86_64' or 'x86'.
        Use 'x86_64' for x64/arm64 (closest allowed), and 'x86' for x86/arm32.
        """
        if not isinstance(urn, str):
            return "x86_64"
        tail = urn.split(":")[-1].lower()
        if tail in ("x64", "x86_64", "amd64", "arm64", "aarch64"):
            return "x86_64"
        if tail in ("x86", "i386", "i686", "arm32", "arm"):
            return "x86"
        return "x86_64"

    def map_os_distribution(_urn: str) -> str:
        """
        aerOS uses 'urn:ngsi-ld:OperatingSystem:Linux' etc.
        map Linux -> UBUNTU (assume), else OTHER.
        """
        if isinstance(_urn, str) and _urn.split(":")[-1].lower() == "linux":
            return "UBUNTU"
        return "OTHER"

    def default_os_version(dist: str) -> str:
        # You asked to assume Ubuntu 22.04 LTS for Linux
        return "OS_VERSION_UBUNTU_2204_LTS" if dist == "UBUNTU" else "OTHER"

    # Totals (aggregate over elements)
    total_cpu = 0
    total_ram = 0
    total_disk = 0
    total_available_ram = 0
    total_available_disk = 0

    flavours_supported: List[Dict[str, Any]] = []
    seen_cpu_isas: set[str] = set()

    for element in domain_ies:
        cpu_cores = int(element.get("cpuCores", 0) or 0)
        ram_cap = int(element.get("ramCapacity", 0) or 0)  # MB?
        avail_ram = int(element.get("availableRam", 0) or 0)  # MB?
        disk_cap = int(element.get("diskCapacity", 0) or 0)  # MB/GB? (pass-through)
        avail_disk = int(element.get("availableDisk", 0) or 0)

        total_cpu += cpu_cores
        total_ram += ram_cap
        total_available_ram += avail_ram
        total_disk += disk_cap
        total_available_disk += avail_disk

        cpu_arch_urn = element.get("cpuArchitecture", "")
        os_urn = element.get("operatingSystem", "")

        isa = map_cpu_arch_to_isa(cpu_arch_urn)
        seen_cpu_isas.add(isa)
        ost_arch = map_cpu_arch_to_ostype_arch(cpu_arch_urn)
        dist = map_os_distribution(os_urn)
        ver = default_os_version(dist)

        # Create a flavour per machine
        flavour = {
            "flavourId": f"{element.get('hostname', 'host')}-{element.get('containerTechnology', 'CT')}",
            "cpuArchType": isa,  # Literal ISA_*
            "supportedOSTypes": [
                {
                    "architecture": ost_arch,  # 'x86_64' or 'x86'
                    "distribution": dist,  # 'UBUNTU' or 'OTHER'
                    "version": ver,  # 'OS_VERSION_UBUNTU_2204_LTS' or 'OTHER'
                    "license": "OS_LICENSE_TYPE_FREE",
                }
            ],
            "numCPU": cpu_cores,
            "memorySize": ram_cap,
            "storageSize": disk_cap,
        }
        flavours_supported.append(flavour)

    # Decide a single ISA for the aggregate reserved/quota entries
    # Preference order: X86_64, ARM_64, X86
    def pick_aggregate_isa() -> str:
        if "ISA_X86_64" in seen_cpu_isas:
            return "ISA_X86_64"
        if "ISA_ARM_64" in seen_cpu_isas:
            return "ISA_ARM_64"
        if "ISA_X86" in seen_cpu_isas:
            return "ISA_X86"
        # fallback
        return "ISA_X86_64"

    agg_isa = pick_aggregate_isa()

    result = {
        "zoneId": domain,
        "reservedComputeResources": [
            {
                "cpuArchType": agg_isa,
                "numCPU": int(
                    total_cpu
                ),  # Same as Quotas untill we have somem policy or data to differentiate
                "memory": total_ram,  # ditto
            }
        ],
        "computeResourceQuotaLimits": [
            {
                "cpuArchType": agg_isa,
                "numCPU": int(total_cpu),
                "memory": total_ram,
            }
        ],
        "flavoursSupported": flavours_supported,
    }

    return result
