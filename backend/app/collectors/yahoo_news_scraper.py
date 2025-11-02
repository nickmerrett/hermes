"""
Yahoo Finance News Scraper using Playwright
Replaces yfinance news collection with direct web scraping
"""
import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)


class YahooNewsScraperError(Exception):
    """Custom exception for Yahoo News Scraper errors"""
    pass


class YahooNewsScraper:
    """
    Scrapes news articles from Yahoo Finance stock pages
    """

    def __init__(self, headless: bool = True, timeout: int = 30000):
        """
        Initialize the Yahoo News Scraper

        Args:
            headless: Whether to run browser in headless mode
            timeout: Page load timeout in milliseconds
        """
        self.headless = headless
        self.timeout = timeout

    async def scrape_news(self, stock_symbol: str, max_articles: int = 20) -> List[Dict]:
        """
        Scrape news articles for a given stock symbol

        Args:
            stock_symbol: Stock ticker symbol (e.g., "ANZ.AX")
            max_articles: Maximum number of articles to retrieve

        Returns:
            List of article dictionaries with keys:
                - title: Article headline
                - url: Link to full article
                - publisher: News source/publisher
                - published_date: Publication timestamp (datetime or None)
                - summary: Article summary/description (if available)
                - thumbnail_url: Image URL (if available)

        Raises:
            YahooNewsScraperError: If scraping fails
        """
        url = f"https://finance.yahoo.com/quote/{stock_symbol}/news/"

        try:
            async with async_playwright() as p:
                logger.info(f"Launching browser to scrape {url}")
                browser = await p.chromium.launch(headless=self.headless)

                try:
                    page = await browser.new_page()

                    # Navigate to the news page
                    logger.info(f"Navigating to {url}")
                    await page.goto(url, wait_until="networkidle", timeout=self.timeout)

                    # Wait for articles to load
                    try:
                        await page.wait_for_selector('li.stream-item.story-item', timeout=10000)
                    except PlaywrightTimeout:
                        logger.warning("Timeout waiting for story items - page may not have loaded properly")

                    # Additional wait for dynamic content
                    await page.wait_for_timeout(2000)

                    # Extract articles using JavaScript in the browser context
                    articles_data = await page.evaluate("""
                        () => {
                            const articles = [];
                            const storyItems = document.querySelectorAll('li.stream-item.story-item');

                            storyItems.forEach((item) => {
                                try {
                                    // Find title and URL
                                    const titleLink = item.querySelector('a[class*="titles"]');
                                    if (!titleLink) return;

                                    const title = titleLink.textContent.trim();
                                    const url = titleLink.href;

                                    // Skip if no valid URL
                                    if (!url || !url.startsWith('http')) return;

                                    // Find publisher and date (combined in publishing div)
                                    const publishingDiv = item.querySelector('div[class*="publishing"]');
                                    let publisher = 'Unknown';
                                    let published_date = null;

                                    if (publishingDiv) {
                                        const publishingText = publishingDiv.textContent.trim();
                                        // Format is like: "Retail Banker International • 16d ago"
                                        const parts = publishingText.split('•').map(p => p.trim());
                                        if (parts.length >= 2) {
                                            publisher = parts[0];
                                            published_date = parts[1];
                                        } else if (parts.length === 1) {
                                            // Might just be publisher or just date
                                            if (parts[0].includes('ago') || parts[0].includes('hour') || parts[0].includes('day')) {
                                                published_date = parts[0];
                                            } else {
                                                publisher = parts[0];
                                            }
                                        }
                                    }

                                    // Find summary/description
                                    const summaryElem = item.querySelector('p[class*="description"]');
                                    const summary = summaryElem ? summaryElem.textContent.trim() : null;

                                    // Find thumbnail image
                                    const imgElem = item.querySelector('img');
                                    const thumbnail_url = imgElem ? imgElem.src : null;

                                    articles.push({
                                        title,
                                        url,
                                        publisher,
                                        published_date,
                                        summary,
                                        thumbnail_url
                                    });
                                } catch (e) {
                                    console.error('Error extracting article:', e);
                                }
                            });

                            return articles;
                        }
                    """)

                    logger.info(f"Extracted {len(articles_data)} articles from {url}")

                    # Process and normalize the articles
                    articles = []
                    for article_data in articles_data[:max_articles]:
                        # Parse the published date
                        published_date = self._parse_date(article_data.get('published_date'))

                        article = {
                            'title': article_data['title'],
                            'url': article_data['url'],
                            'publisher': article_data.get('publisher', 'Unknown'),
                            'published_date': published_date,
                            'summary': article_data.get('summary'),
                            'thumbnail_url': article_data.get('thumbnail_url'),
                        }
                        articles.append(article)

                    return articles

                finally:
                    await browser.close()

        except PlaywrightTimeout as e:
            logger.error(f"Timeout while scraping {url}: {e}")
            raise YahooNewsScraperError(f"Timeout loading page: {e}")
        except Exception as e:
            logger.error(f"Error scraping news for {stock_symbol}: {e}")
            raise YahooNewsScraperError(f"Failed to scrape news: {e}")

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse various date formats from Yahoo Finance
        Uses the same logic as LinkedIn collector for consistency

        Args:
            date_str: Date string in various formats (e.g., "16d ago", "2h ago", "1 week ago")

        Returns:
            datetime object or None if parsing fails
        """
        if not date_str:
            return None

        # Try ISO format first (datetime attribute)
        try:
            # Handle ISO format with timezone
            if 'T' in date_str:
                # Remove timezone suffix if present and parse
                date_str_clean = date_str.replace('Z', '+00:00')
                return datetime.fromisoformat(date_str_clean)
        except (ValueError, AttributeError):
            pass

        # Parse relative time patterns (reused from LinkedIn collector)
        # Patterns: "1mo", "1 mo", "1 month", "1month ago", "16d ago", etc.
        import re
        from datetime import timedelta

        date_string = date_str.strip().lower()
        now = datetime.now(timezone.utc)

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

        logger.warning(f"Could not parse date: {date_str}")
        return None


async def scrape_yahoo_news(stock_symbol: str, max_articles: int = 20) -> List[Dict]:
    """
    Convenience function to scrape Yahoo Finance news

    Args:
        stock_symbol: Stock ticker symbol (e.g., "ANZ.AX")
        max_articles: Maximum number of articles to retrieve

    Returns:
        List of article dictionaries
    """
    scraper = YahooNewsScraper()
    return await scraper.scrape_news(stock_symbol, max_articles)


# For testing/debugging
if __name__ == "__main__":
    import json

    async def test():
        scraper = YahooNewsScraper(headless=True)
        articles = await scraper.scrape_news("ANZ.AX", max_articles=10)

        print(f"\n=== Found {len(articles)} articles ===\n")
        for i, article in enumerate(articles, 1):
            print(f"{i}. {article['title']}")
            print(f"   Publisher: {article['publisher']}")
            print(f"   Date: {article['published_date']}")
            print(f"   URL: {article['url']}")
            if article['summary']:
                print(f"   Summary: {article['summary'][:100]}...")
            print()

        # Save to JSON
        with open('scraped_articles.json', 'w', encoding='utf-8') as f:
            json.dump(articles, f, indent=2, default=str)
        print("Articles saved to scraped_articles.json")

    asyncio.run(test())
