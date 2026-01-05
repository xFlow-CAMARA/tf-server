#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete Integrated Example: End-to-End CAMARA API Workflow

This example demonstrates a complete workflow combining multiple CAMARA APIs
to simulate a realistic 5G network scenario with QoD, Location, and Traffic Influence.
"""

from sunrise6g_opensdk.common.sdk import Sdk as sdkclient
import json
import time


def main():
    print("\n" + "=" * 80)
    print("Complete End-to-End CAMARA API Workflow Example")
    print("=" * 80)

    # Initialize CoreSim adapter
    adapter_specs = {
        "network": {
            "client_name": "coresim",
            "base_url": "http://localhost:8080",
            "scs_as_id": "nef",
            "oam_port": 8081,
            "redis_addr": "localhost:6380",
            "nef_callback_url": "http://localhost:9092/eventsubscriptions"
        }
    }

    try:
        adapters = sdkclient.create_adapters_from(adapter_specs)
        network_client = adapters.get("network")
        print("\n✓ Network client initialized")
    except Exception as e:
        print(f"✗ Failed to initialize client: {e}")
        return

    # Step 1: Configure and Start Simulation
    print("\n" + "-" * 80)
    print("STEP 1: Configure and Start CoreSim Simulation")
    print("-" * 80)

    try:
        config = {
            "simulationProfile": {
                "plmn": {"mcc": "001", "mnc": "01"},
                "dnn": "internet",
                "slice": {"sst": 1, "sd": "FFFFFF"},
                "numOfUe": 5,
                "numOfgNB": 3,
                "arrivalRate": 1
            }
        }
        network_client.configure_simulation(config)
        print("✓ Simulation configured")

        network_client.start_simulation()
        print("✓ Simulation started")
        time.sleep(2)

    except Exception as e:
        print(f"✗ Failed to start simulation: {e}")
        return

    # Step 2: Create QoD Session
    print("\n" + "-" * 80)
    print("STEP 2: Create QoD Session for High-Quality Video Streaming")
    print("-" * 80)

    session_id = None
    try:
        session_info = {
            "device": {
                "ipv4Address": {
                    "publicAddress": "192.168.1.100",
                    "privateAddress": "10.0.0.100"
                }
            },
            "applicationServer": {
                "ipv4Address": "10.0.0.1"
            },
            "qosProfile": "qos-e",  # EMBB for video streaming
            "duration": 1800,  # 30 minutes
            "sink": "http://localhost:8001/qos-callback"
        }

        session = network_client.create_qod_session(session_info)
        session_id = session["sessionId"]["root"]
        print(f"✓ QoD session created: {session_id}")
        print(f"  Device: 192.168.1.100 -> Server: 10.0.0.1")
        print(f"  QoS Profile: EMBB (qos-e)")
        print(f"  Duration: 30 minutes")

    except Exception as e:
        print(f"✗ Failed to create QoD session: {e}")

    # Step 3: Get Location Information
    print("\n" + "-" * 80)
    print("STEP 3: Get UE Location Information")
    print("-" * 80)

    try:
        location_request = {
            "device": {
                "networkAccessIdentifier": "user@example.com",
                "ipv4Address": "192.168.1.100",
                "phoneNumber": "+34607123456"
            }
        }

        location = network_client.create_monitoring_event_subscription(location_request)
        print(f"✓ Location retrieved")
        print(f"  IMSI: user@example.com")
        print(f"  Last Location Time: {location.get('lastLocationTime', 'N/A')}")

    except Exception as e:
        print(f"✗ Failed to get location: {e}")

    # Step 4: Create Traffic Influence Rule
    print("\n" + "-" * 80)
    print("STEP 4: Create Traffic Influence Rule for Edge Routing")
    print("-" * 80)

    resource_id = None
    try:
        ti_info = {
            "appId": "streaming-edge-app",
            "appInstanceId": "10.0.0.5",  # Edge server
            "edgeCloudZoneId": "edge-zone-1",
            "notificationUri": "http://localhost:8001/ti-callback",
            "device": {
                "ipv4Address": {
                    "publicAddress": "192.168.1.100",
                    "privateAddress": "10.0.0.100"
                }
            }
        }

        ti = network_client.create_traffic_influence_resource(ti_info)
        resource_id = ti.get("trafficInfluenceID")
        print(f"✓ Traffic influence rule created: {resource_id}")
        print(f"  App: streaming-edge-app")
        print(f"  Routed to: 10.0.0.5 (Edge Server)")
        print(f"  Edge Zone: edge-zone-1")

    except Exception as e:
        print(f"✗ Failed to create traffic influence: {e}")

    # Step 5: Monitor Active Services
    print("\n" + "-" * 80)
    print("STEP 5: Monitor Active Services (simulating 10 seconds)")
    print("-" * 80)

    try:
        for i in range(5):
            time.sleep(2)
            status = network_client.get_status()
            print(f"[{i+1}] CoreSim Status: {status.get('Status', 'UNKNOWN')}")

    except Exception as e:
        print(f"✗ Failed to monitor: {e}")

    # Step 6: Update Traffic Influence
    print("\n" + "-" * 80)
    print("STEP 6: Update Traffic Influence to Different Edge Zone")
    print("-" * 80)

    if resource_id:
        try:
            updated_info = ti_info.copy()
            updated_info["edgeCloudZoneId"] = "edge-zone-2"

            network_client.put_traffic_influence_resource(resource_id, updated_info)
            print(f"✓ Traffic influence updated")
            print(f"  New Edge Zone: edge-zone-2")

        except Exception as e:
            print(f"✗ Failed to update traffic influence: {e}")

    # Step 7: Cleanup - Delete Resources
    print("\n" + "-" * 80)
    print("STEP 7: Cleanup - Delete All Resources")
    print("-" * 80)

    try:
        if session_id:
            network_client.delete_qod_session(session_id)
            print(f"✓ QoD session deleted: {session_id}")

        if resource_id:
            network_client.delete_traffic_influence_resource(resource_id)
            print(f"✓ Traffic influence rule deleted: {resource_id}")

    except Exception as e:
        print(f"✗ Failed to cleanup resources: {e}")

    # Step 8: Stop Simulation
    print("\n" + "-" * 80)
    print("STEP 8: Stop CoreSim Simulation")
    print("-" * 80)

    try:
        network_client.stop_simulation()
        print("✓ Simulation stopped")

        final_status = network_client.get_status()
        print(f"  Final Status: {final_status.get('Status', 'UNKNOWN')}")

    except Exception as e:
        print(f"✗ Failed to stop simulation: {e}")

    print("\n" + "=" * 80)
    print("End-to-End Workflow Completed Successfully!")
    print("=" * 80 + "\n")

    print("Summary:")
    print("  - Configured CoreSim with 5 UEs and 3 gNBs")
    print("  - Created QoD session for video streaming (EMBB)")
    print("  - Retrieved UE location information")
    print("  - Created and updated traffic influence rules")
    print("  - Monitored simulation status throughout")
    print("  - Cleaned up all resources\n")


if __name__ == "__main__":
    main()
