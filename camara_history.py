"""
CAMARA API History Router
Provides endpoints to query and manage stored QoD and Traffic Influence history
"""

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from mongodb_client import get_mongo_client

router = APIRouter(prefix="/history", tags=["CAMARA History"])


@router.get("/qod")
async def get_qod_history(
    sessionId: Optional[str] = Query(None, description="Filter by session ID"),
    limit: int = Query(100, ge=1, le=1000, description="Max results to return"),
    skip: int = Query(0, ge=0, description="Number of results to skip"),
):
    """
    Get QoD session history from MongoDB
    
    Query Parameters:
    - sessionId: Filter by specific session ID (optional)
    - limit: Maximum number of results (default: 100, max: 1000)
    - skip: Number of results to skip for pagination (default: 0)
    
    Returns: Array of QoD session records with request/response data
    """
    try:
        mongo_client = get_mongo_client()
        sessions = mongo_client.get_qod_sessions(session_id=sessionId, limit=limit, skip=skip)
        total_count = mongo_client.get_qod_session_count(session_id=sessionId)
        
        return {
            "data": sessions,
            "pagination": {
                "total": total_count,
                "limit": limit,
                "skip": skip,
                "returned": len(sessions)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/qod/{sessionId}")
async def delete_qod_history(sessionId: str):
    """
    Delete QoD session from history
    
    Path Parameters:
    - sessionId: Session ID to delete
    
    Returns: 204 No Content on success
    """
    try:
        mongo_client = get_mongo_client()
        deleted = mongo_client.delete_qod_session(sessionId)
        
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Session {sessionId} not found")
        
        return JSONResponse(status_code=204, content=None)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/traffic-influence")
async def get_traffic_influence_history(
    trafficInfluenceId: Optional[str] = Query(None, description="Filter by traffic influence ID"),
    limit: int = Query(100, ge=1, le=1000, description="Max results to return"),
    skip: int = Query(0, ge=0, description="Number of results to skip"),
):
    """
    Get Traffic Influence history from MongoDB
    
    Query Parameters:
    - trafficInfluenceId: Filter by specific traffic influence ID (optional)
    - limit: Maximum number of results (default: 100, max: 1000)
    - skip: Number of results to skip for pagination (default: 0)
    
    Returns: Array of Traffic Influence records with request/response data
    """
    try:
        mongo_client = get_mongo_client()
        influences = mongo_client.get_traffic_influences(
            traffic_influence_id=trafficInfluenceId, 
            limit=limit, 
            skip=skip
        )
        total_count = mongo_client.get_traffic_influence_count(traffic_influence_id=trafficInfluenceId)
        
        return {
            "data": influences,
            "pagination": {
                "total": total_count,
                "limit": limit,
                "skip": skip,
                "returned": len(influences)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/traffic-influence/{trafficInfluenceId}")
async def delete_traffic_influence_history(trafficInfluenceId: str):
    """
    Delete Traffic Influence record from history
    
    Path Parameters:
    - trafficInfluenceId: Traffic Influence ID to delete
    
    Returns: 204 No Content on success
    """
    try:
        mongo_client = get_mongo_client()
        deleted = mongo_client.delete_traffic_influence(trafficInfluenceId)
        
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Traffic Influence {trafficInfluenceId} not found")
        
        return JSONResponse(status_code=204, content=None)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# Stats endpoints
@router.get("/stats")
async def get_history_stats():
    """
    Get statistics about stored history
    
    Returns: Counts of QoD sessions and Traffic Influence resources
    """
    try:
        mongo_client = get_mongo_client()
        
        return {
            "qod_sessions": {
                "total": mongo_client.get_qod_session_count()
            },
            "traffic_influences": {
                "total": mongo_client.get_traffic_influence_count()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
