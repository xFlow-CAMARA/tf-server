# -*- coding: utf-8 -*-
##
#
# This file is part of the Open SDK.
# Defines some fixed mappings that in future releases could be done dynamically
# Contributors:
#   - Miguel Catalan Cid (miguel.catalan@i2cat.net)
##

# mapping from QoD to O-RAN policy
qos_prio_to_oran_prio = {
    "qos-e": "qos-e",
    "qos-s": "qos-s",
    "qos-m": "qos-m",
    "qos-l": "qos-l",
}
# mapping from QoD to 5qi
flow_id_mapping = {"qos-e": 3, "qos-s": 4, "qos-m": 5, "qos-l": 6}


# Maps an IP address to PLMN and gNB identifiers
# Keys: IP (str)
# Values: {"mcc": str, "mnc": str, "gnb_length": int, "gnb_id": int}
ip_to_plmn_gnb_mapping = {
    # Example entries:
    "192.168.1.10": {
        "mcc": "001",
        "mnc": "01",
        "gnb_length": 28,
        "gnb_id": 12345,
        "ran_ue_id": "0000000000000001",
    },
    "10.10.45.1": {
        "mcc": "214",
        "mnc": "07",
        "gnb_length": 28,
        "gnb_id": 67890,
        "ran_ue_id": "0000000000000033",
    },
}

# maps a CAMARA policy request to the information type in the oran NEF
policy_mapping = {"oran-qod": "qod_prb_prio"}
