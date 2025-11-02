"""LinkedIn collector for company updates and job postings"""

from typing import List, Dict, Any
from datetime import datetime
import httpx
import feedparser
from bs4 import BeautifulSoup

from app.collectors.base import RateLimitedCollector, BaseCollector
from app.models.schemas import IntelligenceItemCreate
from app.config.settings import settings


class LinkedInCollector(RateLimitedCollector):
    """
    Collector for LinkedIn company information

    Methods:
    1. LinkedIn RSS feeds (public, no auth needed)
    2. Public company page scraping (respectful, rate-limited)

    Note: This is a basic implementation using public data.
    For production, consider using LinkedIn's official API with proper authentication.
    """

    def __init__(self, customer_config: Dict[str, Any]):
        super().__init__(customer_config, rate_limit=20)  # Conservative rate limit

        self.company_id = customer_config.get('config', {}).get('linkedin_company_id')
        self.company_url = customer_config.get('config', {}).get('linkedin_company_url')

        # User agent for respectful scraping
        self.headers = {
            'User-Agent': 'CustomerIntelligenceTool/1.0 (Intelligence Aggregator)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }

    def get_source_type(self) -> str:
        return "linkedin"

    async def collect(self) -> List[IntelligenceItemCreate]:
        """
        Collect LinkedIn company information

        Returns:
            List of IntelligenceItemCreate objects
        """
        items = []

        try:
            # Method 1: RSS feed (if company ID is available)
            if self.company_id:
                rss_items = await self._collect_from_rss()
                items.extend(rss_items)

            # Method 2: Job postings (can be accessed publicly)
            if self.company_url or self.company_id:
                job_items = await self._collect_job_postings()
                items.extend(job_items)

            self.logger.info(f"Collected {len(items)} items from LinkedIn")

        except Exception as e:
            self.logger.error(f"Error collecting from LinkedIn: {e}")
            raise

        return items

    async def _collect_from_rss(self) -> List[IntelligenceItemCreate]:
        """
        Collect from LinkedIn company RSS feed

        Note: LinkedIn RSS feeds may not be publicly available for all companies
        """
        items = []

        try:
            # LinkedIn RSS feed URL format (may require authentication)
            # This is a placeholder - actual RSS access may be limited
            rss_url = f"https://www.linkedin.com/company/{self.company_id}/posts/?feedView=articles"

            async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
                response = await client.get(rss_url)

                if response.status_code == 200:
                    feed = feedparser.parse(response.text)

                    for entry in feed.entries[:10]:  # Limit entries
                        item = self._process_rss_entry(entry)
                        if item:
                            items.append(item)

        except Exception as e:
            self.logger.warning(f"Could not access LinkedIn RSS feed: {e}")

        return items

    async def _collect_job_postings(self) -> List[IntelligenceItemCreate]:
        """
        Collect recent job postings from LinkedIn

        This indicates company growth and hiring trends
        """
        items = []

        if not self.company_id and not self.company_url:
            return items

        try:
            # LinkedIn allows public access to job listings
            # This is valuable intelligence about company growth
            company_identifier = self.company_id or self._extract_company_id(self.company_url)

            if not company_identifier:
                return items

            # LinkedIn public jobs URL (doesn't require authentication)
            jobs_url = f"https://www.linkedin.com/jobs/search/?f_C={company_identifier}"

            async with httpx.AsyncClient(
                headers=self.headers,
                timeout=30.0,
                follow_redirects=True
            ) as client:
                if not self._check_rate_limit():
                    return items

                response = await client.get(jobs_url)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # This is a simplified parser - LinkedIn's HTML structure may change
                    # For production, use their official API
                    job_cards = soup.find_all('div', class_='base-card')[:5]

                    for card in job_cards:
                        try:
                            title_elem = card.find('h3', class_='base-search-card__title')
                            if not title_elem:
                                continue

                            job_title = title_elem.get_text(strip=True)

                            # Create intelligence item about hiring
                            item = self._create_item(
                                title=f"[LinkedIn Jobs] {self.customer_name} hiring: {job_title}",
                                content=f"New job posting indicates growth in this area.",
                                url=jobs_url,
                                published_date=datetime.now(),
                                raw_data={
                                    'job_title': job_title,
                                    'company_id': company_identifier,
                                    'source': 'linkedin_jobs'
                                }
                            )
                            items.append(item)

                        except Exception as e:
                            self.logger.debug(f"Error parsing job card: {e}")
                            continue

        except Exception as e:
            self.logger.warning(f"Could not collect LinkedIn job postings: {e}")

        return items

    def _process_rss_entry(self, entry: Any) -> IntelligenceItemCreate | None:
        """Process an RSS feed entry"""
        try:
            title = entry.get('title', 'Untitled')
            content = entry.get('summary', '') or entry.get('description', '')
            url = entry.get('link')

            published_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_date = datetime(*entry.published_parsed[:6])

            return self._create_item(
                title=f"[LinkedIn] {title}",
                content=content,
                url=url,
                published_date=published_date,
                raw_data={
                    'company_id': self.company_id,
                    'source': 'linkedin_rss'
                }
            )

        except Exception as e:
            self.logger.error(f"Error processing LinkedIn RSS entry: {e}")
            return None

    def _extract_company_id(self, url: str) -> str | None:
        """Extract company ID from LinkedIn URL"""
        try:
            # LinkedIn company URLs typically: https://www.linkedin.com/company/{id}/
            parts = url.rstrip('/').split('/')
            if 'company' in parts:
                idx = parts.index('company')
                if idx + 1 < len(parts):
                    return parts[idx + 1]
        except Exception:
            pass
        return None


class LinkedInUserCollector(RateLimitedCollector):
    """
    Collector for monitoring individual LinkedIn user profiles

    Tracks:
    1. Profile changes (job title, company, location)
    2. User posts and articles
    3. Career moves and promotions
    4. Activity and engagement patterns

    Methods:
    - Proxycurl API (paid, reliable) - primary
    - Public profile scraping (best effort, rate-limited) - fallback
    """

    def __init__(self, customer_config: Dict[str, Any]):
        super().__init__(customer_config, rate_limit=10)  # Very conservative for user profiles

        self.user_profiles = customer_config.get('config', {}).get('linkedin_user_profiles', [])
        self.api_key = settings.proxycurl_api_key

        # User agent for respectful scraping
        self.headers = {
            'User-Agent': 'CustomerIntelligenceTool/1.0 (Intelligence Aggregator)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }

    def get_source_type(self) -> str:
        return "linkedin_user"

    async def collect(self) -> List[IntelligenceItemCreate]:
        """
        Collect intelligence from LinkedIn user profiles

        Returns:
            List of IntelligenceItemCreate objects
        """
        items = []

        if not self.user_profiles:
            self.logger.info("No LinkedIn user profiles configured")
            return items

        for profile_config in self.user_profiles:
            try:
                # Get profile URL and metadata
                profile_url = profile_config.get('profile_url')
                profile_name = profile_config.get('name', 'Unknown')
                profile_role = profile_config.get('role', '')

                if not profile_url:
                    self.logger.warning(f"No profile_url for {profile_name}")
                    continue

                self.logger.info(f"Collecting data for LinkedIn profile: {profile_name}")

                # Method 1: Try Proxycurl API first (if available)
                if self.api_key:
                    profile_items = await self._collect_via_proxycurl(
                        profile_url, profile_name, profile_role
                    )
                    items.extend(profile_items)

                    # Also collect recent posts/activity
                    post_items = await self._collect_posts_via_proxycurl(
                        profile_url, profile_name, profile_role
                    )
                    items.extend(post_items)
                else:
                    # Method 2: Fallback to public profile scraping
                    profile_items = await self._collect_via_scraping(
                        profile_url, profile_name, profile_role
                    )
                    items.extend(profile_items)

                    # Try to collect posts via scraping
                    post_items = await self._collect_posts_via_scraping(
                        profile_url, profile_name, profile_role
                    )
                    items.extend(post_items)

            except Exception as e:
                self.logger.error(f"Error collecting profile {profile_config.get('name')}: {e}")
                continue

        self.logger.info(f"Collected {len(items)} items from LinkedIn user profiles")
        return items

    async def _collect_via_proxycurl(
        self,
        profile_url: str,
        profile_name: str,
        profile_role: str
    ) -> List[IntelligenceItemCreate]:
        """
        Collect profile data using Proxycurl API

        Proxycurl provides:
        - Profile data (current position, company, location)
        - Activity feed (posts, articles, comments)
        - Experience history (job changes)

        API Docs: https://nubela.co/proxycurl/docs
        """
        items = []

        try:
            # Proxycurl API endpoint for profile data
            api_url = "https://nubela.co/proxycurl/api/v2/linkedin"

            async with httpx.AsyncClient(timeout=30.0) as client:
                # Get profile data
                response = await client.get(
                    api_url,
                    params={'url': profile_url},
                    headers={'Authorization': f'Bearer {self.api_key}'}
                )

                if response.status_code == 200:
                    data = response.json()

                    # Extract current position
                    current_position = self._extract_current_position(data)
                    if current_position:
                        item = self._create_item(
                            title=f"[LinkedIn Profile] {profile_name} - {current_position['title']}",
                            content=f"{profile_name} is currently {current_position['title']} at {current_position['company']}. {profile_role}",
                            url=profile_url,
                            published_date=datetime.now(),
                            raw_data={
                                'profile_name': profile_name,
                                'profile_role': profile_role,
                                'current_position': current_position,
                                'source': 'proxycurl',
                                'full_profile': data
                            }
                        )
                        items.append(item)

                    # Check for recent job changes
                    job_change_items = self._extract_job_changes(data, profile_name, profile_url)
                    items.extend(job_change_items)

                elif response.status_code == 404:
                    self.logger.warning(f"Profile not found: {profile_url}")
                elif response.status_code == 429:
                    self.logger.warning("Proxycurl rate limit exceeded")
                else:
                    self.logger.warning(f"Proxycurl API error: {response.status_code}")

        except Exception as e:
            self.logger.error(f"Error with Proxycurl API: {e}")

        return items

    async def _collect_via_scraping(
        self,
        profile_url: str,
        profile_name: str,
        profile_role: str
    ) -> List[IntelligenceItemCreate]:
        """
        Collect profile data via public profile scraping

        Note: This is a best-effort approach. LinkedIn actively blocks scrapers.
        Use Proxycurl API for production use.
        """
        items = []

        try:
            if not self._check_rate_limit():
                return items

            async with httpx.AsyncClient(
                headers=self.headers,
                timeout=30.0,
                follow_redirects=True
            ) as client:
                response = await client.get(profile_url)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Extract current position (LinkedIn's public profile structure)
                    # Note: Structure may change frequently
                    current_position = self._scrape_current_position(soup)

                    if current_position:
                        item = self._create_item(
                            title=f"[LinkedIn Profile] {profile_name} - {current_position.get('title', 'Position')}",
                            content=f"{profile_name} profile update detected. {profile_role}",
                            url=profile_url,
                            published_date=datetime.now(),
                            raw_data={
                                'profile_name': profile_name,
                                'profile_role': profile_role,
                                'current_position': current_position,
                                'source': 'web_scraping'
                            }
                        )
                        items.append(item)
                    else:
                        self.logger.warning(f"Could not extract position data from {profile_url}")

                elif response.status_code == 999:
                    self.logger.warning(f"LinkedIn blocking detected for {profile_url}")
                else:
                    self.logger.warning(f"Failed to access profile: {response.status_code}")

        except Exception as e:
            self.logger.error(f"Error scraping profile: {e}")

        return items

    async def _collect_posts_via_proxycurl(
        self,
        profile_url: str,
        profile_name: str,
        profile_role: str
    ) -> List[IntelligenceItemCreate]:
        """
        Collect recent posts/activity using Proxycurl API

        Proxycurl Activity Endpoint: Returns recent posts, articles, and activity
        API Docs: https://nubela.co/proxycurl/docs#linkedin-profile-activity-endpoint

        Note: Activity endpoint is a separate API call and may have additional costs
        """
        items = []

        try:
            # Proxycurl API endpoint for profile activity
            activity_url = "https://nubela.co/proxycurl/api/linkedin/profile/activities"

            async with httpx.AsyncClient(timeout=30.0) as client:
                # Get recent activity/posts
                response = await client.get(
                    activity_url,
                    params={'url': profile_url},
                    headers={'Authorization': f'Bearer {self.api_key}'}
                )

                if response.status_code == 200:
                    data = response.json()

                    # Extract posts from activity data
                    activities = data.get('activities', [])

                    # Limit to most recent 10 posts
                    for activity in activities[:10]:
                        try:
                            # Extract post data
                            post_text = activity.get('text', '')
                            post_url = activity.get('url', profile_url)
                            posted_date = activity.get('posted_on')

                            # Skip if no meaningful content
                            if not post_text or len(post_text) < 10:
                                continue

                            # Parse date if available
                            published_date = None
                            if posted_date:
                                try:
                                    from dateutil import parser
                                    published_date = parser.parse(posted_date)
                                except:
                                    published_date = datetime.now()
                            else:
                                published_date = datetime.now()

                            # Create intelligence item for the post
                            item = self._create_item(
                                title=f"[LinkedIn Post] {profile_name}: {post_text[:100]}...",
                                content=post_text,
                                url=post_url,
                                published_date=published_date,
                                raw_data={
                                    'profile_name': profile_name,
                                    'profile_role': profile_role,
                                    'activity_type': activity.get('type', 'post'),
                                    'engagement': {
                                        'likes': activity.get('num_likes', 0),
                                        'comments': activity.get('num_comments', 0),
                                        'shares': activity.get('num_shares', 0)
                                    },
                                    'source': 'proxycurl_activity'
                                }
                            )
                            items.append(item)

                            self.logger.info(f"Collected post from {profile_name}: {post_text[:50]}...")

                        except Exception as e:
                            self.logger.debug(f"Error parsing activity: {e}")
                            continue

                elif response.status_code == 404:
                    self.logger.info(f"No activity data available for: {profile_url}")
                elif response.status_code == 429:
                    self.logger.warning("Proxycurl activity rate limit exceeded")
                else:
                    self.logger.warning(f"Proxycurl activity API error: {response.status_code}")

        except Exception as e:
            self.logger.error(f"Error collecting posts via Proxycurl: {e}")

        return items

    async def _collect_posts_via_scraping(
        self,
        profile_url: str,
        profile_name: str,
        profile_role: str
    ) -> List[IntelligenceItemCreate]:
        """
        Collect recent posts via public profile scraping

        Note: This is very limited and fragile. LinkedIn's structure changes frequently
        and they actively block scrapers. Use Proxycurl API for reliable post collection.
        """
        items = []

        try:
            if not self._check_rate_limit():
                return items

            # Construct activity/posts URL
            # Public LinkedIn profiles show recent activity
            profile_id = self._extract_profile_id(profile_url)
            if not profile_id:
                return items

            # LinkedIn activity URLs (may require login for full access)
            activity_url = f"https://www.linkedin.com/in/{profile_id}/recent-activity/all/"

            async with httpx.AsyncClient(
                headers=self.headers,
                timeout=30.0,
                follow_redirects=True
            ) as client:
                response = await client.get(activity_url)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Try to find post containers
                    # Note: These selectors are very fragile and may break
                    post_containers = soup.find_all('div', class_='feed-shared-update-v2')

                    if not post_containers:
                        # Try alternate selectors
                        post_containers = soup.find_all('article', class_='activity-item')

                    for container in post_containers[:5]:  # Limit to 5 posts
                        try:
                            # Extract post text
                            text_elem = container.find('span', class_='break-words') or \
                                       container.find('div', class_='feed-shared-text')

                            if not text_elem:
                                continue

                            post_text = text_elem.get_text(strip=True)

                            # Skip if too short
                            if len(post_text) < 10:
                                continue

                            # Try to extract post URL
                            link_elem = container.find('a', href=True)
                            post_url = link_elem['href'] if link_elem else profile_url

                            # Create intelligence item
                            item = self._create_item(
                                title=f"[LinkedIn Post] {profile_name}: {post_text[:100]}...",
                                content=post_text,
                                url=post_url,
                                published_date=datetime.now(),
                                raw_data={
                                    'profile_name': profile_name,
                                    'profile_role': profile_role,
                                    'source': 'web_scraping',
                                    'note': 'Scraped from public profile - may be incomplete'
                                }
                            )
                            items.append(item)

                            self.logger.info(f"Scraped post from {profile_name}: {post_text[:50]}...")

                        except Exception as e:
                            self.logger.debug(f"Error parsing post container: {e}")
                            continue

                elif response.status_code == 999:
                    self.logger.warning(f"LinkedIn blocking detected for activity: {profile_url}")
                else:
                    self.logger.info(f"Could not access activity feed: {response.status_code}")

        except Exception as e:
            self.logger.error(f"Error scraping posts: {e}")

        return items

    def _extract_profile_id(self, profile_url: str) -> str | None:
        """Extract profile ID/username from LinkedIn URL"""
        try:
            # LinkedIn profile URLs: https://www.linkedin.com/in/{profile_id}/
            parts = profile_url.rstrip('/').split('/')
            if 'in' in parts:
                idx = parts.index('in')
                if idx + 1 < len(parts):
                    return parts[idx + 1]
        except Exception:
            pass
        return None

    def _extract_current_position(self, profile_data: Dict[str, Any]) -> Dict[str, str] | None:
        """Extract current position from Proxycurl API response"""
        try:
            experiences = profile_data.get('experiences', [])
            if not experiences:
                return None

            # First experience is typically the current one
            current = experiences[0]

            # Check if it's a current position (no end date)
            if current.get('ends_at') is None:
                return {
                    'title': current.get('title', ''),
                    'company': current.get('company', ''),
                    'description': current.get('description', ''),
                    'starts_at': current.get('starts_at', '')
                }
        except Exception as e:
            self.logger.debug(f"Error extracting current position: {e}")

        return None

    def _extract_job_changes(
        self,
        profile_data: Dict[str, Any],
        profile_name: str,
        profile_url: str
    ) -> List[IntelligenceItemCreate]:
        """
        Extract recent job changes from profile data

        Looks for position changes in the last 90 days
        """
        items = []

        try:
            experiences = profile_data.get('experiences', [])

            for exp in experiences:
                starts_at = exp.get('starts_at')
                if not starts_at:
                    continue

                # Check if this is a recent job change (within last 90 days)
                try:
                    start_date = datetime(
                        year=starts_at.get('year', 2000),
                        month=starts_at.get('month', 1),
                        day=starts_at.get('day', 1)
                    )

                    days_ago = (datetime.now() - start_date).days

                    if days_ago <= 90 and days_ago >= 0:
                        # This is a recent job change
                        item = self._create_item(
                            title=f"[LinkedIn] {profile_name} joined {exp.get('company')} as {exp.get('title')}",
                            content=f"Career move: {profile_name} started as {exp.get('title')} at {exp.get('company')}",
                            url=profile_url,
                            published_date=start_date,
                            raw_data={
                                'profile_name': profile_name,
                                'job_change': True,
                                'company': exp.get('company'),
                                'title': exp.get('title'),
                                'source': 'proxycurl'
                            }
                        )
                        items.append(item)

                except Exception as e:
                    self.logger.debug(f"Error parsing job change date: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error extracting job changes: {e}")

        return items

    def _scrape_current_position(self, soup: BeautifulSoup) -> Dict[str, str] | None:
        """
        Extract current position from LinkedIn public profile HTML

        Note: This is fragile and may break as LinkedIn changes their HTML structure.
        For production, use Proxycurl API.
        """
        try:
            # Try to find the experience section
            # These selectors may need to be updated as LinkedIn changes
            title_elem = soup.find('div', class_='text-body-medium')
            company_elem = soup.find('span', class_='text-body-small')

            if title_elem and company_elem:
                return {
                    'title': title_elem.get_text(strip=True),
                    'company': company_elem.get_text(strip=True)
                }

            # Fallback: try alternate selectors
            headline = soup.find('div', class_='top-card-layout__headline')
            if headline:
                return {
                    'title': headline.get_text(strip=True),
                    'company': ''
                }

        except Exception as e:
            self.logger.debug(f"Error scraping position: {e}")

        return None


class LinkedInAlternativeCollector(BaseCollector):
    """
    Alternative LinkedIn collector using third-party services

    For production use, consider:
    - Proxycurl API (paid, official LinkedIn data)
    - ScraperAPI (for scraping with rotation)
    - RapidAPI LinkedIn endpoints
    """

    def __init__(self, customer_config: Dict[str, Any]):
        super().__init__(customer_config)
        self.api_key = settings.proxycurl_api_key  # Example third-party service

    def get_source_type(self) -> str:
        return "linkedin"

    async def collect(self) -> List[IntelligenceItemCreate]:
        """
        Collect using third-party API

        Example placeholder for Proxycurl or similar service
        """
        items = []

        if not self.api_key:
            self.logger.warning("LinkedIn API service not configured")
            return items

        # Implement third-party API integration here
        # This is a placeholder for future implementation

        return items
