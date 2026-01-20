#!/usr/bin/env python3
"""
Test script to analyze Yahoo Finance news page structure
"""
import asyncio
from playwright.async_api import async_playwright
import json


async def analyze_yahoo_news_page(stock_symbol: str):
    """Analyze the structure of Yahoo Finance news page"""
    url = f"https://finance.yahoo.com/quote/{stock_symbol}/news/"

    async with async_playwright() as p:
        # Launch browser in headless mode
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print(f"Navigating to {url}...")
        await page.goto(url, wait_until="networkidle")

        # Wait for news articles to load
        await page.wait_for_timeout(3000)  # Wait 3 seconds for dynamic content

        # Try to find news article containers
        print("\n=== Analyzing page structure ===\n")

        # Look for common selectors for news articles
        selectors_to_try = [
            'li.stream-item',
            'article',
            'div[data-test="news-stream"]',
            'div.stream-item',
            'li[data-test-locator="stream-item"]',
            'div.js-content-viewer',
            'h3 a',
            'a[data-ylk*="itc:0"]',
        ]

        for selector in selectors_to_try:
            elements = await page.query_selector_all(selector)
            print(f"Selector '{selector}': Found {len(elements)} elements")

        # Try to extract article information
        print("\n=== Extracting article data ===\n")

        # Get all links that look like news articles
        article_links = await page.query_selector_all('a[href*="/news/"]')
        print(f"Found {len(article_links)} news article links")

        # Extract first few articles for analysis
        articles = []
        for i, link in enumerate(article_links[:5]):
            try:
                href = await link.get_attribute('href')
                text = await link.inner_text()

                # Try to find associated metadata
                parent = await link.evaluate_handle('el => el.closest("li, article, div[class*=stream]")')

                if parent:
                    html = await parent.evaluate('el => el.outerHTML')

                    article_data = {
                        'index': i,
                        'title': text.strip(),
                        'url': href,
                        'html_preview': html[:500] + '...' if len(html) > 500 else html
                    }
                    articles.append(article_data)
                    print(f"\n--- Article {i + 1} ---")
                    print(f"Title: {article_data['title']}")
                    print(f"URL: {article_data['url']}")

            except Exception as e:
                print(f"Error extracting article {i}: {e}")

        # Take a screenshot for debugging
        screenshot_path = f"/var/home/nmerrett/Documents/vibing/atl-intel/yahoo_news_{stock_symbol.replace('.', '_')}.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"\n=== Screenshot saved to {screenshot_path} ===")

        # Save raw HTML for analysis
        html_content = await page.content()
        html_path = f"/var/home/nmerrett/Documents/vibing/atl-intel/yahoo_news_{stock_symbol.replace('.', '_')}.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"=== HTML saved to {html_path} ===")

        # Save extracted articles as JSON
        json_path = f"/var/home/nmerrett/Documents/vibing/atl-intel/yahoo_news_{stock_symbol.replace('.', '_')}_articles.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(articles, f, indent=2)
        print(f"=== Article data saved to {json_path} ===")

        await browser.close()

        return articles


if __name__ == "__main__":
    stock_symbol = "ANZ.AX"
    articles = asyncio.run(analyze_yahoo_news_page(stock_symbol))
    print(f"\n=== Summary: Found {len(articles)} articles ===")
