#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CAMARA Traffic Influence API Example

This example demonstrates how to create, retrieve, and delete traffic influence
resources using the TF SDK with CoreSim + NEF stack.
"""

from sunrise6g_opensdk.common.sdk import Sdk as sdkclient
import json
import time


def main():
    print("\n" + "=" * 70)
    print("CAMARA Traffic Influence API Example")
    print("=" * 70)

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

    # Start simulation
    try:
        print("\n--- Starting CoreSim Simulation ---")
        network_client.start_simulation()
        print("✓ Simulation started")
        time.sleep(2)
    except Exception as e:
        print(f"✗ Failed to start simulation: {e}")
        return

    # Create Traffic Influence Resource
    try:
        print("\n--- Creating Traffic Influence Resource ---")
        traffic_influence_info = {
            "appId": "app-video-streaming-123",
            "appInstanceId": "10.0.0.5",  # Server IP
            "edgeCloudZoneId": "DNAI1",
            "notificationUri": "http://localhost:9092/eventsubscriptions",
            "device": {
                "ipv4Address": {
                    "publicAddress": "12.1.0.2",  # Same IP as QoD example
                    "privateAddress": "12.1.0.2"
                }
            }
        }

        ti_resource = network_client.create_traffic_influence_resource(traffic_influence_info)
        resource_id = ti_resource.get("trafficInfluenceID")
        print(f"✓ Traffic influence resource created")
        print(f"  Resource ID: {resource_id}")
        print(f"  App ID: {ti_resource.get('appId', 'N/A')}")
        print(f"  App Instance: {ti_resource.get('appInstanceId', 'N/A')}")
        print(f"  Edge Zone: {ti_resource.get('edgeCloudZoneId', 'N/A')}")
        
        # Display full NEF response as JSON
        print("\n  Full NEF Response:")
        print(json.dumps(ti_resource, indent=2, default=str))

    except Exception as e:
        print(f"✗ Failed to create traffic influence: {e}")
        import traceback
        traceback.print_exc()
        return

    # Get Traffic Influence Resource Details
    try:
        print("\n--- Getting Traffic Influence Resource Details ---")
        ti_details = network_client.get_individual_traffic_influence_resource(resource_id)
        print(f"✓ Traffic influence details retrieved")
        print(f"  Device IP: {ti_details.get('ipv4Addr', 'N/A')}")
        print(f"  Server IP: {ti_details.get('appInstanceId', 'N/A')}")
        print(f"  Edge Zone: {ti_details.get('edgeCloudZoneId', 'N/A')}")
        print(f"  DNN: {ti_details.get('dnn', 'N/A')}")
        
        # Display full NEF response as JSON
        print("\n  Full NEF Response:")
        print(json.dumps(ti_details, indent=2, default=str))

    except Exception as e:
        print(f"✗ Failed to get traffic influence details: {e}")
        import traceback
        traceback.print_exc()

    # Update Traffic Influence Resource
    try:
        print("\n--- Updating Traffic Influence Resource ---")
        updated_info = traffic_influence_info.copy()
        updated_info["edgeCloudZoneId"] = "DNAI2"  # Update zone

        updated_ti = network_client.put_traffic_influence_resource(resource_id, updated_info)
        print(f"✓ Traffic influence resource updated")
        print(f"  New Edge Zone: {updated_ti.get('edgeCloudZoneId', 'N/A')}")
        
        # Display full NEF response as JSON
        print("\n  Full NEF Response:")
        print(json.dumps(updated_ti, indent=2, default=str))

    except Exception as e:
        print(f"✗ Failed to update traffic influence: {e}")
        import traceback
        traceback.print_exc()

    # Get All Traffic Influence Resources
    try:
        print("\n--- Getting All Traffic Influence Resources ---")
        all_resources = network_client.get_all_traffic_influence_resource()
        print(f"✓ Retrieved {len(all_resources)} traffic influence resource(s)")
        for i, resource in enumerate(all_resources, 1):
            device_ip = resource.get('ipv4Addr', 'N/A')
            app_id = resource.get('afAppId', 'N/A')
            print(f"  Resource {i}: {app_id} -> Device IP: {device_ip}")
        
        # Display full NEF response as JSON
        if all_resources:
            print("\n  Full NEF Response:")
            print(json.dumps(all_resources, indent=2, default=str))

    except Exception as e:
        print(f"✗ Failed to get all resources: {e}")
        import traceback
        traceback.print_exc()

    # Delete Traffic Influence Resource
    try:
        print("\n--- Deleting Traffic Influence Resource ---")
        network_client.delete_traffic_influence_resource(resource_id)
        print(f"✓ Traffic influence resource deleted: {resource_id}")

    except Exception as e:
        print(f"✗ Failed to delete traffic influence: {e}")
        import traceback
        traceback.print_exc()


    # Stop simulation
    try:
        print("\n--- Stopping CoreSim Simulation ---")
        network_client.stop_simulation()
        print("✓ Simulation stopped")
    except Exception as e:
        print(f"✗ Failed to stop simulation: {e}")

    print("\n" + "=" * 70)
    print("Traffic Influence API Example Completed Successfully")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
