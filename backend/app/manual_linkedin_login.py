#!/usr/bin/env python
"""
Manual LinkedIn Login Script

This script opens a browser window where you can manually login to LinkedIn.
After you login, it saves the session cookies for automated collection to use.

Usage:
    python app/manual_linkedin_login.py

    OR from Docker/Podman (with X11 forwarding):
    podman exec -it intel-backend python app/manual_linkedin_login.py
"""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright


async def manual_login():
    """Launch browser for manual LinkedIn login"""

    print("=" * 70)
    print("Manual LinkedIn Login")
    print("=" * 70)
    print()
    print("This will open a browser window where you can login to LinkedIn.")
    print("After logging in:")
    print("  1. Complete any security challenges")
    print("  2. Make sure you see your LinkedIn feed")
    print("  3. Return to this terminal and press Enter")
    print()
    print("The session will be saved and reused for automated collection.")
    print()
    print("=" * 70)
    print()

    input("Press Enter to open browser...")

    # Session storage
    session_dir = Path('data/linkedin_sessions')
    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = session_dir / 'session_manual.json'

    async with async_playwright() as p:
        # Launch browser in NON-HEADLESS mode so you can see it
        print("Launching browser...")
        browser = await p.chromium.launch(
            headless=False,  # IMPORTANT: Not headless so you can interact
            args=[
                '--disable-blink-features=AutomationControlled',
            ]
        )

        # Create context with realistic settings
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
        )

        # Add stealth
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        page = await context.new_page()

        # Navigate to LinkedIn login
        print("Opening LinkedIn login page...")
        await page.goto('https://www.linkedin.com/login')

        print()
        print("=" * 70)
        print("🌐 BROWSER WINDOW OPENED")
        print("=" * 70)
        print()
        print("Instructions:")
        print("  1. In the browser window, login to LinkedIn")
        print("  2. Enter your email and password")
        print("  3. Complete any security verification (2FA, captcha, etc.)")
        print("  4. Wait until you see your LinkedIn feed/home page")
        print("  5. Come back here and press Enter")
        print()
        print("⚠️  DO NOT close the browser window!")
        print()

        # Wait for user to login manually
        input("Press Enter AFTER you have logged in and see your feed...")

        # Check if login was successful
        current_url = page.url
        print(f"\nCurrent URL: {current_url}")

        if 'feed' in current_url or 'mynetwork' in current_url or 'linkedin.com' in current_url:
            print("✅ Looks like you're logged in!")

            # Save the session
            print("\nSaving session cookies...")
            storage_state = await context.storage_state()

            with open(session_file, 'w') as f:
                json.dump(storage_state, f, indent=2)

            print(f"✅ Session saved to: {session_file}")
            print()
            print("=" * 70)
            print("SUCCESS!")
            print("=" * 70)
            print()
            print("Your LinkedIn session has been saved.")
            print("Automated collection will now use this session.")
            print()
            print("Next steps:")
            print("  1. Close the browser window")
            print("  2. Run: python app/cli.py collect")
            print()

        else:
            print("⚠️  Warning: Doesn't look like you're logged in")
            print(f"   Expected to see 'feed' or 'mynetwork' in URL, but got: {current_url}")
            print()

            save_anyway = input("Save session anyway? (y/n): ")
            if save_anyway.lower() == 'y':
                storage_state = await context.storage_state()
                with open(session_file, 'w') as f:
                    json.dump(storage_state, f, indent=2)
                print(f"✅ Session saved to: {session_file}")
            else:
                print("❌ Session not saved. Try again.")

        # Don't close automatically - let user close browser
        print()
        input("Press Enter to close browser and exit...")

        await browser.close()
        print("\nBrowser closed. Goodbye!")


async def copy_to_customer_sessions():
    """Copy manual session to customer session files"""
    print()
    copy = input("Copy this session to customer session files? (y/n): ")

    if copy.lower() != 'y':
        return

    session_dir = Path('data/linkedin_sessions')
    manual_session = session_dir / 'session_manual.json'

    if not manual_session.exists():
        print("❌ Manual session file not found!")
        return

    # Copy to session_1.json and session_2.json (for NBN Co and ANZ)
    for customer_id in [1, 2]:
        customer_session = session_dir / f'session_{customer_id}.json'

        with open(manual_session, 'r') as src:
            session_data = json.load(src)

        with open(customer_session, 'w') as dst:
            json.dump(session_data, dst, indent=2)

        print(f"✅ Copied to: {customer_session}")

    print()
    print("Session files updated! Collections will use this login.")


if __name__ == '__main__':
    try:
        asyncio.run(manual_login())
        asyncio.run(copy_to_customer_sessions())
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
