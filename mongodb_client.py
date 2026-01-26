"""
MongoDB client for CAMARA API persistence
Stores QoD and Traffic Influence request/response history
"""
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from pymongo import MongoClient, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database


class CamaraMongoClient:
    """MongoDB client for CAMARA API data persistence"""
    
    def __init__(self):
        mongodb_uri = os.getenv("MONGODB_URI", "mongodb://mongodb:27017/camara")
        self.client = MongoClient(mongodb_uri)
        self.db: Database = self.client.get_default_database()
        
        # Collections
        self.qod_sessions: Collection = self.db["qod_sessions"]
        # NOTE: MongoDB init script creates/validates this collection name.
        # Keep the variable name for API compatibility, but point it at the
        # validated collection.
        self.traffic_influences: Collection = self.db["traffic_influence_subscriptions"]
        
        # Create indexes
        self._create_indexes()
    
    def _create_indexes(self):
        """Create indexes for efficient querying"""
        # QoD indexes
        self.qod_sessions.create_index("sessionId", unique=True)
        self.qod_sessions.create_index("timestamp")
        self.qod_sessions.create_index([("timestamp", DESCENDING)])
        
        # Traffic Influence indexes
        # traffic_influence_subscriptions indexes
        self.traffic_influences.create_index("subscriptionId", unique=True)
        self.traffic_influences.create_index("createdAt")
        self.traffic_influences.create_index([("createdAt", DESCENDING)])
    
    # ========== QoD Session Operations ==========
    
    def save_qod_session(
        self,
        session_id: str,
        operation: str,  # "CREATE", "GET", "DELETE"
        request_data: Dict[str, Any],
        response_data: Dict[str, Any],
        status_code: int,
        device: Optional[Dict[str, Any]] = None,
        qos_profile: Optional[str] = None,
    ) -> str:
        """Save QoD session operation to MongoDB"""
        document = {
            "sessionId": session_id,
            "operation": operation,
            "createdAt": datetime.utcnow(),  # Changed from timestamp to createdAt
            "request": request_data,
            "response": response_data,
            "statusCode": status_code,
            "device": device or {},  # Ensure device is always an object
            "qosProfile": qos_profile or "QOS_E",  # Provide default if None
        }
        
        # For CREATE operations, insert new document
        if operation == "CREATE":
            result = self.qod_sessions.insert_one(document)
            return str(result.inserted_id)
        
        # For GET/DELETE operations, update existing document with new operation record
        else:
            # Add to operations history
            self.qod_sessions.update_one(
                {"sessionId": session_id},
                {
                    "$push": {
                        "operations": {
                            "operation": operation,
                            "timestamp": datetime.utcnow(),
                            "request": request_data,
                            "response": response_data,
                            "statusCode": status_code,
                        }
                    }
                },
                upsert=True
            )
            return session_id
    
    def get_qod_sessions(
        self,
        session_id: Optional[str] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get QoD sessions with optional filtering"""
        query = {}
        if session_id:
            query["sessionId"] = session_id
        
        cursor = self.qod_sessions.find(query).sort("createdAt", DESCENDING).skip(skip).limit(limit)
        sessions = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])  # Convert ObjectId to string
            sessions.append(doc)
        
        return sessions
    
    def delete_qod_session(self, session_id: str) -> bool:
        """Delete QoD session from history"""
        result = self.qod_sessions.delete_one({"sessionId": session_id})
        return result.deleted_count > 0
    
    def get_qod_session_count(self, session_id: Optional[str] = None) -> int:
        """Get total count of QoD sessions"""
        query = {}
        if session_id:
            query["sessionId"] = session_id
        return self.qod_sessions.count_documents(query)
    
    # ========== Traffic Influence Operations ==========
    
    def save_traffic_influence(
        self,
        traffic_influence_id: str,
        operation: str,  # "CREATE", "GET", "UPDATE", "DELETE"
        request_data: Dict[str, Any],
        response_data: Dict[str, Any],
        status_code: int,
        device: Optional[Dict[str, Any]] = None,
        traffic_filters: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Save Traffic Influence operation to MongoDB"""
        document = {
            "subscriptionId": traffic_influence_id,  # Changed to match MongoDB schema
            "trafficInfluenceId": traffic_influence_id,  # Keep for backward compatibility
            "operation": operation,
            "createdAt": datetime.utcnow(),  # Changed from timestamp to createdAt
            "request": request_data,
            "response": response_data,
            "statusCode": status_code,
            "device": device or {},  # Ensure device is always an object
            "trafficFilters": traffic_filters or [],
        }
        
        # For CREATE operations, insert new document
        if operation == "CREATE":
            result = self.traffic_influences.insert_one(document)
            return str(result.inserted_id)
        
        # For GET/UPDATE/DELETE operations, update existing document
        else:
            self.traffic_influences.update_one(
                {"subscriptionId": traffic_influence_id},
                {
                    # Keep a top-level snapshot for the dashboard history table.
                    "$set": {
                        "operation": operation,
                        "request": request_data,
                        "response": response_data,
                        "statusCode": status_code,
                        "device": device or {},
                        "trafficFilters": traffic_filters or [],
                    },
                    # Ensure schema-required fields exist if this is the first
                    # operation we see for this subscription.
                    "$setOnInsert": {
                        "subscriptionId": traffic_influence_id,
                        "trafficInfluenceId": traffic_influence_id,
                        "createdAt": datetime.utcnow(),
                    },
                    "$push": {
                        "operations": {
                            "operation": operation,
                            "timestamp": datetime.utcnow(),
                            "request": request_data,
                            "response": response_data,
                            "statusCode": status_code,
                        }
                    }
                },
                upsert=True
            )
            return traffic_influence_id
    
    def get_traffic_influences(
        self,
        traffic_influence_id: Optional[str] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get Traffic Influence resources with optional filtering"""
        query = {}
        if traffic_influence_id:
            # Query both fields for backward compatibility
            query["$or"] = [
                {"subscriptionId": traffic_influence_id},
                {"trafficInfluenceId": traffic_influence_id}
            ]
        
        cursor = self.traffic_influences.find(query).sort("createdAt", DESCENDING).skip(skip).limit(limit)
        influences = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])  # Convert ObjectId to string
            influences.append(doc)
        
        return influences
    
    def delete_traffic_influence(self, traffic_influence_id: str) -> bool:
        """Delete Traffic Influence from history"""
        # Try subscriptionId first, then trafficInfluenceId for backward compatibility
        result = self.traffic_influences.delete_one({
            "$or": [
                {"subscriptionId": traffic_influence_id},
                {"trafficInfluenceId": traffic_influence_id}
            ]
        })
        return result.deleted_count > 0
    
    def get_traffic_influence_count(self, traffic_influence_id: Optional[str] = None) -> int:
        """Get total count of Traffic Influence resources"""
        query = {}
        if traffic_influence_id:
            query["$or"] = [
                {"subscriptionId": traffic_influence_id},
                {"trafficInfluenceId": traffic_influence_id}
            ]
        return self.traffic_influences.count_documents(query)
    
    def close(self):
        """Close MongoDB connection"""
        self.client.close()


# Global MongoDB client instance
mongo_client: Optional[CamaraMongoClient] = None


def get_mongo_client() -> CamaraMongoClient:
    """Get or create MongoDB client instance"""
    global mongo_client
    if mongo_client is None:
        mongo_client = CamaraMongoClient()
    return mongo_client
