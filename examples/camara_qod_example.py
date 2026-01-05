#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CAMARA QoD (Quality of Demand) API Example

This example demonstrates how to create, retrieve, and delete QoD sessions
using the TF SDK with CoreSim + NEF stack.

CoreSim Constraints:
- UE IPs must be from the 12.1.0.0/16 subnet (CoreSim's default IPAM allocation)
- NEF requires 'dnn' field (defaults to 'internet')
- NEF requires 'flowInfo' with flowId and flowDescriptions array
- QoS profiles must be configured in NEF asSessionWithQos.yaml (qos-e, qos2, qos3, qos4)
"""

from sunrise6g_opensdk.common.sdk import Sdk as sdkclient
import json
import time
import os


def main():
    print("\n" + "=" * 70)
    print("CAMARA QoD (Quality of Demand) API Example")
    print("=" * 70)

    # Initialize CoreSim adapter with configurable endpoints
    coresim_base = os.getenv("CORESIM_BASE_URL", "http://localhost:8080")
    qod_base = os.getenv("NEF_QOD_BASE_URL", "http://localhost:8100")
    redis_addr = os.getenv("REDIS_ADDR", "localhost:6380")
    nef_callback = os.getenv("NEF_CALLBACK_URL", "http://localhost:9092/eventsubscriptions")
    
    adapter_specs = {
        "network": {
            "client_name": "coresim",
            "base_url": coresim_base,
            "scs_as_id": "nef",
            "oam_port": 8081,
            "redis_addr": redis_addr,
            "nef_callback_url": nef_callback,
            "qod_base_url": qod_base,
            "location_base_url": os.getenv("NEF_LOCATION_BASE_URL", "http://localhost:8102"),
            "ti_base_url": os.getenv("NEF_TI_BASE_URL", "http://localhost:8101"),
        }
    }

    try:
        adapters = sdkclient.create_adapters_from(adapter_specs)
        network_client = adapters.get("network")
        print("\n✓ Network client initialized")
    except Exception as e:
        print(f"✗ Failed to initialize client: {e}")
        return

    # Start simulation
    try:
        print("\n--- Starting CoreSim Simulation ---")
        status = network_client.get_status()
        print(f"Current status: {json.dumps(status, indent=2)}")
        
        network_client.start_simulation()
        print("✓ Simulation started")
        time.sleep(2)
    except Exception as e:
        print(f"✗ Failed to start simulation: {e}")
        return

    # Create QoD Session
    try:
        print("\n--- Creating QoD Session ---")
        session_info = {
            "device": {
                "ipv4Address": {
                    "publicAddress": "12.1.0.1",  # CoreSim IPAM allocation (12.1.0.0/16)
                    "privateAddress": "10.0.0.100"
                }
            },
            "applicationServer": {
                "ipv4Address": "10.0.0.1"
            },
            "qosProfile": "qos2",  # Using qos2 from NEF config (240 Mbps CONTROL)
            "duration": 3600,  # 1 hour
            "sink": "http://localhost:9092/eventsubscriptions"
        }

        session = network_client.create_qod_session(session_info)
        session_id = session["sessionId"]  # Serialized as string UUID, not a dict
        print(f"✓ QoD session created")
        print(f"  Session ID: {session_id}")
        print(f"  QoS Status: {session.get('qosStatus', 'N/A')}")
        print(f"  Duration: {session.get('duration', 'N/A')} seconds")
        print(f"\n  Full Response JSON:")
        print(json.dumps(session, indent=4, default=str))

    except Exception as e:
        print(f"✗ Failed to create QoD session: {e}")
        return

    # Get QoD Session Details
    try:
        print("\n--- Getting QoD Session Details ---")
        session_details = network_client.get_qod_session(session_id)
        print(f"✓ Session details retrieved")
        
        # NEF returns flat structure with these fields directly
        device_ipv4 = session_details.get('ueIpv4Addr', 'N/A')
        qos_profile = session_details.get('qosReference', 'N/A')
        dnn = session_details.get('dnn', 'N/A')
        flow_info = session_details.get('flowInfo', [])
        
        # Extract server IP from flow description if available
        server_ipv4 = 'N/A'
        if flow_info and len(flow_info) > 0:
            flow_desc = flow_info[0].get('flowDescriptions', [])
            if flow_desc and len(flow_desc) > 0:
                # Parse flow descriptor to extract server IP
                # Format: "permit in ip from 12.1.0.1 0-65535 to 10.0.0.1 0-65535, ..."
                desc = flow_desc[0]
                if 'to' in desc:
                    parts = desc.split('to')
                    if len(parts) > 1:
                        server_part = parts[1].strip().split()[0]
                        server_ipv4 = server_part.rstrip('/32')
        
        print(f"  Device IP (UE): {device_ipv4}")
        print(f"  Server IP: {server_ipv4}")
        print(f"  QoS Profile: {qos_profile}")
        print(f"  DNN: {dnn}")
        print(f"  Session ID: {session_details.get('self', 'N/A')}")
        
        # Get notification destination
        notif_dest = session_details.get('notificationDestination', 'N/A')
        print(f"  Notification URL: {notif_dest}")
        print(f"\n  Full NEF Response JSON:")
        print(json.dumps(session_details, indent=4, default=str))

    except Exception as e:
        print(f"✗ Failed to get session details: {e}")

    # Delete QoD Session
    try:
        print("\n--- Deleting QoD Session ---")
        network_client.delete_qod_session(session_id)
        print(f"✓ QoD session deleted: {session_id}")

    except Exception as e:
        print(f"✗ Failed to delete QoD session: {e}")

    # Stop simulation
    try:
        print("\n--- Stopping CoreSim Simulation ---")
        # Note: Stopping CoreSim will reset UE allocations on next start
        # For continuous testing, consider commenting this out
        # network_client.stop_simulation()
        # print("✓ Simulation stopped")
        print("⊘ Simulation stop skipped - UE allocations persist for next run")
    except Exception as e:
        print(f"✗ Failed to stop simulation: {e}")

    print("\n" + "=" * 70)
    print("QoD API Example Completed Successfully")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
