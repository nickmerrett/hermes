"""
Executive Relationship Service

Provides intelligence and insights about executives for sales relationship building.
"""

import logging
import json
import re
import httpx
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from sqlalchemy import or_
from anthropic import Anthropic
from urllib.parse import quote_plus

from app.models.database import Customer, IntelligenceItem, ProcessedIntelligence, PlatformSettings
from app.config.settings import settings

# Import OpenAI (optional)
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

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
    - Fetch executive profiles from customer configurations
    - Query Hermes intelligence for executive mentions
    - Generate AI-powered talking points
    - Find connection paths (colleagues at same company)
    - Create meeting preparation documents
    """

    def __init__(self, db: Session):
        self.db = db
        self.logger = logging.getLogger(__name__)

    # ── Helper methods ──────────────────────────────────────────────

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Lowercase, strip, replace hyphens/underscores with spaces."""
        return re.sub(r'[-_]+', ' ', name.strip().lower())

    @classmethod
    def _names_match(cls, executive_id: str, candidate_name: str) -> bool:
        """Fuzzy match an executive_id (URL slug) against a candidate name."""
        norm_id = cls._normalize_name(executive_id)
        norm_name = cls._normalize_name(candidate_name)

        # Exact match after normalization
        if norm_id == norm_name:
            return True

        # Substring match (either direction)
        if norm_id in norm_name or norm_name in norm_id:
            return True

        # Dot-stripped match (e.g. "nuno-a-matos" vs "Nuno A. Matos")
        norm_name_no_dots = norm_name.replace('.', '')
        norm_id_no_dots = norm_id.replace('.', '')
        if norm_id_no_dots == norm_name_no_dots:
            return True

        return False

    @classmethod
    def _url_slug_matches(cls, executive_id: str, url: str) -> bool:
        """Extract LinkedIn URL slug and compare to executive_id."""
        if not url:
            return False
        # Extract slug from URLs like https://www.linkedin.com/in/nuno-a-matos/
        match = re.search(r'linkedin\.com/in/([^/?#]+)', url)
        if match:
            slug = match.group(1).rstrip('/')
            return cls._normalize_name(slug) == cls._normalize_name(executive_id)
        return False

    def _find_executive_in_customers(
        self,
        executive_id: str,
        customer_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Search all customers' linkedin_user_profiles configs for a matching executive.

        Returns list of dicts with keys: name, role, linkedin_url, notes, customer_id, customer_name
        """
        if customer_id:
            customers = self.db.query(Customer).filter(Customer.id == customer_id).all()
        else:
            customers = self.db.query(Customer).all()

        matches = []
        for customer in customers:
            config = customer.config or {}
            profiles = config.get('linkedin_user_profiles', [])
            for profile in profiles:
                name = profile.get('name', '')
                profile_url = profile.get('profile_url', '')

                if self._names_match(executive_id, name) or self._url_slug_matches(executive_id, profile_url):
                    matches.append({
                        'name': name,
                        'role': profile.get('role', ''),
                        'linkedin_url': profile_url,
                        'notes': profile.get('notes', ''),
                        'customer_id': customer.id,
                        'customer_name': customer.name,
                    })

        return matches

    def _find_executive_in_linkedin_items(
        self,
        executive_id: str,
        customer_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fallback: search collected LinkedIn intelligence items for an executive
        by matching profile_name in raw_data or the [LinkedIn Post/Profile] title pattern.

        Returns same shape as _find_executive_in_customers.
        """
        display_name = executive_id.replace('-', ' ')

        # Search for LinkedIn items whose title matches the executive name
        # Titles look like: "[LinkedIn Post] Guy Scott: ..." or "[LinkedIn Profile] Guy Scott - CTO"
        title_pattern = f"%LinkedIn%{display_name}%"

        query = self.db.query(
            IntelligenceItem.customer_id,
            IntelligenceItem.title,
            IntelligenceItem.raw_data,
            Customer.name.label('customer_name')
        ).join(
            Customer, Customer.id == IntelligenceItem.customer_id
        ).filter(
            IntelligenceItem.source_type.in_(['linkedin_user', 'linkedin_company', 'linkedin']),
            IntelligenceItem.title.ilike(title_pattern),
        )

        if customer_id:
            query = query.filter(IntelligenceItem.customer_id == customer_id)

        # Just need one hit per customer to extract profile info
        rows = query.order_by(IntelligenceItem.published_date.desc()).limit(20).all()

        matches = []
        seen_customers = set()

        for row in rows:
            cust_id = row.customer_id
            if cust_id in seen_customers:
                continue

            raw = row.raw_data or {}
            name = raw.get('profile_name', '')
            role = raw.get('profile_role', '')

            # Extract name/role from title if raw_data is sparse
            if not name:
                title = row.title or ''
                # "[LinkedIn Post] Guy Scott: some text..."
                m = re.match(r'\[LinkedIn (?:Post|Profile|Activity)\]\s*(.+?)(?::|$)', title)
                if m:
                    extracted = m.group(1).strip()
                    # "[LinkedIn Profile] Guy Scott - CTO"
                    if ' - ' in extracted:
                        parts = extracted.split(' - ', 1)
                        name = parts[0].strip()
                        if not role:
                            role = parts[1].strip()
                    else:
                        name = extracted

            if not name:
                continue

            # Verify the name actually matches the executive_id
            if not self._names_match(executive_id, name):
                continue

            seen_customers.add(cust_id)

            # Try to extract linkedin_url from raw_data or item URL
            linkedin_url = raw.get('profile_url', '')
            if not linkedin_url:
                # Build it from the slug
                linkedin_url = f"https://www.linkedin.com/in/{executive_id}"

            # Try to extract current position from Proxycurl data
            current_pos = raw.get('current_position', {})
            if current_pos and not role:
                role = f"{current_pos.get('title', '')} at {current_pos.get('company', '')}".strip(' at ')

            matches.append({
                'name': name,
                'role': role,
                'linkedin_url': linkedin_url,
                'notes': '',
                'customer_id': cust_id,
                'customer_name': row.customer_name,
            })

        return matches

    async def _discover_linkedin_profile(
        self,
        executive_id: str,
        customer_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Discover an executive's LinkedIn profile by searching:
        1. Proxycurl Person Lookup API (if API key available)
        2. Google search fallback (site:linkedin.com/in "name" "company")

        Returns dict matching the shape from _find_executive_in_customers, or None.
        """
        display_name = executive_id.replace('-', ' ').title()
        name_parts = display_name.split()
        if len(name_parts) < 2:
            return None

        first_name = name_parts[0]
        last_name = ' '.join(name_parts[1:])

        # Get company context if available
        company_name = None
        company_domain = None
        cust_id = customer_id
        if customer_id:
            customer = self.db.query(Customer).filter(Customer.id == customer_id).first()
            if customer:
                company_name = customer.name
                company_domain = customer.domain or (customer.config or {}).get('domain', '')

        # ── Method 1: Proxycurl Person Lookup ──
        if settings.proxycurl_api_key:
            result = await self._proxycurl_lookup(
                first_name, last_name, company_name, company_domain,
                executive_id, cust_id
            )
            if result:
                return result

        # ── Method 2: Google search for LinkedIn URL + public profile scrape ──
        result = await self._google_linkedin_search(
            display_name, company_name, executive_id, cust_id
        )
        if result:
            return result

        return None

    async def _proxycurl_lookup(
        self,
        first_name: str,
        last_name: str,
        company_name: Optional[str],
        company_domain: Optional[str],
        executive_id: str,
        customer_id: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        """Use Proxycurl Person Lookup API to find and fetch a LinkedIn profile."""
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                # Step 1: Resolve name → LinkedIn URL
                params = {
                    'first_name': first_name,
                    'last_name': last_name,
                }
                if company_domain:
                    params['company_domain'] = company_domain
                elif company_name:
                    params['enrich_profile'] = 'skip'
                    params['company_name'] = company_name

                headers = {'Authorization': f'Bearer {settings.proxycurl_api_key}'}

                resp = await client.get(
                    'https://nubela.co/proxycurl/api/linkedin/profile/resolve',
                    params=params,
                    headers=headers,
                )

                if resp.status_code != 200:
                    self.logger.warning(f"Proxycurl lookup returned {resp.status_code}")
                    return None

                linkedin_url = resp.json().get('url')
                if not linkedin_url:
                    return None

                self.logger.info(f"Proxycurl resolved {first_name} {last_name} → {linkedin_url}")

                # Step 2: Fetch full profile
                profile_resp = await client.get(
                    'https://nubela.co/proxycurl/api/v2/linkedin',
                    params={'url': linkedin_url},
                    headers=headers,
                )

                if profile_resp.status_code != 200:
                    # We at least have the URL
                    return self._build_discovery_result(
                        name=f"{first_name} {last_name}",
                        linkedin_url=linkedin_url,
                        executive_id=executive_id,
                        customer_id=customer_id,
                    )

                data = profile_resp.json()
                return self._parse_proxycurl_profile(data, executive_id, customer_id)

        except Exception as e:
            self.logger.warning(f"Proxycurl lookup failed: {e}")
            return None

    def _parse_proxycurl_profile(
        self,
        data: Dict[str, Any],
        executive_id: str,
        customer_id: Optional[int],
    ) -> Dict[str, Any]:
        """Parse a Proxycurl profile response into our standard result dict."""
        name = data.get('full_name') or f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
        headline = data.get('headline', '')
        linkedin_url = data.get('public_identifier')
        if linkedin_url and not linkedin_url.startswith('http'):
            linkedin_url = f"https://www.linkedin.com/in/{linkedin_url}"
        elif not linkedin_url:
            linkedin_url = f"https://www.linkedin.com/in/{executive_id}"

        # Current role from headline or experiences
        role = headline
        company_from_profile = ''
        experiences = data.get('experiences', [])
        if experiences and isinstance(experiences, list):
            current = experiences[0]
            if not role:
                role = current.get('title', '')
            company_from_profile = current.get('company', '')

        # Get customer name for context
        customer_name = company_from_profile
        if customer_id:
            cust = self.db.query(Customer).filter(Customer.id == customer_id).first()
            if cust:
                customer_name = cust.name

        result = self._build_discovery_result(
            name=name,
            role=role,
            linkedin_url=linkedin_url,
            executive_id=executive_id,
            customer_id=customer_id,
            customer_name=customer_name,
        )

        # Store background data for enrichment
        result['_background'] = []
        for exp in (experiences or [])[:5]:
            result['_background'].append({
                'company': exp.get('company', ''),
                'role': exp.get('title', ''),
                'start_date': self._format_proxycurl_date(exp.get('starts_at')),
                'end_date': self._format_proxycurl_date(exp.get('ends_at')),
                'description': exp.get('description', ''),
            })

        result['_summary'] = data.get('summary', '')

        return result

    @staticmethod
    def _format_proxycurl_date(date_obj: Optional[Dict]) -> Optional[str]:
        """Convert Proxycurl date dict {year, month, day} to string."""
        if not date_obj or not isinstance(date_obj, dict):
            return None
        year = date_obj.get('year')
        month = date_obj.get('month', 1)
        if year:
            return f"{year}-{month:02d}-01"
        return None

    async def _google_linkedin_search(
        self,
        display_name: str,
        company_name: Optional[str],
        executive_id: str,
        customer_id: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        """Search Google for a person's LinkedIn profile URL and scrape basic info."""
        try:
            query = f'site:linkedin.com/in "{display_name}"'
            if company_name:
                query += f' "{company_name}"'

            search_url = f"https://www.google.com/search?q={quote_plus(query)}&num=5"

            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9',
                }
            ) as client:
                resp = await client.get(search_url)

                if resp.status_code != 200:
                    self.logger.warning(f"Google search returned {resp.status_code}")
                    return None

                # Extract LinkedIn URLs from Google results
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, 'html.parser')

                linkedin_url = None
                role_from_snippet = ''

                for a_tag in soup.find_all('a', href=True):
                    href = a_tag['href']
                    # Google wraps URLs — extract actual URL
                    m = re.search(r'linkedin\.com/in/([^&"\'/?#]+)', href)
                    if m:
                        slug = m.group(1)
                        linkedin_url = f"https://www.linkedin.com/in/{slug}"
                        # Try to get title/role from the snippet text
                        parent = a_tag.find_parent(['div', 'li'])
                        if parent:
                            snippet_text = parent.get_text(' ', strip=True)
                            # Common patterns: "Name - Title - Company | LinkedIn"
                            role_match = re.search(
                                rf'{re.escape(display_name)}\s*[-–]\s*(.+?)(?:\s*[-–|]|\s*LinkedIn)',
                                snippet_text, re.IGNORECASE
                            )
                            if role_match:
                                role_from_snippet = role_match.group(1).strip()
                        break

                if not linkedin_url:
                    self.logger.info(f"No LinkedIn URL found via Google for: {display_name}")
                    return None

                self.logger.info(f"Google found LinkedIn profile: {linkedin_url}")

                # Try to scrape basic info from the public profile
                role = role_from_snippet
                if not role:
                    role = await self._scrape_public_linkedin_headline(client, linkedin_url)

                return self._build_discovery_result(
                    name=display_name,
                    role=role,
                    linkedin_url=linkedin_url,
                    executive_id=executive_id,
                    customer_id=customer_id,
                )

        except Exception as e:
            self.logger.warning(f"Google LinkedIn search failed: {e}")
            return None

    async def _scrape_public_linkedin_headline(
        self, client: httpx.AsyncClient, linkedin_url: str
    ) -> str:
        """Try to extract headline from public LinkedIn profile page."""
        try:
            resp = await client.get(linkedin_url)
            if resp.status_code != 200:
                return ''

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'html.parser')

            # Public profile headline is in meta description or specific tags
            meta_desc = soup.find('meta', {'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                # Format: "Name - Title - Company · Experience: ..."
                content = meta_desc['content']
                parts = content.split(' · ')[0]  # Before the bullet
                # Remove the name prefix
                dash_parts = parts.split(' - ')
                if len(dash_parts) >= 2:
                    return ' - '.join(dash_parts[1:]).strip()

            return ''
        except Exception:
            return ''

    def _build_discovery_result(
        self,
        name: str,
        executive_id: str,
        linkedin_url: str = '',
        role: str = '',
        customer_id: Optional[int] = None,
        customer_name: str = '',
    ) -> Dict[str, Any]:
        """Build a standard result dict from discovered profile data."""
        if not customer_name and customer_id:
            cust = self.db.query(Customer).filter(Customer.id == customer_id).first()
            customer_name = cust.name if cust else ''

        return {
            'name': name,
            'role': role,
            'linkedin_url': linkedin_url,
            'notes': 'Discovered via LinkedIn search',
            'customer_id': customer_id,
            'customer_name': customer_name,
            '_discovered': True,  # Flag so caller knows this is newly discovered
        }

    @staticmethod
    def _map_source_to_activity_type(source_type: str) -> str:
        """Map source_type to an activity_type for the frontend."""
        mapping = {
            'linkedin_user': 'post',
            'linkedin_company': 'post',
            'news_api': 'article',
            'rss': 'article',
            'google_news': 'article',
            'australian_news': 'article',
            'reddit': 'mention',
            'web_scrape': 'article',
            'asx_announce': 'announcement',
            'stock': 'announcement',
        }
        return mapping.get(source_type, 'mention')

    def _get_recent_linkedin_posts(
        self,
        name: str,
        customer_id: int,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get recent LinkedIn posts by this executive."""
        title_pattern = f"%LinkedIn Post%{name}%"
        items = self.db.query(IntelligenceItem).filter(
            IntelligenceItem.customer_id == customer_id,
            IntelligenceItem.source_type.in_(['linkedin_user', 'linkedin']),
            IntelligenceItem.title.ilike(title_pattern),
        ).order_by(
            IntelligenceItem.published_date.desc()
        ).limit(limit).all()

        posts = []
        for item in items:
            # Strip the "[LinkedIn Post] Name: " prefix from title
            title = re.sub(r'^\[LinkedIn (?:Post|Activity)\]\s*[^:]+:\s*', '', item.title)
            posts.append({
                'date': item.published_date.isoformat() if item.published_date else None,
                'title': title[:150],
                'content': (item.content or '')[:300],
                'url': item.url,
            })
        return posts

    def _extract_recent_topics(
        self,
        name: str,
        customer_id: Optional[int],
        days: int = 90
    ) -> List[str]:
        """Query ProcessedIntelligence tags from items mentioning the person."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        name_pattern = f"%{name}%"

        query = self.db.query(ProcessedIntelligence.tags).join(
            IntelligenceItem,
            IntelligenceItem.id == ProcessedIntelligence.item_id
        ).filter(
            IntelligenceItem.published_date >= cutoff,
            or_(
                IntelligenceItem.title.ilike(name_pattern),
                IntelligenceItem.content.ilike(name_pattern),
            )
        )

        if customer_id:
            query = query.filter(IntelligenceItem.customer_id == customer_id)

        rows = query.limit(100).all()

        # Count tag frequency
        tag_counts: Dict[str, int] = {}
        for (tags,) in rows:
            if tags and isinstance(tags, list):
                for tag in tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # Return top tags sorted by frequency
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
        return [tag for tag, _ in sorted_tags[:8]]

    def _create_ai_client(self) -> Tuple[Any, str, str]:
        """
        Initialize AI client using premium model settings.

        Returns (client, client_type, model_name) or raises ValueError.
        """
        provider = settings.ai_provider
        model = settings.ai_model

        # Check for UI model override
        if settings.model_override_in_ui:
            ai_config = self.db.query(PlatformSettings).filter(
                PlatformSettings.key == 'ai_config'
            ).first()
            if ai_config and isinstance(ai_config.value, dict):
                model = ai_config.value.get('model', model)

        if provider == 'anthropic':
            if not settings.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY not configured")
            client = Anthropic(
                api_key=settings.anthropic_api_key,
                base_url=settings.anthropic_api_base_url
            )
            return client, 'anthropic', model

        elif provider == 'openai':
            if not OPENAI_AVAILABLE:
                raise ValueError("OpenAI package not installed")
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY not configured")
            client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url
            )
            return client, 'openai', model

        else:
            raise ValueError(f"Unknown AI provider: {provider}")

    @staticmethod
    def _parse_talking_points_response(response_text: str) -> Dict[str, Any]:
        """Strip markdown fences and parse JSON from AI response."""
        text = response_text.strip()
        # Strip markdown code fences
        if text.startswith('```'):
            # Remove opening fence (with optional language tag)
            text = re.sub(r'^```\w*\n?', '', text)
            text = re.sub(r'\n?```$', '', text)
            text = text.strip()

        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse AI talking points as JSON, returning raw text")
            return {
                'ice_breakers': [response_text[:500]],
                'discussion_topics': [],
                'competitive_intelligence': [],
                'action_items': [],
            }

        # Ensure all expected keys exist
        for key in ('ice_breakers', 'discussion_topics', 'competitive_intelligence', 'action_items'):
            if key not in result:
                result[key] = []

        return result

    # ── Main methods ────────────────────────────────────────────────

    async def get_executive_profile(
        self,
        executive_id: str,
        customer_id: Optional[int] = None
    ) -> Optional[ExecutiveProfile]:
        """
        Get executive profile from customer configs and Hermes intelligence.

        Args:
            executive_id: Unique identifier for the executive (e.g., linkedin-url-slug)
            customer_id: Optional customer context for filtering intelligence

        Returns:
            ExecutiveProfile or None if not found
        """
        self.logger.info(f"Fetching profile for executive: {executive_id}")

        # Primary: search customer config linkedin_user_profiles
        matches = self._find_executive_in_customers(executive_id, customer_id)

        # Fallback: mine collected LinkedIn intelligence items
        if not matches:
            matches = self._find_executive_in_linkedin_items(executive_id, customer_id)

        if matches:
            # Use first match as primary
            primary = matches[0]
            profile = ExecutiveProfile(
                executive_id=executive_id,
                name=primary['name'],
                title=primary['role'],
                company=primary['customer_name'],
                linkedin_url=primary['linkedin_url'],
                current_focus=self._extract_recent_topics(
                    primary['name'],
                    primary['customer_id'],
                ),
            )

            # Enrich with recent LinkedIn posts
            profile.recent_posts = self._get_recent_linkedin_posts(
                primary['name'], primary['customer_id']
            )
        else:
            # No match — return minimal profile using slug as display name
            display_name = executive_id.replace('-', ' ').title()
            profile = ExecutiveProfile(
                executive_id=executive_id,
                name=display_name,
                linkedin_url=f"https://linkedin.com/in/{executive_id}",
            )

        return profile

    async def get_executive_activity(
        self,
        executive_id: str,
        customer_id: Optional[int] = None,
        days: int = 90
    ) -> List[ExecutiveActivity]:
        """
        Get recent activity timeline for an executive from Hermes intelligence.

        Args:
            executive_id: Executive identifier
            customer_id: Optional customer context
            days: Number of days to look back

        Returns:
            List of ExecutiveActivity sorted by date (newest first)
        """
        self.logger.info(f"Fetching activity for executive: {executive_id}, last {days} days")

        # Resolve executive name (config first, then LinkedIn items fallback)
        matches = self._find_executive_in_customers(executive_id, customer_id)
        if not matches:
            matches = self._find_executive_in_linkedin_items(executive_id, customer_id)

        if not matches:
            return []

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Collect activities from all matched customer contexts
        seen_urls = set()
        seen_titles = set()
        activities = []

        for match in matches:
            name = match['name']
            cust_id = match['customer_id']
            name_pattern = f"%{name}%"

            items = self.db.query(IntelligenceItem).outerjoin(
                ProcessedIntelligence,
                IntelligenceItem.id == ProcessedIntelligence.item_id
            ).filter(
                IntelligenceItem.customer_id == cust_id,
                IntelligenceItem.published_date >= cutoff_date,
                or_(
                    IntelligenceItem.title.ilike(name_pattern),
                    IntelligenceItem.content.ilike(name_pattern),
                )
            ).order_by(
                IntelligenceItem.published_date.desc()
            ).limit(50).all()

            for item in items:
                # Deduplicate by URL and title
                if item.url and item.url in seen_urls:
                    continue
                title_key = item.title.strip().lower()
                if title_key in seen_titles:
                    continue
                if item.url:
                    seen_urls.add(item.url)
                seen_titles.add(title_key)

                summary = item.title
                sentiment = None
                priority_score = None
                if item.processed:
                    summary = item.processed.summary or item.title
                    sentiment = item.processed.sentiment
                    priority_score = item.processed.priority_score

                activities.append(ExecutiveActivity(
                    date=item.published_date or item.collected_date,
                    activity_type=self._map_source_to_activity_type(item.source_type),
                    title=item.title,
                    content=summary,
                    source=item.source_type,
                    url=item.url,
                    sentiment=sentiment,
                    priority_score=priority_score,
                ))

        # Sort by date, newest first, limit to 50
        activities.sort(key=lambda x: x.date, reverse=True)
        return activities[:50]

    async def find_connection_paths(
        self,
        executive_id: str,
        user_linkedin_connections: List[str] = None
    ) -> List[ConnectionPath]:
        """
        Find colleagues — other executives configured on the same customer(s).

        Args:
            executive_id: Executive identifier
            user_linkedin_connections: Not used (no LinkedIn API available)

        Returns:
            List of ConnectionPath objects
        """
        self.logger.info(f"Finding connections for executive: {executive_id}")

        matches = self._find_executive_in_customers(executive_id)
        if not matches:
            matches = self._find_executive_in_linkedin_items(executive_id)
        if not matches:
            return []

        connections = []
        seen_names = set()
        primary_name = matches[0]['name'].lower()

        for match in matches:
            # Get all other executives at the same company
            customer = self.db.query(Customer).filter(Customer.id == match['customer_id']).first()
            if not customer:
                continue

            config = customer.config or {}
            profiles = config.get('linkedin_user_profiles', [])

            for profile in profiles:
                colleague_name = profile.get('name', '')
                if not colleague_name or colleague_name.lower() == primary_name:
                    continue
                if colleague_name.lower() in seen_names:
                    continue
                seen_names.add(colleague_name.lower())

                connections.append(ConnectionPath(
                    mutual_connection_name=colleague_name,
                    mutual_connection_title=profile.get('role', ''),
                    mutual_connection_company=match['customer_name'],
                    relationship_strength='medium',
                    introduction_context=f"Colleague at {match['customer_name']}",
                ))

        return connections[:10]

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

        # Get real executive profile and activity
        profile = await self.get_executive_profile(executive_id, customer_id)
        if not profile:
            return {'error': 'Executive profile not found'}

        activities = await self.get_executive_activity(executive_id, customer_id, days=30)

        # Get customer information
        customer = self.db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return {'error': 'Customer not found'}

        # Get recent high-priority customer intelligence (last 30 days)
        cutoff = datetime.utcnow() - timedelta(days=30)
        recent_intel = self.db.query(IntelligenceItem).outerjoin(
            ProcessedIntelligence,
            IntelligenceItem.id == ProcessedIntelligence.item_id
        ).filter(
            IntelligenceItem.customer_id == customer_id,
            IntelligenceItem.published_date >= cutoff,
        ).order_by(
            ProcessedIntelligence.priority_score.desc().nullslast(),
            IntelligenceItem.published_date.desc()
        ).limit(10).all()

        try:
            client, client_type, model = self._create_ai_client()
        except ValueError as e:
            self.logger.warning(f"AI client not available: {e}")
            return {'error': f'AI not available: {e}'}

        # Build prompt with real data
        prompt = self._build_talking_points_prompt(
            profile=profile,
            activities=activities,
            customer=customer,
            meeting_context=meeting_context,
            recent_intel=recent_intel,
        )

        try:
            if client_type == 'anthropic':
                response = client.messages.create(
                    model=model,
                    max_tokens=1200,
                    messages=[{"role": "user", "content": prompt}]
                )
                response_text = response.content[0].text
            elif client_type == 'openai':
                response = client.chat.completions.create(
                    model=model,
                    max_tokens=1200,
                    messages=[{"role": "user", "content": prompt}]
                )
                response_text = response.choices[0].message.content
            else:
                return {'error': f'Unknown client type: {client_type}'}

            return self._parse_talking_points_response(response_text)

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
        meeting_context: Optional[str],
        recent_intel: Optional[List[IntelligenceItem]] = None,
    ) -> str:
        """Build AI prompt for generating talking points."""

        focus_str = ', '.join(profile.current_focus) if profile.current_focus else 'Not available'
        interests_str = ', '.join(profile.interests) if profile.interests else 'Not available'
        keywords_str = ', '.join(customer.keywords or []) if customer.keywords else 'Not available'

        prompt = f"""Generate talking points for a sales meeting with the following executive.

Executive Profile:
- Name: {profile.name}
- Title: {profile.title or 'Unknown'}
- Company: {profile.company or 'Unknown'}
- Current Focus Topics: {focus_str}
- Interests: {interests_str}

Recent Activity ({len(activities)} items):
"""

        if activities:
            for activity in activities[:5]:
                prompt += f"- [{activity.date.strftime('%Y-%m-%d')}] ({activity.activity_type}) {activity.title}\n"
                if activity.content and activity.content != activity.title:
                    prompt += f"  Summary: {activity.content[:200]}\n"
        else:
            prompt += "- No recent activity found in our intelligence system\n"

        prompt += f"""
Customer: {customer.name}
Customer Keywords: {keywords_str}
"""

        # Add recent intelligence about the customer
        if recent_intel:
            prompt += "\nRecent Customer Intelligence:\n"
            for idx, item in enumerate(recent_intel[:10], 1):
                summary = item.title
                if item.processed and item.processed.summary:
                    summary = item.processed.summary
                prompt += f"{idx}. {summary[:200]}\n"

        prompt += f"""
Meeting Context: {meeting_context or 'Initial sales conversation'}

Respond with a JSON object containing exactly these keys:
- "ice_breakers": array of 3-5 conversation starters based on their recent activity and interests
- "discussion_topics": array of objects with "topic", "context", and "suggested_approach" keys
- "competitive_intelligence": array of strategic insights about the company
- "action_items": array of suggested follow-up actions

Focus on building rapport and identifying alignment between their needs and our solutions.
Return ONLY valid JSON, no markdown fences or extra text.
"""

        return prompt
