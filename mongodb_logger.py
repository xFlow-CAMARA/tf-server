"""
MongoDB Logging Middleware for CAMARA APIs

Logs all API requests and responses to MongoDB for analytics and monitoring.
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from pymongo import MongoClient
from datetime import datetime
import time
import os


class MongoDBLoggerMiddleware(BaseHTTPMiddleware):
    """Middleware to log API requests to MongoDB"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        
        # Initialize MongoDB connection
        mongo_uri = os.getenv("MONGODB_URI", "mongodb://mongodb:27017")
        mongo_db = os.getenv("MONGODB_DB", "camara")
        
        try:
            self.client = MongoClient(mongo_uri)
            self.db = self.client[mongo_db]
            self.logs_collection = self.db.api_usage_logs
            self.metrics_collection = self.db.api_metrics_hourly
            print(f"✓ MongoDB logger connected to {mongo_uri}/{mongo_db}")
        except Exception as e:
            print(f"✗ MongoDB logger failed to connect: {e}")
            self.client = None
    
    async def dispatch(self, request: Request, call_next):
        """Log request and response"""
        
        # Skip health checks and static files
        if request.url.path in ["/", "/health", "/docs", "/openapi.json"]:
            return await call_next(request)
        
        # Record start time
        start_time = time.time()
        timestamp = datetime.utcnow()
        
        # Process request
        response = await call_next(request)
        
        # Calculate latency
        latency_ms = round((time.time() - start_time) * 1000, 2)
        
        # Extract API details
        api_name = self._extract_api_name(request.url.path)
        
        # Log to MongoDB if connected
        if self.client:
            try:
                # Log individual request
                log_entry = {
                    "timestamp": timestamp,
                    "api_name": api_name,
                    "method": request.method,
                    "endpoint": request.url.path,
                    "query_params": dict(request.query_params),
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                    "client_ip": request.client.host if request.client else None,
                    "user_agent": request.headers.get("user-agent"),
                }
                
                self.logs_collection.insert_one(log_entry)
                
                # Update hourly metrics
                hour = timestamp.replace(minute=0, second=0, microsecond=0)
                self._update_hourly_metrics(api_name, hour, latency_ms, response.status_code)
                
            except Exception as e:
                print(f"MongoDB logging error: {e}")
        
        return response
    
    def _extract_api_name(self, path: str) -> str:
        """Extract API name from path"""
        if "/quality-on-demand" in path or "/qos-profiles" in path:
            return "QoD"
        elif "/location-retrieval" in path or "/device-location" in path or "/retrieve" in path:
            return "Device Location"
        elif "/traffic-influence" in path:
            return "Traffic Influence"
        elif "/number-verification" in path or "/verify" in path:
            return "Number Verification"
        elif "/device-status" in path or "/connectivity" in path or "/roaming" in path:
            return "Device Status"
        elif "/sim-swap" in path or "/check" in path:
            return "SIM Swap"
        else:
            return "Other"
    
    def _update_hourly_metrics(self, api_name: str, hour: datetime, latency_ms: float, status_code: int):
        """Update or insert hourly aggregated metrics"""
        try:
            # Check if hourly record exists
            result = self.metrics_collection.find_one({
                "api_name": api_name,
                "hour": hour
            })
            
            if result:
                # Update existing record
                self.metrics_collection.update_one(
                    {"_id": result["_id"]},
                    {
                        "$inc": {
                            "request_count": 1,
                            "error_count": 1 if status_code >= 400 else 0,
                            "total_latency_ms": latency_ms
                        },
                        "$set": {
                            "avg_latency_ms": (result["total_latency_ms"] + latency_ms) / (result["request_count"] + 1),
                            "max_latency_ms": max(result.get("max_latency_ms", 0), latency_ms),
                            "min_latency_ms": min(result.get("min_latency_ms", float('inf')), latency_ms)
                        }
                    }
                )
            else:
                # Create new hourly record
                self.metrics_collection.insert_one({
                    "api_name": api_name,
                    "hour": hour,
                    "request_count": 1,
                    "error_count": 1 if status_code >= 400 else 0,
                    "total_latency_ms": latency_ms,
                    "avg_latency_ms": latency_ms,
                    "max_latency_ms": latency_ms,
                    "min_latency_ms": latency_ms,
                    "created_at": datetime.utcnow()
                })
        except Exception as e:
            print(f"Error updating hourly metrics: {e}")
