"""
Mailsac collector for newsletter monitoring.

Fetches emails from Mailsac disposable inboxes, extracts article links,
and creates intelligence items from newsletter content.
"""

import re
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

import httpx
import trafilatura
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from app.collectors.base import RateLimitedCollector
from app.models.schemas import IntelligenceItemCreate
from app.config.settings import settings


class MailsacCollector(RateLimitedCollector):
    """
    Mailsac collector for newsletter monitoring.

    Fetches emails from Mailsac inboxes, extracts article links,
    and creates intelligence items from full article content.
    """

    BASE_URL = "https://mailsac.com/api"

    def __init__(self, customer_config: Dict[str, Any]):
        super().__init__(customer_config, rate_limit=60)  # 1 req/sec to be safe

        mailsac_cfg = customer_config.get('config', {}).get('mailsac_config', {})

        self.api_key = settings.mailsac_api_key
        self.email_addresses = mailsac_cfg.get('email_addresses', [])
        self.extract_links = mailsac_cfg.get('extract_links', True)
        self.delete_after_processing = mailsac_cfg.get('delete_after_processing', True)
        self.max_age_days = mailsac_cfg.get('max_age_days', 7)

        if not self.api_key:
            raise ValueError("Mailsac API key not configured (MAILSAC_API_KEY)")

        if not self.email_addresses:
            raise ValueError("No Mailsac email addresses configured for this customer")

    def get_source_type(self) -> str:
        return "mailsac"

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Mailsac API requests."""
        return {
            "Mailsac-Key": self.api_key,
            "Accept": "application/json"
        }

    async def collect(self) -> List[IntelligenceItemCreate]:
        """Collect newsletter content from Mailsac inboxes."""
        items = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for email_address in self.email_addresses:
                try:
                    inbox_items = await self._process_inbox(client, email_address)
                    items.extend(inbox_items)
                except Exception as e:
                    self.logger.error(f"Error processing inbox {email_address}: {e}")
                    continue

        self.logger.info(f"Collected {len(items)} items from Mailsac")
        return items

    async def _process_inbox(
        self, client: httpx.AsyncClient, email_address: str
    ) -> List[IntelligenceItemCreate]:
        """Process all messages in a Mailsac inbox."""
        items = []
        processed_message_ids = []

        try:
            # List messages in inbox
            response = await client.get(
                f"{self.BASE_URL}/addresses/{email_address}/messages",
                headers=self._get_headers()
            )
            response.raise_for_status()
            messages = response.json()

            self.logger.info(f"Found {len(messages)} messages in {email_address}")

            # Filter by age
            cutoff_date = datetime.utcnow() - timedelta(days=self.max_age_days)

            for msg in messages:
                try:
                    # Parse message date
                    msg_date = None
                    if msg.get('received'):
                        try:
                            msg_date = date_parser.parse(msg['received'])
                        except Exception:
                            pass

                    # Skip old messages
                    if msg_date and msg_date < cutoff_date:
                        self.logger.debug(f"Skipping old message: {msg.get('subject')}")
                        continue

                    message_id = msg.get('_id')
                    subject = msg.get('subject', 'No Subject')
                    from_addr = msg.get('from', [{}])[0].get('address', 'Unknown')

                    self.logger.info(f"Processing: {subject} from {from_addr}")

                    # Fetch message body
                    body_html = await self._get_message_body(
                        client, email_address, message_id, 'body'
                    )
                    body_text = await self._get_message_body(
                        client, email_address, message_id, 'text'
                    )

                    body = body_html or body_text or ''

                    if not body:
                        self.logger.debug(f"No body content for message {message_id}")
                        continue

                    if self.extract_links:
                        # Extract and fetch article links
                        link_items = await self._extract_and_fetch_links(
                            client, body, is_html=(body_html is not None),
                            from_addr=from_addr, subject=subject,
                            msg_date=msg_date
                        )
                        items.extend(link_items)
                    else:
                        # Use email content directly as intelligence item
                        item = self._create_item_from_email(
                            subject=subject,
                            body=body,
                            from_addr=from_addr,
                            email_address=email_address,
                            msg_date=msg_date
                        )
                        if item and self._should_collect_item(item.title, item.content or ''):
                            items.append(item)

                    processed_message_ids.append((email_address, message_id))

                except Exception as e:
                    self.logger.error(f"Error processing message: {e}")
                    continue

            # Delete processed messages
            if self.delete_after_processing and processed_message_ids:
                await self._delete_messages(client, processed_message_ids)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                self.logger.error("Mailsac authentication failed - check API key")
                raise ValueError("Mailsac authentication failed - check API key")
            else:
                self.logger.error(f"Mailsac API error: {e}")
                raise

        return items

    async def _get_message_body(
        self,
        client: httpx.AsyncClient,
        email_address: str,
        message_id: str,
        body_type: str  # 'body' for HTML, 'text' for plain text
    ) -> Optional[str]:
        """Fetch message body from Mailsac."""
        try:
            response = await client.get(
                f"{self.BASE_URL}/{body_type}/{email_address}/{message_id}",
                headers=self._get_headers()
            )
            if response.status_code == 200:
                return response.text
        except Exception as e:
            self.logger.debug(f"Error fetching {body_type} body: {e}")
        return None

    async def _extract_and_fetch_links(
        self,
        client: httpx.AsyncClient,
        body: str,
        is_html: bool,
        from_addr: str,
        subject: str,
        msg_date: Optional[datetime]
    ) -> List[IntelligenceItemCreate]:
        """Extract links from email body and fetch article content."""
        items = []

        links = self._extract_article_links(body, is_html)
        self.logger.info(f"Extracted {len(links)} article links")

        for link_data in links[:10]:  # Limit to 10 links per email
            url = link_data['url']
            try:
                item = await self._fetch_article_content(
                    client, url, from_addr, subject, msg_date
                )
                if item and self._should_collect_item(item.title, item.content or ''):
                    items.append(item)
            except Exception as e:
                self.logger.debug(f"Error fetching {url}: {e}")
                continue

        return items

    def _extract_article_links(self, body: str, is_html: bool) -> List[Dict[str, str]]:
        """Extract article URLs from email body."""
        links = []

        if is_html:
            soup = BeautifulSoup(body, 'html.parser')
            for a_tag in soup.find_all('a', href=True):
                url = a_tag['href']
                if self._is_article_url(url):
                    links.append({
                        'url': url,
                        'title': a_tag.get_text(strip=True)
                    })
        else:
            url_pattern = r'https?://[^\s<>"\']+'
            urls = re.findall(url_pattern, body)
            for url in urls:
                url = url.rstrip('.,;:)')
                if self._is_article_url(url):
                    links.append({'url': url, 'title': ''})

        # Deduplicate
        seen = set()
        unique = []
        for link in links:
            if link['url'] not in seen:
                seen.add(link['url'])
                unique.append(link)

        return unique

    def _is_article_url(self, url: str) -> bool:
        """Check if URL is likely an article (not tracking/social/image)."""
        url_lower = url.lower()

        # Skip non-article links
        skip_patterns = [
            'unsubscribe', 'preferences', 'manage-subscription',
            'facebook.com', 'twitter.com', 'x.com/share',
            'linkedin.com/share', 'instagram.com',
            'mailto:', 'tel:', 'javascript:',
            '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
            '.pdf', '.doc', '.docx',
            'track.', 'click.', 'trk.', 'email.', 'e.email',
            'list-manage.com', 'mailchimp.com',
            'substack.com/subscribe', '/subscribe',
            'youtube.com/watch', 'youtu.be'
        ]

        for pattern in skip_patterns:
            if pattern in url_lower:
                return False

        # Must be http(s)
        if not url_lower.startswith('http'):
            return False

        return True

    async def _fetch_article_content(
        self,
        client: httpx.AsyncClient,
        url: str,
        from_addr: str,
        subject: str,
        msg_date: Optional[datetime]
    ) -> Optional[IntelligenceItemCreate]:
        """Fetch full article content using trafilatura."""
        try:
            response = await client.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }, follow_redirects=True)
            response.raise_for_status()

            result = trafilatura.extract(
                response.text,
                include_comments=False,
                include_tables=False,
                favor_precision=True,
                url=url,
                with_metadata=True,
                output_format='json'
            )

            if not result:
                return None

            metadata = json.loads(result) if isinstance(result, str) else result

            title = metadata.get('title', 'Untitled')
            content = metadata.get('text', '')

            if not content:
                return None

            # Parse published date from article or use email date
            published_date = msg_date or datetime.utcnow()
            if metadata.get('date'):
                try:
                    published_date = date_parser.parse(metadata['date'])
                except Exception:
                    pass

            return self._create_item(
                title=title,
                content=content,
                url=url,
                published_date=published_date,
                raw_data={
                    'source': 'mailsac',
                    'email_from': from_addr,
                    'email_subject': subject,
                    'author': metadata.get('author'),
                    'hostname': metadata.get('hostname'),
                    'description': metadata.get('description')
                }
            )

        except httpx.HTTPStatusError as e:
            self.logger.debug(f"HTTP error fetching {url}: {e.response.status_code}")
            return None
        except Exception as e:
            self.logger.debug(f"Error fetching article from {url}: {e}")
            return None

    def _create_item_from_email(
        self,
        subject: str,
        body: str,
        from_addr: str,
        email_address: str,
        msg_date: Optional[datetime]
    ) -> Optional[IntelligenceItemCreate]:
        """Create intelligence item directly from email content."""
        # Strip HTML if present
        if '<html' in body.lower() or '<body' in body.lower():
            soup = BeautifulSoup(body, 'html.parser')
            content = soup.get_text(separator='\n', strip=True)
        else:
            content = body

        if not content or len(content) < 50:
            return None

        return self._create_item(
            title=subject,
            content=content[:10000],  # Limit content length
            url=None,
            published_date=msg_date or datetime.utcnow(),
            raw_data={
                'source': 'mailsac',
                'email_from': from_addr,
                'inbox_address': email_address
            }
        )

    async def _delete_messages(
        self,
        client: httpx.AsyncClient,
        message_ids: List[tuple]
    ):
        """Delete processed messages from Mailsac."""
        deleted = 0
        for email_address, message_id in message_ids:
            try:
                response = await client.delete(
                    f"{self.BASE_URL}/addresses/{email_address}/messages/{message_id}",
                    headers=self._get_headers()
                )
                if response.status_code in (200, 204):
                    deleted += 1
            except Exception as e:
                self.logger.debug(f"Error deleting message {message_id}: {e}")

        self.logger.info(f"Deleted {deleted}/{len(message_ids)} processed messages")
