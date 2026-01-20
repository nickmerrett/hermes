"""
Executive Relationship Service

Provides intelligence and insights about executives for sales relationship building.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from sqlalchemy.orm import Session

from app.models.database import Customer
# from app.processors.ai_processor import get_ai_processor  # TODO: Use for AI-powered talking points

logger = logging.getLogger(__name__)


@dataclass
class BackgroundItem:
    """Executive's professional background entry."""
    company: str
    role: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None


@dataclass
class ExecutiveProfile:
    """Executive profile with LinkedIn and Hermes data."""
    executive_id: str
    name: str
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    background: List[BackgroundItem] = field(default_factory=list)
    current_focus: List[str] = field(default_factory=list)
    interests: List[str] = field(default_factory=list)
    recent_posts: List[Dict[str, Any]] = field(default_factory=list)

    def add_background(self, company: str, role: str, start_date: str = None,
                       end_date: str = None, description: str = None):
        """Add a background entry."""
        self.background.append(BackgroundItem(
            company=company,
            role=role,
            start_date=start_date,
            end_date=end_date,
            description=description
        ))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            'executive_id': self.executive_id,
            'name': self.name,
            'title': self.title,
            'company': self.company,
            'location': self.location,
            'linkedin_url': self.linkedin_url,
            'background': [
                {
                    'company': bg.company,
                    'role': bg.role,
                    'start_date': bg.start_date,
                    'end_date': bg.end_date,
                    'description': bg.description
                }
                for bg in self.background
            ],
            'current_focus': self.current_focus,
            'interests': self.interests,
            'recent_posts': self.recent_posts
        }


@dataclass
class ExecutiveActivity:
    """An activity related to an executive."""
    date: datetime
    activity_type: str  # 'post', 'mention', 'article', 'announcement'
    title: str
    content: str
    source: str
    url: Optional[str] = None
    sentiment: Optional[str] = None
    priority_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            'date': self.date.isoformat(),
            'activity_type': self.activity_type,
            'title': self.title,
            'content': self.content,
            'source': self.source,
            'url': self.url,
            'sentiment': self.sentiment,
            'priority_score': self.priority_score
        }


@dataclass
class ConnectionPath:
    """A connection path between user and executive."""
    mutual_connection_name: str
    mutual_connection_title: Optional[str] = None
    mutual_connection_company: Optional[str] = None
    relationship_strength: str = 'weak'  # 'strong', 'medium', 'weak'
    introduction_context: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            'mutual_connection_name': self.mutual_connection_name,
            'mutual_connection_title': self.mutual_connection_title,
            'mutual_connection_company': self.mutual_connection_company,
            'relationship_strength': self.relationship_strength,
            'introduction_context': self.introduction_context
        }


class ExecutiveRelationshipService:
    """
    Service for managing executive relationship intelligence.

    Provides methods to:
    - Fetch executive profiles from LinkedIn
    - Query Hermes intelligence for executive mentions
    - Generate AI-powered talking points
    - Find connection paths
    - Create meeting preparation documents
    """

    def __init__(self, db: Session):
        self.db = db
        self.logger = logging.getLogger(__name__)

    async def get_executive_profile(
        self,
        executive_id: str,
        customer_id: Optional[int] = None
    ) -> Optional[ExecutiveProfile]:
        """
        Get executive profile combining LinkedIn and Hermes data.

        Args:
            executive_id: Unique identifier for the executive (e.g., linkedin-url-slug)
            customer_id: Optional customer context for filtering intelligence

        Returns:
            ExecutiveProfile or None if not found
        """
        # TODO: Implement LinkedIn API/scraping to fetch profile
        # For now, return a sample profile for testing

        self.logger.info(f"Fetching profile for executive: {executive_id}")

        # Sample data for development
        profile = ExecutiveProfile(
            executive_id=executive_id,
            name="Jane Smith",
            title="Chief Financial Officer",
            company="Acme Corp",
            location="San Francisco, CA",
            linkedin_url=f"https://linkedin.com/in/{executive_id}",
            current_focus=["Digital Transformation", "Cloud Migration", "Cost Optimization"],
            interests=["AI/ML", "FinTech", "Sustainability"]
        )

        # Add sample background
        profile.add_background(
            company="IBM",
            role="VP of Finance",
            start_date="2018-01-01",
            end_date="2023-12-31",
            description="Led financial transformation initiatives"
        )

        profile.add_background(
            company="Oracle",
            role="Senior Finance Director",
            start_date="2015-06-01",
            end_date="2017-12-31",
            description="Managed enterprise finance operations"
        )

        # TODO: Query Hermes intelligence for mentions of this executive
        # TODO: Add recent posts from LinkedIn

        return profile

    async def get_executive_activity(
        self,
        executive_id: str,
        customer_id: Optional[int] = None,
        days: int = 90
    ) -> List[ExecutiveActivity]:
        """
        Get recent activity timeline for an executive.

        Combines:
        - LinkedIn posts
        - Mentions in Hermes intelligence
        - News articles
        - Company announcements

        Args:
            executive_id: Executive identifier
            customer_id: Optional customer context
            days: Number of days to look back

        Returns:
            List of ExecutiveActivity sorted by date (newest first)
        """
        self.logger.info(f"Fetching activity for executive: {executive_id}, last {days} days")

        activities = []
        # cutoff_date would be used when querying actual data
        # cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Query Hermes intelligence for mentions
        # We'll search for the executive's name in intelligence items
        # TODO: Implement proper executive name extraction/matching

        # For now, return sample activities
        activities.append(ExecutiveActivity(
            date=datetime.utcnow() - timedelta(days=2),
            activity_type='post',
            title='Thoughts on AI in Finance',
            content='Excited to share our latest findings on AI adoption in financial services...',
            source='LinkedIn',
            url='https://linkedin.com/posts/...',
            sentiment='positive',
            priority_score=0.8
        ))

        activities.append(ExecutiveActivity(
            date=datetime.utcnow() - timedelta(days=7),
            activity_type='mention',
            title='Acme Corp Announces Q4 Results',
            content='CFO Jane Smith highlighted strong revenue growth...',
            source='Business Wire',
            url='https://businesswire.com/...',
            sentiment='positive',
            priority_score=0.9
        ))

        # Sort by date, newest first
        activities.sort(key=lambda x: x.date, reverse=True)

        return activities

    async def find_connection_paths(
        self,
        executive_id: str,
        user_linkedin_connections: List[str] = None
    ) -> List[ConnectionPath]:
        """
        Find mutual connections between user and executive.

        Args:
            executive_id: Executive identifier
            user_linkedin_connections: List of user's LinkedIn connection IDs

        Returns:
            List of ConnectionPath objects
        """
        self.logger.info(f"Finding connections for executive: {executive_id}")

        # TODO: Implement LinkedIn connection path finding
        # This requires:
        # 1. User's LinkedIn connections
        # 2. Executive's LinkedIn connections
        # 3. Algorithm to find mutual connections

        # Sample data for development
        connections = [
            ConnectionPath(
                mutual_connection_name="Bob Johnson",
                mutual_connection_title="VP of Sales",
                mutual_connection_company="Tech Solutions Inc",
                relationship_strength="strong",
                introduction_context="Worked together at Oracle 2015-2017"
            )
        ]

        return connections

    async def generate_talking_points(
        self,
        executive_id: str,
        customer_id: int,
        meeting_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate AI-powered talking points for meeting with executive.

        Args:
            executive_id: Executive identifier
            customer_id: Customer context
            meeting_context: Optional context about the meeting

        Returns:
            Dictionary with talking points, ice breakers, and topics
        """
        self.logger.info(f"Generating talking points for executive: {executive_id}")

        # Get executive profile and activity
        profile = await self.get_executive_profile(executive_id, customer_id)
        if not profile:
            return {'error': 'Executive profile not found'}

        # TODO: Use activities in AI-powered talking points generation
        # activities = await self.get_executive_activity(executive_id, customer_id)
        _ = await self.get_executive_activity(executive_id, customer_id)  # Fetch for future use

        # Get customer information
        customer = self.db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return {'error': 'Customer not found'}

        # TODO: Use AI to generate talking points
        # prompt = self._build_talking_points_prompt(
        #     profile=profile,
        #     activities=activities,
        #     customer=customer,
        #     meeting_context=meeting_context
        # )
        # ai_processor = get_ai_processor(self.db)

        try:
            # Generate talking points using AI
            # TODO: Call AI processor with appropriate prompt
            # For now, return sample data

            talking_points = {
                'ice_breakers': [
                    "Congratulations on Acme Corp's recent Q4 results - impressive growth!",
                    "I saw your post about AI in finance - we've been exploring similar initiatives",
                    "Your background at IBM and Oracle gives you unique perspective on digital transformation"
                ],
                'discussion_topics': [
                    {
                        'topic': 'Cloud Migration Strategy',
                        'context': 'Based on their focus on digital transformation and cost optimization',
                        'suggested_approach': 'Share case studies of similar financial services migrations'
                    },
                    {
                        'topic': 'AI/ML in Financial Operations',
                        'context': 'Aligns with their stated interests and recent LinkedIn post',
                        'suggested_approach': 'Discuss practical AI applications that reduce costs'
                    }
                ],
                'competitive_intelligence': [
                    'Acme Corp recently completed Oracle to cloud migration',
                    'CFO publicly mentioned 15% cost reduction target for 2024'
                ],
                'action_items': [
                    'Send case study on financial services cloud migration',
                    'Prepare ROI calculator for their specific use case',
                    'Connect with Bob Johnson (mutual connection) for warm intro'
                ]
            }

            return talking_points

        except Exception as e:
            self.logger.error(f"Error generating talking points: {e}", exc_info=True)
            return {'error': str(e)}

    async def get_meeting_prep(
        self,
        executive_id: str,
        customer_id: int,
        meeting_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get complete meeting preparation document.

        Combines:
        - Executive profile
        - Recent activity
        - Talking points
        - Connection paths
        - Competitive intelligence

        Args:
            executive_id: Executive identifier
            customer_id: Customer context
            meeting_context: Optional meeting context

        Returns:
            Complete meeting prep dictionary
        """
        self.logger.info(f"Preparing meeting prep for executive: {executive_id}")

        # Gather all data
        profile = await self.get_executive_profile(executive_id, customer_id)
        activities = await self.get_executive_activity(executive_id, customer_id)
        connections = await self.find_connection_paths(executive_id)
        talking_points = await self.generate_talking_points(
            executive_id, customer_id, meeting_context
        )

        return {
            'profile': profile.to_dict() if profile else None,
            'recent_activity': [a.to_dict() for a in activities],
            'connection_paths': [c.to_dict() for c in connections],
            'talking_points': talking_points,
            'generated_at': datetime.utcnow().isoformat()
        }

    def _build_talking_points_prompt(
        self,
        profile: ExecutiveProfile,
        activities: List[ExecutiveActivity],
        customer: Customer,
        meeting_context: Optional[str]
    ) -> str:
        """Build AI prompt for generating talking points."""

        prompt = f"""Generate talking points for a sales meeting with the following executive:

Executive Profile:
- Name: {profile.name}
- Title: {profile.title}
- Company: {profile.company}
- Current Focus: {', '.join(profile.current_focus)}
- Interests: {', '.join(profile.interests)}

Recent Activity:
"""

        for activity in activities[:5]:  # Top 5 recent activities
            prompt += f"- [{activity.date.strftime('%Y-%m-%d')}] {activity.title}\n"

        prompt += f"""
Our Company: {customer.name}
Our Keywords: {', '.join(customer.keywords or [])}

Meeting Context: {meeting_context or 'Initial sales conversation'}

Please provide:
1. 3-5 ice breakers based on their recent activity and interests
2. Key discussion topics that align with their focus areas and our capabilities
3. Competitive intelligence insights
4. Suggested action items for follow-up

Focus on building rapport and identifying alignment between their needs and our solutions.
"""

        return prompt
