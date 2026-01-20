"""Web scraper collector for sites without RSS feeds using trafilatura or Playwright"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
import trafilatura
import asyncio

try:
    from playwright.async_api import async_playwright, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from app.collectors.base import RateLimitedCollector
from app.models.schemas import IntelligenceItemCreate


class WebScraperCollector(RateLimitedCollector):
    """
    Advanced web scraper using trafilatura or Playwright for content extraction

    Configuration via YAML:
    web_scrape_sources:
      - name: "Source Name"
        url: "https://example.com/news"
        mode: "trafilatura"  # Fast mode using HTTP requests (default)
        selectors:  # Only needed for basic mode or article list discovery
          article_list: "div.article"  # CSS selector for article containers
          title: "h2.title"             # CSS selector for title (basic mode)
          link: "a.read-more"           # CSS selector for article link
          date: "span.date"             # Optional: date selector (basic mode)
          summary: "p.summary"          # Optional: summary (basic mode)
        max_articles: 20                # Optional: limit articles per scrape
        extract_full_content: true      # Use trafilatura to fetch full article (default: true)

      - name: "JS-Heavy Site"
        url: "https://example.com/modern-blog"
        mode: "playwright"              # Browser automation for JS-rendered sites
        playwright_options:
          headless: true                # Run browser in headless mode (default: true)
          wait_for_selector: "div.posts"  # Wait for this selector to appear
          wait_timeout: 10000           # Timeout in ms (default: 10000)
          scroll_to_load: false         # Scroll to trigger lazy loading (default: false)
          scroll_pause: 1               # Seconds to pause between scrolls (default: 1)
        selectors:
          article_list: "div.post"
          title: "h2.title"
          link: "a.permalink"
          date: "time.published"
        max_articles: 20
    """

    def __init__(self, customer_config: Dict[str, Any]):
        super().__init__(customer_config, rate_limit=10)

        collection_config = customer_config.get('config', {})
        self.scrape_sources = collection_config.get('web_scrape_sources', [])

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    def get_source_type(self) -> str:
        return "web_scrape"

    async def collect(self) -> List[IntelligenceItemCreate]:
        """Collect from all configured web scrape sources"""
        items = []

        if not self.scrape_sources:
            self.logger.debug("No web scrape sources configured")
            return items

        # Separate sources by mode
        http_sources = []
        playwright_sources = []

        for source_config in self.scrape_sources:
            mode = source_config.get('mode', 'trafilatura')
            if mode == 'playwright':
                playwright_sources.append(source_config)
            else:
                http_sources.append(source_config)

        # Process HTTP-based sources (trafilatura/basic)
        if http_sources:
            async with httpx.AsyncClient(headers=self.headers, timeout=30.0, follow_redirects=True) as client:
                for source_config in http_sources:
                    try:
                        source_items = await self._scrape_source(client, source_config)
                        items.extend(source_items)
                    except Exception as e:
                        source_name = source_config.get('name', 'Unknown')
                        self.logger.error(f"Error scraping {source_name}: {e}", exc_info=True)

        # Process Playwright-based sources
        if playwright_sources:
            if not PLAYWRIGHT_AVAILABLE:
                self.logger.error("Playwright sources configured but Playwright not installed")
            else:
                playwright_items = await self._scrape_with_playwright(playwright_sources)
                items.extend(playwright_items)

        self.logger.info(f"Collected {len(items)} items from {len(self.scrape_sources)} web scrape sources")
        return items

    async def _scrape_source(
        self,
        client: httpx.AsyncClient,
        source_config: Dict[str, Any]
    ) -> List[IntelligenceItemCreate]:
        """Scrape a single source based on its configuration"""
        items = []

        source_name = source_config.get('name', 'Unknown Source')
        url = source_config.get('url')
        extract_full = source_config.get('extract_full_content', True)
        selectors = source_config.get('selectors', {})
        max_articles = source_config.get('max_articles', 20)

        if not url:
            self.logger.warning(f"Invalid config for {source_name}: missing url")
            return items

        try:
            # Fetch the listing page
            self.logger.debug(f"Fetching {url}")
            response = await client.get(url)
            response.raise_for_status()

            # Find article links
            article_links = self._find_article_links(response.text, selectors, url)
            self.logger.info(f"Found {len(article_links)} article links on {source_name}")

            # Process each article
            processed = 0
            for article_data in article_links[:max_articles]:
                try:
                    if extract_full and article_data.get('url'):
                        # Use trafilatura to fetch and extract full article
                        item = await self._extract_with_trafilatura(
                            client,
                            article_data['url'],
                            source_name
                        )
                    else:
                        # Use basic extraction from listing page
                        item = self._create_basic_item(article_data, source_name, url)

                    if item and self._should_collect_item(item.title, item.content or ''):
                        items.append(item)
                        processed += 1

                except Exception as e:
                    self.logger.debug(f"Error processing article: {e}")
                    continue

            self.logger.info(f"Scraped {len(items)} relevant items from {source_name}")

        except httpx.HTTPError as e:
            self.logger.error(f"HTTP error scraping {source_name}: {e}")
        except Exception as e:
            self.logger.error(f"Error parsing {source_name}: {e}", exc_info=True)

        return items

    def _find_article_links(
        self,
        html: str,
        selectors: Dict[str, Any],
        base_url: str
    ) -> List[Dict[str, Any]]:
        """Find article links and metadata from listing page"""
        articles = []
        soup = BeautifulSoup(html, 'html.parser')

        article_list_selector = selectors.get('article_list', 'article, .article, .post')
        article_containers = soup.select(article_list_selector)

        for article_elem in article_containers:
            try:
                article_data = {}

                # Extract title
                title_selector = selectors.get('title', 'h1, h2, h3, h4 a, .title')
                title_elem = article_elem.select_one(title_selector)
                if title_elem:
                    article_data['title'] = title_elem.get_text(strip=True)

                # Extract link
                link_selector = selectors.get('link', 'a')
                link_elem = article_elem.select_one(link_selector)
                if link_elem:
                    url = link_elem.get('href', '')
                    if url and not url.startswith('http'):
                        from urllib.parse import urljoin
                        url = urljoin(base_url, url)
                    article_data['url'] = url

                # Extract date
                date_selector = selectors.get('date')
                if date_selector:
                    date_elem = article_elem.select_one(date_selector)
                    if date_elem:
                        article_data['date_text'] = date_elem.get_text(strip=True)

                # Extract summary
                summary_selector = selectors.get('summary')
                if summary_selector:
                    summary_elem = article_elem.select_one(summary_selector)
                    if summary_elem:
                        article_data['summary'] = summary_elem.get_text(strip=True)

                # Only add if we have at least a URL or title
                if article_data.get('url') or article_data.get('title'):
                    articles.append(article_data)

            except Exception as e:
                self.logger.debug(f"Error extracting article metadata: {e}")
                continue

        return articles

    async def _extract_with_trafilatura(
        self,
        client: httpx.AsyncClient,
        url: str,
        source_name: str
    ) -> Optional[IntelligenceItemCreate]:
        """Use trafilatura to extract full article content"""
        try:
            # Fetch the article page
            response = await client.get(url)
            response.raise_for_status()

            # Extract content with trafilatura
            downloaded = response.text

            # Extract with metadata
            result = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False,
                favor_precision=True,
                url=url,
                with_metadata=True,
                output_format='json'
            )

            if not result:
                self.logger.debug(f"Trafilatura could not extract content from {url}")
                return None

            # Parse the JSON result
            import json
            metadata = json.loads(result) if isinstance(result, str) else result

            title = metadata.get('title', 'Untitled')
            content = metadata.get('text', '')

            # Parse date
            published_date = None
            date_str = metadata.get('date')
            if date_str:
                try:
                    published_date = date_parser.parse(date_str)
                except (ValueError, TypeError):
                    pass

            return self._create_item(
                title=f"[{source_name}] {title}",
                content=content,
                url=url,
                published_date=published_date,
                raw_data={
                    'source': source_name,
                    'method': 'trafilatura',
                    'author': metadata.get('author'),
                    'hostname': metadata.get('hostname'),
                    'description': metadata.get('description'),
                }
            )

        except Exception as e:
            self.logger.debug(f"Error extracting with trafilatura from {url}: {e}")
            return None

    def _create_basic_item(
        self,
        article_data: Dict[str, Any],
        source_name: str,
        base_url: str
    ) -> Optional[IntelligenceItemCreate]:
        """Create item from basic extracted data (without full content fetch)"""
        try:
            title = article_data.get('title', 'Untitled')
            content = article_data.get('summary', '')
            url = article_data.get('url')

            # Parse date
            published_date = None
            date_text = article_data.get('date_text')
            if date_text:
                published_date = self._parse_date(date_text)

            return self._create_item(
                title=f"[{source_name}] {title}",
                content=content,
                url=url,
                published_date=published_date,
                raw_data={
                    'source': source_name,
                    'scrape_url': base_url,
                    'method': 'basic_scrape'
                }
            )

        except Exception as e:
            self.logger.error(f"Error creating basic item: {e}")
            return None

    async def _scrape_with_playwright(
        self,
        sources: List[Dict[str, Any]]
    ) -> List[IntelligenceItemCreate]:
        """Scrape sources using Playwright browser automation"""
        items = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                ]
            )

            try:
                context = await browser.new_context(
                    user_agent=self.headers['User-Agent'],
                    viewport={'width': 1920, 'height': 1080},
                )

                # Add stealth script
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """)

                page = await context.new_page()

                for source_config in sources:
                    try:
                        source_items = await self._scrape_source_with_playwright(
                            page, source_config
                        )
                        items.extend(source_items)
                    except Exception as e:
                        source_name = source_config.get('name', 'Unknown')
                        self.logger.error(f"Error scraping {source_name} with Playwright: {e}", exc_info=True)

            finally:
                await browser.close()

        return items

    async def _scrape_source_with_playwright(
        self,
        page: Page,
        source_config: Dict[str, Any]
    ) -> List[IntelligenceItemCreate]:
        """Scrape a single source using Playwright"""
        items = []

        source_name = source_config.get('name', 'Unknown Source')
        url = source_config.get('url')
        selectors = source_config.get('selectors', {})
        max_articles = source_config.get('max_articles', 20)
        pw_options = source_config.get('playwright_options', {})

        if not url:
            self.logger.warning(f"Invalid config for {source_name}: missing url")
            return items

        try:
            self.logger.info(f"Scraping {source_name} with Playwright")

            # Navigate to page
            await page.goto(url, wait_until='domcontentloaded')

            # Wait for specific selector if configured
            wait_selector = pw_options.get('wait_for_selector')
            wait_timeout = pw_options.get('wait_timeout', 10000)
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=wait_timeout)
                except Exception as e:
                    self.logger.warning(f"Timeout waiting for selector {wait_selector}: {e}")

            # Optional: Scroll to load content
            if pw_options.get('scroll_to_load', False):
                scroll_pause = pw_options.get('scroll_pause', 1)
                await self._scroll_page(page, scroll_pause)

            # Get page HTML
            html = await page.content()

            # Extract articles using same method as HTTP scraper
            article_links = self._find_article_links(html, selectors, url)
            self.logger.info(f"Found {len(article_links)} article links on {source_name}")

            # Process articles (use first pass data, don't fetch full articles again)
            for article_data in article_links[:max_articles]:
                try:
                    item = self._create_basic_item(article_data, source_name, url)
                    if item and self._should_collect_item(item.title, item.content or ''):
                        items.append(item)
                except Exception as e:
                    self.logger.debug(f"Error processing article: {e}")
                    continue

            self.logger.info(f"Scraped {len(items)} items from {source_name} with Playwright")

        except Exception as e:
            self.logger.error(f"Error scraping {source_name} with Playwright: {e}", exc_info=True)

        return items

    async def _scroll_page(self, page: Page, pause_seconds: float = 1):
        """Scroll page to trigger lazy loading"""
        try:
            # Get initial height
            prev_height = await page.evaluate("document.body.scrollHeight")

            for _ in range(5):  # Max 5 scrolls
                # Scroll to bottom
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(pause_seconds)

                # Check if height changed
                new_height = await page.evaluate("document.body.scrollHeight")
                if new_height == prev_height:
                    break  # No more content loaded
                prev_height = new_height

        except Exception as e:
            self.logger.debug(f"Error during page scroll: {e}")

    def _parse_date(self, date_text: str, date_format: Optional[str] = None) -> Optional[datetime]:
        """Parse date string into datetime object"""
        if not date_text:
            return None

        try:
            # Try custom format first if provided
            if date_format:
                return datetime.strptime(date_text, date_format)

            # Try fuzzy parsing
            return date_parser.parse(date_text, fuzzy=True)
        except Exception as e:
            self.logger.debug(f"Could not parse date '{date_text}': {e}")
            return None
