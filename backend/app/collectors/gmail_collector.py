"""
Gmail collector for press release digest monitoring.

Fetches emails from Gmail, extracts article links, and fetches full content.
"""

import base64
import re
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from email import message_from_bytes
from email.message import Message

import httpx
import trafilatura
from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dateutil import parser as date_parser

from app.collectors.base import RateLimitedCollector
from app.models.schemas import IntelligenceItemCreate
from app.utils.encryption import get_encryption_service
from app.config.settings import settings


class GmailCollector(RateLimitedCollector):
    """
    Gmail collector for press release digest monitoring.

    Fetches digest emails, extracts article links, and creates intelligence items
    from full article content.
    """

    def __init__(self, customer_config: Dict[str, Any]):
        super().__init__(customer_config, rate_limit=60)  # Gmail API: 1 req/sec

        gmail_cfg = customer_config.get('config', {}).get('gmail_config', {})

        self.email_address = gmail_cfg.get('email_address')
        self.encrypted_refresh_token = gmail_cfg.get('refresh_token')
        self.use_whitelist = gmail_cfg.get('use_sender_whitelist', False)
        self.sender_whitelist = gmail_cfg.get('sender_whitelist', [])
        self.label_config = gmail_cfg.get('label_config', {})

        if not self.encrypted_refresh_token:
            raise ValueError("Gmail not connected for this customer")

    def get_source_type(self) -> str:
        return "gmail"

    def _get_gmail_service(self):
        """Create authenticated Gmail API service."""
        try:
            # Decrypt refresh token
            encryption_service = get_encryption_service()
            refresh_token = encryption_service.decrypt(self.encrypted_refresh_token)

            # Create credentials
            credentials = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=settings.google_client_id,
                client_secret=settings.google_client_secret,
                scopes=[
                    'https://www.googleapis.com/auth/gmail.readonly',
                    'https://www.googleapis.com/auth/gmail.modify'
                ]
            )

            # Refresh access token
            credentials.refresh(Request())

            return build('gmail', 'v1', credentials=credentials)

        except Exception as e:
            self.logger.error(f"Error creating Gmail service: {e}", exc_info=True)
            raise

    async def collect(self) -> List[IntelligenceItemCreate]:
        """Collect press releases from Gmail digest emails."""
        items = []

        try:
            service = self._get_gmail_service()

            # Build search query
            query_parts = ['is:unread']

            # Add sender whitelist if enabled
            if self.use_whitelist and self.sender_whitelist:
                sender_queries = [f'from:{sender}' for sender in self.sender_whitelist]
                query_parts.append(f'({" OR ".join(sender_queries)})')

            # Look for emails from last 7 days
            after_date = (datetime.utcnow() - timedelta(days=7)).strftime('%Y/%m/%d')
            query_parts.append(f'after:{after_date}')

            query = ' '.join(query_parts)
            self.logger.info(f"Gmail query: {query}")

            # Search for messages
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=100
            ).execute()

            messages = results.get('messages', [])
            self.logger.info(f"Found {len(messages)} unread digest emails")

            processed_message_ids = []

            # Process each message
            for message_ref in messages:
                try:
                    # Get full message
                    message = service.users().messages().get(
                        userId='me',
                        id=message_ref['id'],
                        format='raw'
                    ).execute()

                    # Parse email
                    msg_bytes = base64.urlsafe_b64decode(message['raw'])
                    email_msg = message_from_bytes(msg_bytes)

                    subject = email_msg.get('subject', 'No Subject')
                    from_addr = email_msg.get('from', 'Unknown Sender')

                    self.logger.info(f"Processing: {subject} from {from_addr}")

                    # Extract email body
                    body_html = self._get_email_body(email_msg, 'html')
                    body_text = self._get_email_body(email_msg, 'plain')

                    # Extract press release links
                    links = self._extract_press_release_links(
                        body_html or body_text or '',
                        is_html=(body_html is not None)
                    )

                    self.logger.info(f"Extracted {len(links)} press release links")

                    # Fetch full content for each link
                    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                        for link_data in links:
                            url = link_data['url']

                            try:
                                # Fetch article content with trafilatura
                                item = await self._fetch_article_content(
                                    client, url, from_addr, subject
                                )

                                if item and self._should_collect_item(
                                    item.title, item.content or ''
                                ):
                                    items.append(item)

                            except Exception as e:
                                self.logger.debug(f"Error fetching {url}: {e}")
                                continue

                    # Mark message as processed
                    processed_message_ids.append(message_ref['id'])

                except Exception as e:
                    self.logger.error(f"Error processing message: {e}")
                    continue

            # Mark emails as read and apply label
            if processed_message_ids:
                self._mark_messages_processed(service, processed_message_ids)

            self.logger.info(f"Collected {len(items)} press release items from Gmail")

        except HttpError as e:
            if e.resp.status == 401:
                self.logger.error("Gmail authentication failed - token may be expired")
                raise ValueError("Gmail authentication failed - please reconnect your Gmail account")
            else:
                self.logger.error(f"Gmail API error: {e}", exc_info=True)
                raise

        except Exception as e:
            self.logger.error(f"Gmail collection error: {e}", exc_info=True)
            raise

        return items

    def _get_email_body(self, email_msg: Message, content_type: str) -> Optional[str]:
        """Extract email body (html or plain text)."""
        if email_msg.is_multipart():
            for part in email_msg.walk():
                if part.get_content_type() == f'text/{content_type}':
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or 'utf-8'
                            return payload.decode(charset, errors='ignore')
                    except Exception as e:
                        self.logger.debug(f"Error decoding email part: {e}")
                        continue
        else:
            if email_msg.get_content_type() == f'text/{content_type}':
                try:
                    payload = email_msg.get_payload(decode=True)
                    if payload:
                        charset = email_msg.get_content_charset() or 'utf-8'
                        return payload.decode(charset, errors='ignore')
                except Exception as e:
                    self.logger.debug(f"Error decoding email body: {e}")

        return None

    def _extract_press_release_links(
        self, body: str, is_html: bool
    ) -> List[Dict[str, str]]:
        """Extract press release URLs from email body."""
        links = []

        if is_html:
            soup = BeautifulSoup(body, 'html.parser')

            # Find all links
            for a_tag in soup.find_all('a', href=True):
                url = a_tag['href']

                # Filter for press release URLs
                if self._is_press_release_url(url):
                    links.append({
                        'url': url,
                        'title': a_tag.get_text(strip=True),
                        'snippet': ''
                    })
        else:
            # Plain text - extract URLs with regex
            url_pattern = r'https?://[^\s<>"]+'
            urls = re.findall(url_pattern, body)

            for url in urls:
                # Clean up trailing punctuation
                url = url.rstrip('.,;:)')

                if self._is_press_release_url(url):
                    links.append({
                        'url': url,
                        'title': '',
                        'snippet': ''
                    })

        # Deduplicate
        seen_urls = set()
        unique_links = []
        for link in links:
            if link['url'] not in seen_urls:
                seen_urls.add(link['url'])
                unique_links.append(link)

        return unique_links

    def _is_press_release_url(self, url: str) -> bool:
        """Check if URL looks like a press release."""
        url_lower = url.lower()

        # Skip common non-article links
        skip_patterns = [
            'unsubscribe', 'preferences', 'facebook.com', 'twitter.com',
            'linkedin.com/share', 'instagram.com', 'mailto:', 'tel:',
            '.png', '.jpg', '.jpeg', '.gif', '.pdf', '.doc',
            'youtube.com', 'youtu.be'
        ]

        for pattern in skip_patterns:
            if pattern in url_lower:
                return False

        # Known press release services
        pr_domains = [
            'prnewswire.com/news-releases',
            'businesswire.com/news/home',
            'globenewswire.com/news-release',
            'accesswire.com/newsroom',
            'prnews.io',
            'newswire.com/news-releases',
            'marketwired.com',
            'einpresswire.com',
            'prweb.com',
            'businesswire.com/portal/site'
        ]

        for domain in pr_domains:
            if domain in url_lower:
                return True

        # Check if it's a company newsroom (matches customer domain)
        if self.domain and self.domain in url_lower:
            newsroom_indicators = [
                '/news', '/press', '/newsroom', '/media',
                '/investor-relations', '/ir/', '/blog'
            ]
            if any(ind in url_lower for ind in newsroom_indicators):
                return True

        return False

    async def _fetch_article_content(
        self,
        client: httpx.AsyncClient,
        url: str,
        from_addr: str,
        subject: str
    ) -> Optional[IntelligenceItemCreate]:
        """Fetch full article content using trafilatura."""
        try:
            response = await client.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            response.raise_for_status()

            # Extract with trafilatura
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
                self.logger.debug(f"No content extracted from {url}")
                return None

            metadata = json.loads(result) if isinstance(result, str) else result

            title = metadata.get('title', 'Untitled Press Release')
            content = metadata.get('text', '')

            if not content:
                return None

            # Parse published date
            published_date = None
            date_str = metadata.get('date')
            if date_str:
                try:
                    published_date = date_parser.parse(date_str)
                except Exception:
                    pass

            return self._create_item(
                title=title,
                content=content,
                url=url,
                published_date=published_date or datetime.utcnow(),
                raw_data={
                    'source': 'gmail',
                    'email_from': from_addr,
                    'email_subject': subject,
                    'author': metadata.get('author'),
                    'hostname': metadata.get('hostname'),
                    'description': metadata.get('description'),
                    'extracted_date': datetime.utcnow().isoformat()
                }
            )

        except httpx.HTTPStatusError as e:
            self.logger.debug(f"HTTP error fetching {url}: {e.response.status_code}")
            return None

        except Exception as e:
            self.logger.debug(f"Error fetching article from {url}: {e}")
            return None

    def _mark_messages_processed(self, service, message_ids: List[str]):
        """Mark messages as read and optionally apply label."""
        try:
            modify_request = {'removeLabelIds': []}

            # Mark as read
            if self.label_config.get('mark_as_read', True):
                modify_request['removeLabelIds'].append('UNREAD')

            # Apply label if configured
            label_name = self.label_config.get('apply_label', '').strip()
            if label_name:
                # Get or create label
                label_id = self._get_or_create_label(service, label_name)
                if label_id:
                    modify_request['addLabelIds'] = [label_id]

            # Batch modify
            if modify_request['removeLabelIds'] or modify_request.get('addLabelIds'):
                service.users().messages().batchModify(
                    userId='me',
                    body={
                        'ids': message_ids,
                        **modify_request
                    }
                ).execute()

                self.logger.info(f"Marked {len(message_ids)} messages as processed")

        except Exception as e:
            self.logger.error(f"Error marking messages processed: {e}")

    def _get_or_create_label(self, service, label_name: str) -> Optional[str]:
        """Get existing label ID or create new label."""
        try:
            # List existing labels
            results = service.users().labels().list(userId='me').execute()
            labels = results.get('labels', [])

            # Check if label exists
            for label in labels:
                if label['name'] == label_name:
                    return label['id']

            # Create label
            label_object = {
                'name': label_name,
                'labelListVisibility': 'labelShow',
                'messageListVisibility': 'show'
            }
            created_label = service.users().labels().create(
                userId='me',
                body=label_object
            ).execute()

            self.logger.info(f"Created Gmail label: {label_name}")
            return created_label['id']

        except Exception as e:
            self.logger.error(f"Error with Gmail label: {e}")
            return None
