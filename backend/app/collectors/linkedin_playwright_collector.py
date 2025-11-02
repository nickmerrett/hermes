"""
Playwright-based LinkedIn collector for user profiles and posts

Uses browser automation to scrape LinkedIn data while avoiding detection.
Supports both logged-in and anonymous scraping modes.

Requirements:
    pip install playwright playwright-stealth
    playwright install chromium
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio
import json
import hashlib
import re
from pathlib import Path

try:
    from playwright.async_api import async_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from app.collectors.base import RateLimitedCollector
from app.models.schemas import IntelligenceItemCreate
from app.config.settings import settings


class PlaywrightLinkedInCollector(RateLimitedCollector):
    """
    LinkedIn collector using Playwright browser automation

    Features:
    - Stealth mode to avoid detection
    - Session persistence (saves cookies)
    - Optional login support
    - Profile data collection
    - Post/activity collection
    - Smart rate limiting

    Configuration:
        LINKEDIN_EMAIL: Your LinkedIn email (optional, for logged-in scraping)
        LINKEDIN_PASSWORD: Your LinkedIn password (optional)
        LINKEDIN_HEADLESS: Run in headless mode (default: true)
    """

    def __init__(self, customer_config: Dict[str, Any]):
        super().__init__(customer_config, rate_limit=5)  # Very conservative: 5 profiles/min

        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright not installed. Run: "
                "pip install playwright && playwright install chromium"
            )

        self.user_profiles = customer_config.get('config', {}).get('linkedin_user_profiles', [])

        # LinkedIn credentials (optional - for logged-in scraping)
        self.linkedin_email = getattr(settings, 'linkedin_email', None)
        self.linkedin_password = getattr(settings, 'linkedin_password', None)

        # Browser settings
        self.headless = getattr(settings, 'linkedin_headless', True)

        # Session persistence
        self.session_dir = Path('data/linkedin_sessions')
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.session_file = self.session_dir / f'session_{self.customer_id}.json'

        # Anti-detection settings
        self.user_agent = (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )

    def get_source_type(self) -> str:
        return "linkedin_user"

    async def collect(self) -> List[IntelligenceItemCreate]:
        """
        Collect LinkedIn user profile data using Playwright

        Returns:
            List of IntelligenceItemCreate objects
        """
        items = []

        if not self.user_profiles:
            self.logger.info("No LinkedIn user profiles configured")
            return items

        self.logger.info(f"Starting Playwright-based LinkedIn collection for {len(self.user_profiles)} profiles")

        async with async_playwright() as p:
            # Launch browser with anti-detection measures
            browser = await self._launch_browser(p)

            try:
                # Create context with saved session
                context = await self._create_context(browser)
                page = await context.new_page()

                # Check if we need to login
                if self.linkedin_email and self.linkedin_password:
                    await self._ensure_logged_in(page)

                # Collect data for each profile
                for profile_config in self.user_profiles:
                    if not self._check_rate_limit():
                        self.logger.warning("Rate limit reached, stopping collection")
                        break

                    try:
                        profile_url = profile_config.get('profile_url')
                        profile_name = profile_config.get('name', 'Unknown')
                        profile_role = profile_config.get('role', '')

                        if not profile_url:
                            continue

                        self.logger.info(f"Collecting data for: {profile_name}")

                        # Skip profile data collection - we only want posts/articles
                        # profile_items = await self._collect_profile_data(
                        #     page, profile_url, profile_name, profile_role
                        # )
                        # items.extend(profile_items)

                        # Collect recent posts
                        post_items = await self._collect_profile_posts(
                            page, profile_url, profile_name, profile_role
                        )
                        items.extend(post_items)

                        # Small delay between profiles
                        await asyncio.sleep(2)

                    except Exception as e:
                        self.logger.error(f"Error collecting profile {profile_name}: {e}")
                        continue

                # Save session for next time
                await self._save_session(context)

            finally:
                await browser.close()

        self.logger.info(f"Collected {len(items)} items via Playwright")
        return items

    async def _launch_browser(self, playwright) -> Browser:
        """Launch browser with anti-detection settings"""

        launch_options = {
            'headless': self.headless,
            'args': [
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process'
            ]
        }

        browser = await playwright.chromium.launch(**launch_options)
        return browser

    async def _create_context(self, browser: Browser):
        """Create browser context with session persistence"""

        context_options = {
            'user_agent': self.user_agent,
            'viewport': {'width': 1920, 'height': 1080},
            'locale': 'en-US',
            'timezone_id': 'America/New_York',
        }

        # Load saved session if exists
        if self.session_file.exists():
            try:
                with open(self.session_file, 'r') as f:
                    storage_state = json.load(f)
                context_options['storage_state'] = storage_state
                self.logger.info("Loaded saved LinkedIn session")
            except Exception as e:
                self.logger.warning(f"Could not load session: {e}")

        context = await browser.new_context(**context_options)

        # Add extra stealth
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
        """)

        return context

    async def _save_session(self, context):
        """Save session cookies for reuse"""
        try:
            storage_state = await context.storage_state()
            with open(self.session_file, 'w') as f:
                json.dump(storage_state, f)
            self.logger.info("Saved LinkedIn session")
        except Exception as e:
            self.logger.warning(f"Could not save session: {e}")

    async def _ensure_logged_in(self, page: Page):
        """Ensure user is logged into LinkedIn"""

        try:
            # Navigate to LinkedIn
            await page.goto('https://www.linkedin.com/feed', wait_until='domcontentloaded')
            await asyncio.sleep(2)

            # Check if we're on login page
            current_url = page.url

            if 'login' in current_url or 'uas/login' in current_url:
                self.logger.info("Not logged in, attempting login...")
                await self._perform_login(page)
            else:
                self.logger.info("Already logged in")

        except Exception as e:
            self.logger.error(f"Login check failed: {e}")
            raise

    async def _perform_login(self, page: Page):
        """Perform LinkedIn login"""

        if not self.linkedin_email or not self.linkedin_password:
            raise ValueError("LinkedIn credentials not configured")

        try:
            # Navigate to login page
            await page.goto('https://www.linkedin.com/login', wait_until='domcontentloaded')
            await asyncio.sleep(2)

            # Fill in credentials
            await page.fill('input[name="session_key"]', self.linkedin_email)
            await page.fill('input[name="session_password"]', self.linkedin_password)

            # Click login
            await page.click('button[type="submit"]')
            await page.wait_for_load_state('networkidle', timeout=30000)

            # Check if login successful
            if 'checkpoint/challenge' in page.url:
                self.logger.error("Login requires verification/captcha")
                raise Exception("Login verification required - please login manually once")

            if 'feed' in page.url or 'mynetwork' in page.url:
                self.logger.info("Login successful!")
            else:
                self.logger.warning(f"Login may have failed, current URL: {page.url}")

        except Exception as e:
            self.logger.error(f"Login failed: {e}")
            raise

    async def _collect_profile_data(
        self,
        page: Page,
        profile_url: str,
        profile_name: str,
        profile_role: str
    ) -> List[IntelligenceItemCreate]:
        """Collect profile data from LinkedIn profile page"""

        items = []

        try:
            # Navigate to profile
            await page.goto(profile_url, wait_until='domcontentloaded')
            await asyncio.sleep(3)  # Wait for dynamic content

            # Check if we got blocked
            if 'authwall' in page.url or 'uas/login' in page.url:
                self.logger.warning(f"Profile requires login: {profile_url}")
                return items

            # Extract profile headline/title
            try:
                headline = await page.text_content('div.text-body-medium', timeout=5000)
                if headline:
                    headline = headline.strip()
            except:
                headline = None

            # Extract current position
            try:
                position_elem = await page.query_selector('div.pvs-list__outer-container li.pvs-list__paged-list-item')
                if position_elem:
                    job_title = await position_elem.text_content()
                    job_title = job_title.strip() if job_title else None
                else:
                    job_title = headline
            except:
                job_title = headline

            # Create profile update item
            if headline or job_title:
                item = self._create_item(
                    title=f"[LinkedIn Profile] {profile_name} - {headline or job_title or 'Profile'}",
                    content=f"{profile_name} profile data collected via browser automation. {profile_role}",
                    url=profile_url,
                    published_date=datetime.now(),
                    raw_data={
                        'profile_name': profile_name,
                        'profile_role': profile_role,
                        'headline': headline,
                        'job_title': job_title,
                        'source': 'playwright',
                        'collection_method': 'browser_automation'
                    }
                )
                items.append(item)
                self.logger.info(f"Collected profile data for {profile_name}")

        except Exception as e:
            self.logger.error(f"Error collecting profile data: {e}")

        return items

    def _parse_linkedin_date(self, date_string: str) -> datetime:
        """
        Parse LinkedIn relative date format to datetime

        Args:
            date_string: LinkedIn date string like "2h", "1d", "2w", "1mo", "1 month ago", etc.

        Returns:
            datetime object in container timezone
        """
        if not date_string:
            return datetime.now()

        date_string = date_string.strip().lower()
        now = datetime.now()  # Container timezone set via TZ environment variable

        # Try to match relative time patterns
        # Patterns: "1mo", "1 mo", "1 month", "1month ago", etc.
        patterns = [
            (r'(\d+)\s*h(?:our|r|rs)?', 'hours'),
            (r'(\d+)\s*d(?:ay|ays)?', 'days'),
            (r'(\d+)\s*w(?:eek|k|ks)?', 'weeks'),
            (r'(\d+)\s*mo(?:nth|nths)?', 'months'),
            (r'(\d+)\s*y(?:ear|r|rs)?', 'years'),
        ]

        for pattern, unit in patterns:
            match = re.search(pattern, date_string)
            if match:
                value = int(match.group(1))

                if unit == 'hours':
                    return now - timedelta(hours=value)
                elif unit == 'days':
                    return now - timedelta(days=value)
                elif unit == 'weeks':
                    return now - timedelta(weeks=value)
                elif unit == 'months':
                    return now - timedelta(days=value * 30)  # Approximate month
                elif unit == 'years':
                    return now - timedelta(days=value * 365)  # Approximate year

        # If we can't parse it, return current time
        self.logger.debug(f"Could not parse date string: '{date_string}'")
        return now

    async def _collect_profile_posts(
        self,
        page: Page,
        profile_url: str,
        profile_name: str,
        profile_role: str
    ) -> List[IntelligenceItemCreate]:
        """Collect recent posts from LinkedIn profile"""

        items = []

        try:
            # Navigate to activity page
            activity_url = profile_url.rstrip('/') + '/recent-activity/all/'
            await page.goto(activity_url, wait_until='domcontentloaded')
            await asyncio.sleep(3)

            # Check if blocked
            if 'authwall' in page.url or 'uas/login' in page.url:
                self.logger.warning(f"Activity page requires login: {activity_url}")
                return items

            # Find post containers
            post_selectors = [
                'div.feed-shared-update-v2',
                'div.profile-creator-shared-feed-update__container',
                'li.profile-creator-shared-feed-update__container'
            ]

            posts = []
            for selector in post_selectors:
                try:
                    posts = await page.query_selector_all(selector)
                    if posts:
                        break
                except:
                    continue

            if not posts:
                self.logger.info(f"No posts found for {profile_name}")
                return items

            # Extract data from first 5 posts
            for idx, post in enumerate(posts[:5]):
                try:
                    # Extract post text
                    text_elem = await post.query_selector('span.break-words')
                    if not text_elem:
                        text_elem = await post.query_selector('div.feed-shared-text')

                    if text_elem:
                        post_text = await text_elem.text_content()
                        post_text = post_text.strip() if post_text else None

                        if post_text and len(post_text) > 20:
                            # Try to get post URL
                            link_elem = await post.query_selector('a[href*="/posts/"]')
                            if link_elem:
                                post_url = await link_elem.get_attribute('href')
                            else:
                                # Generate unique URL using hash of content to avoid duplicates
                                content_hash = hashlib.md5(post_text.encode()).hexdigest()[:12]
                                post_url = f"{profile_url}#post-{content_hash}"

                            # Try to extract post date
                            post_date = datetime.now()  # Default fallback (container timezone)
                            date_found = False

                            # More specific date selectors for LinkedIn
                            date_selectors = [
                                'span.feed-shared-actor__sub-description span.visually-hidden',
                                'span.update-components-actor__sub-description span.visually-hidden',
                                'span.feed-shared-actor__sub-description',
                                'span.update-components-actor__sub-description',
                                '.feed-shared-actor__sub-description time',
                                'time',
                                'span[aria-hidden="true"]',
                            ]

                            for selector in date_selectors:
                                try:
                                    date_elem = await post.query_selector(selector)
                                    if date_elem:
                                        date_text = await date_elem.text_content()
                                        date_text = date_text.strip() if date_text else ""

                                        # Look for patterns like "1mo", "2w", "3d", "4h"
                                        if date_text and re.search(r'\d+\s*(mo|w|d|h|y)', date_text.lower()):
                                            post_date = self._parse_linkedin_date(date_text)
                                            self.logger.info(f"✓ Parsed post date from '{selector}': '{date_text}' -> {post_date.strftime('%Y-%m-%d %H:%M')}")
                                            date_found = True
                                            break
                                except Exception as e:
                                    continue

                            if not date_found:
                                self.logger.warning(f"Could not extract date for post, using current time")

                            # Create post item
                            item = self._create_item(
                                title=f"[LinkedIn Post] {profile_name}: {post_text[:100]}...",
                                content=post_text,
                                url=post_url,
                                published_date=post_date,
                                raw_data={
                                    'profile_name': profile_name,
                                    'profile_role': profile_role,
                                    'source': 'playwright',
                                    'collection_method': 'browser_automation',
                                    'post_index': idx
                                }
                            )
                            items.append(item)

                except Exception as e:
                    self.logger.debug(f"Error extracting post: {e}")
                    continue

            self.logger.info(f"Collected {len(items)} posts for {profile_name}")

        except Exception as e:
            self.logger.error(f"Error collecting posts: {e}")

        return items
