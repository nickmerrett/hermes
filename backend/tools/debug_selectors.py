#!/usr/bin/env python3
"""
Debug script to find correct selectors for publisher and date
"""
import asyncio
from playwright.async_api import async_playwright


async def debug_selectors():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("Loading page...")
        await page.goto("https://finance.yahoo.com/quote/ANZ.AX/news/", wait_until="networkidle")
        await page.wait_for_selector('li.stream-item.story-item', timeout=10000)
        await page.wait_for_timeout(2000)

        # Get the first article's HTML
        first_article_html = await page.evaluate("""
            () => {
                const item = document.querySelector('li.stream-item.story-item');
                return item ? item.innerHTML : null;
            }
        """)

        if first_article_html:
            print("\n=== First Article HTML ===")
            print(first_article_html[:3000])
            print("\n" + "="*50 + "\n")

        # Try different selectors for publisher
        publisher_selectors = [
            'div[class*="provider"]',
            'div[class*="Provider"]',
            'span[class*="provider"]',
            'div[class*="source"]',
            '.provider-name',
            '[data-test="provider-name"]',
        ]

        print("\n=== Testing Publisher Selectors ===")
        for selector in publisher_selectors:
            result = await page.evaluate(f"""
                () => {{
                    const item = document.querySelector('li.stream-item.story-item');
                    const elem = item ? item.querySelector('{selector}') : null;
                    return elem ? elem.textContent.trim() : null;
                }}
            """)
            print(f"{selector}: {result}")

        # Try different selectors for date/time
        time_selectors = [
            'time',
            'span[class*="time"]',
            'div[class*="time"]',
            'span[class*="age"]',
            '[data-test="article-age"]',
        ]

        print("\n=== Testing Time Selectors ===")
        for selector in time_selectors:
            result = await page.evaluate(f"""
                () => {{
                    const item = document.querySelector('li.stream-item.story-item');
                    const elem = item ? item.querySelector('{selector}') : null;
                    if (!elem) return null;
                    return {{
                        text: elem.textContent.trim(),
                        datetime: elem.getAttribute('datetime')
                    }};
                }}
            """)
            print(f"{selector}: {result}")

        # Get all classes in the first article
        print("\n=== All Elements with Classes ===")
        all_classes = await page.evaluate("""
            () => {
                const item = document.querySelector('li.stream-item.story-item');
                const elements = item ? item.querySelectorAll('[class]') : [];
                const classes = {};
                elements.forEach(el => {
                    const className = el.className;
                    const text = el.textContent.trim().substring(0, 50);
                    if (!classes[className] && text.length > 0 && text.length < 100) {
                        classes[className] = text;
                    }
                });
                return classes;
            }
        """)
        for class_name, text in list(all_classes.items())[:20]:
            print(f"{class_name}: {text}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(debug_selectors())
