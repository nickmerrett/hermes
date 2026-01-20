"""
Executive Relationship API Endpoints

Provides API endpoints for executive relationship intelligence and meeting preparation.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.executive_relationship import ExecutiveRelationshipService

router = APIRouter(prefix="/executives", tags=["executives"])
logger = logging.getLogger(__name__)


@router.get("/{executive_id}/profile")
async def get_executive_profile(
    executive_id: str,
    customer_id: Optional[int] = Query(None, description="Customer context for filtering intelligence"),
    db: Session = Depends(get_db)
):
    """
    Get executive profile with LinkedIn and Hermes intelligence data.

    Args:
        executive_id: Executive identifier (e.g., linkedin-url-slug or email)
        customer_id: Optional customer ID for context

    Returns:
        ExecutiveProfile with background, interests, and recent activity
    """
    try:
        service = ExecutiveRelationshipService(db)
        profile = await service.get_executive_profile(executive_id, customer_id)

        if not profile:
            raise HTTPException(status_code=404, detail="Executive profile not found")

        return profile.to_dict()

    except Exception as e:
        logger.error(f"Error fetching executive profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch executive profile: {str(e)}")


@router.get("/{executive_id}/activity")
async def get_executive_activity(
    executive_id: str,
    customer_id: Optional[int] = Query(None, description="Customer context"),
    days: int = Query(90, ge=1, le=365, description="Number of days to look back"),
    db: Session = Depends(get_db)
):
    """
    Get recent activity timeline for an executive.

    Includes:
    - LinkedIn posts
    - Mentions in intelligence items
    - News articles
    - Company announcements

    Args:
        executive_id: Executive identifier
        customer_id: Optional customer context
        days: Number of days to look back (default 90)

    Returns:
        List of activities sorted by date (newest first)
    """
    try:
        service = ExecutiveRelationshipService(db)
        activities = await service.get_executive_activity(executive_id, customer_id, days)

        return {
            'executive_id': executive_id,
            'activities': [activity.to_dict() for activity in activities],
            'total_count': len(activities),
            'days_queried': days
        }

    except Exception as e:
        logger.error(f"Error fetching executive activity: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch activity: {str(e)}")


@router.get("/{executive_id}/connections")
async def get_connection_paths(
    executive_id: str,
    user_linkedin_id: Optional[str] = Query(None, description="User's LinkedIn ID for finding mutual connections"),
    db: Session = Depends(get_db)
):
    """
    Find connection paths between user and executive.

    Returns mutual connections and introduction opportunities.

    Args:
        executive_id: Executive identifier
        user_linkedin_id: Optional user's LinkedIn ID

    Returns:
        List of connection paths with relationship strength
    """
    try:
        service = ExecutiveRelationshipService(db)

        # TODO: Fetch user's LinkedIn connections if user_linkedin_id provided
        user_connections = []

        connections = await service.find_connection_paths(executive_id, user_connections)

        return {
            'executive_id': executive_id,
            'connection_paths': [conn.to_dict() for conn in connections],
            'total_paths': len(connections)
        }

    except Exception as e:
        logger.error(f"Error finding connections: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to find connections: {str(e)}")


@router.post("/{executive_id}/talking-points")
async def generate_talking_points(
    executive_id: str,
    customer_id: int,
    meeting_context: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Generate AI-powered talking points for meeting with executive.

    Args:
        executive_id: Executive identifier
        customer_id: Customer context (required)
        meeting_context: Optional context about the meeting

    Returns:
        Talking points, ice breakers, discussion topics, and action items
    """
    try:
        service = ExecutiveRelationshipService(db)
        talking_points = await service.generate_talking_points(
            executive_id, customer_id, meeting_context
        )

        if 'error' in talking_points:
            raise HTTPException(status_code=400, detail=talking_points['error'])

        return {
            'executive_id': executive_id,
            'customer_id': customer_id,
            **talking_points
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating talking points: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate talking points: {str(e)}")


@router.get("/{executive_id}/meeting-prep")
async def get_meeting_prep(
    executive_id: str,
    customer_id: int,
    meeting_context: Optional[str] = Query(None, description="Context about the meeting"),
    db: Session = Depends(get_db)
):
    """
    Get complete meeting preparation document.

    Combines:
    - Executive profile
    - Recent activity timeline
    - Connection paths
    - AI-generated talking points
    - Competitive intelligence

    Args:
        executive_id: Executive identifier
        customer_id: Customer context (required)
        meeting_context: Optional meeting context

    Returns:
        Complete meeting prep document
    """
    try:
        service = ExecutiveRelationshipService(db)
        meeting_prep = await service.get_meeting_prep(
            executive_id, customer_id, meeting_context
        )

        return {
            'executive_id': executive_id,
            'customer_id': customer_id,
            **meeting_prep
        }

    except Exception as e:
        logger.error(f"Error generating meeting prep: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate meeting prep: {str(e)}")


@router.get("/search")
async def search_executives(
    query: str = Query(..., description="Search query (name, company, title)"),
    limit: int = Query(10, ge=1, le=100, description="Maximum results to return"),
    db: Session = Depends(get_db)
):
    """
    Search for executives by name, company, or title.

    Args:
        query: Search query string
        limit: Maximum number of results

    Returns:
        List of matching executive profiles
    """
    try:
        # TODO: Implement executive search
        # This could search:
        # 1. Local database of executives
        # 2. LinkedIn API
        # 3. Intelligence items for executive mentions

        logger.info(f"Searching for executives: {query}")

        return {
            'query': query,
            'results': [],
            'total': 0,
            'message': 'Search not yet implemented'
        }

    except Exception as e:
        logger.error(f"Error searching executives: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
