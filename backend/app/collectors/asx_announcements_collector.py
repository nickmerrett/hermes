"""ASX Announcements collector using the MarkitDigital API"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from io import BytesIO

import httpx
from pypdf import PdfReader

from app.collectors.base import BaseCollector
from app.models.schemas import IntelligenceItemCreate

PDF_EXCERPT_MAX_CHARS = 3000
PDF_MAX_PAGES_TO_SCAN = 5     # how many leading pages to look through
PDF_MIN_PAGE_CHARS = 150      # pages shorter than this are probably a cover/disclaimer page


class ASXAnnouncementsCollector(BaseCollector):
    """
    Collector for official ASX company announcements.

    Uses the MarkitDigital API to fetch announcements for ASX-listed companies.
    Provides headline, announcement type, price sensitivity, and document links.

    Requires customer to have a stock_symbol ending in .AX (e.g., "ANZ.AX").
    """

    API_BASE = "https://asx.api.markitdigital.com/asx-research/1.0/companies"
    DOCUMENT_BASE = "https://cdn-api.markitdigital.com/apiman-gateway/ASX/asx-research/1.0/file"

    def __init__(self, customer_config: Dict[str, Any]):
        super().__init__(customer_config)
        self.stock_symbol = customer_config.get('stock_symbol')

        if not self.stock_symbol:
            raise ValueError(f"Stock symbol not configured for {self.customer_name}")

        # Strip .AX suffix to get ASX ticker
        self.asx_ticker = self.stock_symbol.replace('.AX', '').replace('.ax', '')

    def get_source_type(self) -> str:
        return "asx_announcements"

    async def collect(self) -> List[IntelligenceItemCreate]:
        """Collect announcements from the ASX API."""
        items = []

        try:
            url = f"{self.API_BASE}/{self.asx_ticker}/announcements"
            params = {"count": 20, "market_sensitive": "false"}

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers={"Accept": "application/json"}
                )
                response.raise_for_status()

                data = response.json()
                announcements = data.get("data", {}).get("items", [])

                if not announcements:
                    self.logger.info(f"No ASX announcements found for {self.asx_ticker}")
                    return items

                self.logger.info(f"Fetched {len(announcements)} ASX announcements for {self.asx_ticker}")

                for announcement in announcements:
                    item = await self._process_announcement(announcement, client)
                    if item:
                        items.append(item)

        except httpx.HTTPStatusError as e:
            self.logger.error(f"ASX API HTTP error for {self.asx_ticker}: {e.response.status_code}")
            raise
        except Exception as e:
            self.logger.error(f"Error fetching ASX announcements for {self.asx_ticker}: {e}")
            raise

        return items

    async def _fetch_pdf_excerpt(self, client: httpx.AsyncClient, doc_url: str) -> Optional[str]:
        """
        Best-effort peek at an announcement PDF: substantive text from the leading
        pages, bounded in size. Cover pages, letterheads and disclaimer pages are
        often near-empty of real text, so short pages are skipped in favour of
        wherever the actual content (e.g. an executive summary) starts.
        """
        try:
            response = await client.get(doc_url, timeout=20.0)
            response.raise_for_status()

            content_length = len(response.content)
            if content_length > 20 * 1024 * 1024:  # 20MB - skip huge docs (e.g. full annual reports)
                self.logger.debug(f"Skipping PDF excerpt, too large ({content_length} bytes): {doc_url}")
                return None

            reader = PdfReader(BytesIO(response.content))
            if not reader.pages:
                return None

            collected = []
            collected_chars = 0
            best_fallback = ""  # longest single page seen, in case every page is short

            for page in reader.pages[:PDF_MAX_PAGES_TO_SCAN]:
                text = (page.extract_text() or "").strip()
                if not text:
                    continue

                if len(text) > len(best_fallback):
                    best_fallback = text

                if len(text) < PDF_MIN_PAGE_CHARS:
                    # Likely a cover/letterhead/disclaimer page - skip, keep scanning
                    continue

                collected.append(text)
                collected_chars += len(text)
                if collected_chars >= PDF_EXCERPT_MAX_CHARS:
                    break

            excerpt = "\n\n".join(collected) if collected else best_fallback
            if not excerpt:
                return None

            return excerpt[:PDF_EXCERPT_MAX_CHARS]

        except Exception as e:
            self.logger.debug(f"Could not extract PDF excerpt from {doc_url}: {e}")
            return None

    async def _process_announcement(
        self, announcement: Dict[str, Any], client: httpx.AsyncClient
    ) -> IntelligenceItemCreate | None:
        """Process a single ASX announcement into an IntelligenceItemCreate."""
        try:
            headline = announcement.get("headline", "Untitled Announcement")
            is_price_sensitive = announcement.get("is_price_sensitive", False)
            announcement_type = announcement.get("type", "Unknown")
            display_name = announcement.get("display_name", self.asx_ticker)
            document_key = announcement.get("documentKey", "")
            file_size = announcement.get("size", 0)

            # Build title with sensitivity flag
            prefix = f"[ASX:{self.asx_ticker}]"
            if is_price_sensitive:
                prefix += " [PRICE SENSITIVE]"
            title = f"{prefix} {headline}"

            # Build content
            content_parts = [
                f"ASX Announcement: {announcement_type}",
                f"Company: {display_name}",
            ]
            if is_price_sensitive:
                content_parts.append("Price Sensitive: Yes")

            # Build document URL from documentKey
            doc_url = None
            if document_key:
                doc_url = f"{self.DOCUMENT_BASE}/{document_key}"

            # Best-effort peek at the PDF's first page so downstream AI processing
            # has something to summarize beyond the bare headline
            if doc_url:
                excerpt = await self._fetch_pdf_excerpt(client, doc_url)
                if excerpt:
                    content_parts.append(f"Document excerpt:\n{excerpt}")

            content = "\n".join(content_parts)

            # Parse published date
            published_date = None
            date_str = announcement.get("document_date")
            if date_str:
                try:
                    published_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    pass

            return self._create_item(
                title=title,
                content=content,
                url=doc_url,
                published_date=published_date,
                raw_data={
                    'stock_symbol': self.stock_symbol,
                    'asx_ticker': self.asx_ticker,
                    'announcement_type': announcement_type,
                    'is_price_sensitive': is_price_sensitive,
                    'document_key': document_key,
                    'file_size': file_size,
                    'display_name': display_name,
                }
            )

        except Exception as e:
            self.logger.error(f"Error processing ASX announcement: {e}")
            return None
