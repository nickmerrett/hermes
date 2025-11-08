"""
Customer research service for automated config generation

Uses web search and AI to discover:
- Company information (domain, description, stock symbol)
- Executive team and LinkedIn profiles
- Competitors
- Keywords and data sources
"""

import logging
from typing import Dict, List, Any, Optional
import re
import httpx
from bs4 import BeautifulSoup
from anthropic import Anthropic

from app.config.settings import settings

logger = logging.getLogger(__name__)


class CustomerResearchService:
    """
    Research companies and generate customer config data

    Uses web search + AI analysis to discover company information
    """

    def __init__(self):
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),  # 10s total, 5s to connect
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        )

    async def research_company(self, company_name: str) -> Dict[str, Any]:
        """
        Research a company and return structured data

        Args:
            company_name: Name of the company to research

        Returns:
            Dictionary with researched information
        """
        logger.info(f"Starting research for company: {company_name}")

        result = {
            'company_name': company_name,
            'domain': None,
            'description': None,
            'stock_symbol': None,
            'industry': None,
            'executives': [],
            'competitors': [],
            'keywords': [],
            'priority_keywords': [],
            'data_sources': {
                'rss_feeds': [],
                'twitter_handle': None,
                'linkedin_company_url': None,
                'subreddits': []
            }
        }

        # Step 1: Basic company info (domain, description, stock)
        basic_info = await self._research_basic_info(company_name)
        result.update(basic_info)

        # Store domain for use by other methods
        self._current_domain = result.get('domain')

        # Step 2: Find executives
        linkedin_url = result.get('linkedin_company_url') or ''
        executives = await self._research_executives(company_name, linkedin_url)
        result['executives'] = executives

        # Step 3: Find competitors
        competitors = await self._research_competitors(company_name, result.get('industry'))
        result['competitors'] = competitors

        # Step 4: Generate keywords
        keywords = await self._generate_keywords(company_name, result)
        result['keywords'] = keywords['keywords']
        result['priority_keywords'] = keywords['priority_keywords']

        # Step 5: Find data sources
        data_sources = await self._find_data_sources(company_name, result['domain'])
        result['data_sources'].update(data_sources)

        logger.info(f"Research completed for {company_name}")
        return result

    def _extract_json_from_text(self, text: str) -> str:
        """Extract JSON from text that may contain markdown or explanatory text"""
        import re

        # Try to find JSON in markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            return json_match.group(1)

        # Try to find raw JSON object
        json_match = re.search(r'(\{.*\})', text, re.DOTALL)
        if json_match:
            return json_match.group(1)

        return text

    async def _research_basic_info(self, company_name: str) -> Dict[str, Any]:
        """Research basic company information"""

        prompt = f"""Research the company "{company_name}" and provide the following information.

Return ONLY a JSON object (no explanatory text, no markdown formatting):

{{
  "domain": "example.com",
  "description": "Brief one-sentence description",
  "stock_symbol": "SYMB",
  "industry": "Industry name",
  "linkedin_company_url": "https://linkedin.com/company/name",
  "twitter_handle": "@company"
}}

Rules:
- Use null for any field where you're uncertain
- Domain should be just the domain name (e.g., "telstra.com.au")
- Stock symbol should include exchange if not US (e.g., "TLS.AX" for Australian stocks)
- LinkedIn URL should be the full company page URL
- Return ONLY the JSON object, nothing else"""

        try:
            response = self.client.messages.create(
                model=settings.ai_model,
                max_tokens=1000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Parse JSON response
            import json
            text_response = response.content[0].text
            json_text = self._extract_json_from_text(text_response)
            result = json.loads(json_text)

            # Ensure all expected fields exist
            defaults = {
                'domain': None,
                'description': None,
                'stock_symbol': None,
                'industry': None,
                'linkedin_company_url': None,
                'twitter_handle': None
            }
            defaults.update(result)

            logger.info(f"Found basic info for {company_name}: {defaults.get('domain')}")
            return defaults

        except Exception as e:
            logger.error(f"Error researching basic info: {e}", exc_info=True)
            logger.error(f"Raw AI response (if available): {response.content[0].text if 'response' in locals() else 'N/A'}")
            return {
                'domain': None,
                'description': None,
                'stock_symbol': None,
                'industry': None,
                'linkedin_company_url': None,
                'twitter_handle': None
            }

    async def _fetch_page_content(self, url: str) -> Optional[str]:
        """Fetch and extract text content from a web page"""
        try:
            response = await self.http_client.get(url)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()

                # Get text content
                text = soup.get_text(separator='\n', strip=True)
                # Limit to first 8000 characters to avoid token limits
                return text[:8000]
            else:
                logger.warning(f"Failed to fetch {url}: HTTP {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    async def _search_leadership_page(self, domain: str, company_name: str) -> Optional[str]:
        """Try to find and fetch the company's leadership/about page"""
        if not domain:
            return None

        common_paths = [
            '/about/leadership',
            '/about/team',
            '/leadership',
            '/team',
            '/about-us/leadership',
            '/company/leadership',
            '/about',
            '/about-us'
        ]

        for path in common_paths:
            url = f"https://{domain}{path}"
            logger.info(f"Trying leadership page: {url}")
            content = await self._fetch_page_content(url)
            if content and ('executive' in content.lower() or 'ceo' in content.lower() or 'leadership' in content.lower()):
                logger.info(f"Found leadership content at {url}")
                return content

        return None

    async def _research_executives(self, company_name: str, linkedin_url: str) -> List[Dict[str, str]]:
        """Research company executives using web scraping + AI"""

        # Try multiple sources to get current executive information
        domain = None
        if hasattr(self, '_current_domain'):
            domain = self._current_domain

        sources_content = []

        # Try company website leadership page (with timeout protection)
        if domain:
            try:
                logger.info(f"Searching company website for executives: {domain}")
                web_content = await self._search_leadership_page(domain, company_name)
                if web_content:
                    sources_content.append(("Company Website", web_content))
                    logger.info(f"✓ Found executives on company website")
            except Exception as e:
                logger.warning(f"Company website search failed: {e}")

        # Build context from sources (simplified - just use what we found)
        web_context = ""
        if sources_content:
            source_name, content = sources_content[0]
            web_context = f"\n\nCURRENT LEADERSHIP PAGE CONTENT (from {source_name}):\n{content[:6000]}\n\nUse this CURRENT information as your primary source."
            logger.info(f"Using {source_name} for executive data")
        else:
            logger.warning(f"No web sources found for {company_name} executives, using AI knowledge only")

        prompt = f"""Find the top 4-6 C-level executives for {company_name}.
{web_context}

Return ONLY a JSON array (no explanatory text, no markdown):

[
  {{
    "name": "Full Name",
    "role": "CEO",
    "linkedin_url": "https://linkedin.com/in/profile",
    "notes": "Current as of [source]"
  }}
]

Company LinkedIn: {linkedin_url}

IMPORTANT RULES:
- If leadership page content is provided above, prioritize executives from that CURRENT source
- Only include C-level executives (CEO, CTO, CFO, COO, CMO, etc.)
- Limit to 4-6 executives (quality over quantity)
- For LinkedIn URLs, construct best-guess URLs based on name and company
- Indicate source in notes (e.g., "From company website" or "From knowledge base - verify")
- Return ONLY the JSON array, nothing else"""

        try:
            response = self.client.messages.create(
                model=settings.ai_model,
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            import json
            text_response = response.content[0].text
            # Extract JSON array from text
            import re
            json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', text_response, re.DOTALL)
            if json_match:
                json_text = json_match.group(1)
            else:
                json_match = re.search(r'(\[.*\])', text_response, re.DOTALL)
                json_text = json_match.group(1) if json_match else text_response

            result = json.loads(json_text)
            logger.info(f"Found {len(result)} executives for {company_name}")
            return result

        except Exception as e:
            logger.error(f"Error researching executives: {e}")
            return []

    async def _research_competitors(self, company_name: str, industry: Optional[str]) -> List[str]:
        """Research company competitors"""

        industry_context = f" in the {industry} industry" if industry else ""

        prompt = f"""List the top 5-8 competitors for {company_name}{industry_context}.

Focus on:
- Direct competitors (same market/products)
- Major players in the industry
- Companies that sales teams would compete against

Return ONLY the company names, one per line.
Be concise - just the company name, no explanations.

Example format:
Competitor One
Competitor Two
Competitor Three"""

        try:
            response = self.client.messages.create(
                model=settings.ai_model,
                max_tokens=500,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Parse line-by-line
            competitors = [
                line.strip()
                for line in response.content[0].text.strip().split('\n')
                if line.strip() and not line.strip().startswith('#')
            ]

            logger.info(f"Found {len(competitors)} competitors for {company_name}")
            return competitors[:8]  # Limit to 8

        except Exception as e:
            logger.error(f"Error researching competitors: {e}")
            return []

    async def _generate_keywords(self, company_name: str, company_info: Dict) -> Dict[str, List[str]]:
        """Generate monitoring keywords"""

        domain = company_info.get('domain', '')
        description = company_info.get('description', '')
        industry = company_info.get('industry', '')

        prompt = f"""Generate monitoring keywords for {company_name}.

Domain: {domain}
Description: {description}
Industry: {industry}

Return ONLY a JSON object (no explanatory text, no markdown):

{{
  "keywords": ["keyword1", "keyword2", "...10-15 total"],
  "priority_keywords": ["priority1", "priority2", "...5-8 total"]
}}

Include:
- General keywords: Company name variations, products, industry terms, acronyms
- Priority keywords: High-impact terms (CEO, earnings, crisis terms, regulatory)

Return ONLY the JSON object, nothing else."""

        try:
            response = self.client.messages.create(
                model=settings.ai_model,
                max_tokens=1000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            import json
            text_response = response.content[0].text
            json_text = self._extract_json_from_text(text_response)
            result = json.loads(json_text)
            logger.info(f"Generated {len(result.get('keywords', []))} keywords")
            return result

        except Exception as e:
            logger.error(f"Error generating keywords: {e}")
            return {'keywords': [], 'priority_keywords': []}

    async def _find_data_sources(self, company_name: str, domain: Optional[str]) -> Dict[str, Any]:
        """Find potential data sources"""

        domain_hint = f" (domain: {domain})" if domain else ""

        prompt = f"""Suggest data sources to monitor for {company_name}{domain_hint}.

Return ONLY a JSON object (no explanatory text, no markdown):

{{
  "rss_feeds": [
    {{"url": "https://example.com/feed", "name": "Official Blog"}},
    {{"url": "https://example.com/news/rss", "name": "Newsroom"}}
  ],
  "subreddits": ["subreddit1", "subreddit2"]
}}

Include:
1. RSS feeds - Newsroom, blog, or press release feeds (only if confident they exist)
2. Subreddits - 3-5 relevant subreddits where this company/industry is discussed

Use empty arrays if unsure. Return ONLY the JSON object, nothing else."""

        try:
            response = self.client.messages.create(
                model=settings.ai_model,
                max_tokens=1000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            import json
            text_response = response.content[0].text
            json_text = self._extract_json_from_text(text_response)
            result = json.loads(json_text)
            logger.info(f"Found data sources for {company_name}")
            return result

        except Exception as e:
            logger.error(f"Error finding data sources: {e}")
            return {'rss_feeds': [], 'subreddits': []}

    def generate_yaml_config(self, research_data: Dict[str, Any]) -> str:
        """
        Generate YAML configuration from research data

        Args:
            research_data: Research results from research_company()

        Returns:
            YAML string ready to paste into customers.yaml
        """

        company_name = research_data['company_name']
        domain = research_data.get('domain') or ''
        description = research_data.get('description') or f"{company_name} company"
        stock_symbol = research_data.get('stock_symbol')

        # Build executives list
        executives_yaml = ""
        if research_data.get('executives'):
            executives_yaml = "\n    linkedin_user_profiles:"
            for exec_info in research_data['executives']:
                executives_yaml += f"""
      - profile_url: "{exec_info.get('linkedin_url', '')}"
        name: "{exec_info.get('name', '')}"
        role: "{exec_info.get('role', '')}"
        notes: "{exec_info.get('notes', '')}" """

        # Build RSS feeds
        rss_feeds_yaml = "[]"
        if research_data.get('data_sources', {}).get('rss_feeds'):
            rss_feeds_yaml = ""
            for feed in research_data['data_sources']['rss_feeds']:
                rss_feeds_yaml += f"""
      - url: "{feed.get('url', '')}"
        name: "{feed.get('name', '')}" """

        # Build subreddits
        subreddits_yaml = ""
        if research_data.get('data_sources', {}).get('subreddits'):
            for sub in research_data['data_sources']['subreddits']:
                subreddits_yaml += f'\n        - "{sub}"'

        yaml_config = f"""
  - name: "{company_name}"
    domain: "{domain}"
    description: "{description}"

    keywords:{self._list_to_yaml(research_data.get('keywords', []), 6)}

    competitors:{self._list_to_yaml(research_data.get('competitors', []), 6)}

    stock_symbol: {"null" if not stock_symbol else f'"{stock_symbol}"'}

    rss_feeds: {rss_feeds_yaml}

    twitter_handle: {f'"{research_data.get("data_sources", {}).get("twitter_handle")}"' if research_data.get('data_sources', {}).get('twitter_handle') else 'null'}
    linkedin_company_url: {f'"{research_data.get("linkedin_company_url")}"' if research_data.get('linkedin_company_url') else 'null'}
{executives_yaml if executives_yaml else ""}

    collection_config:
      news_enabled: true
      stock_enabled: {str(stock_symbol is not None).lower()}
      rss_enabled: true
      australian_news_enabled: true
      google_news_enabled: true

      reddit_enabled: {str(bool(subreddits_yaml)).lower()}
      reddit_subreddits:{subreddits_yaml if subreddits_yaml else ' []'}

      twitter_enabled: false
      linkedin_enabled: {str(bool(research_data.get('linkedin_company_url'))).lower()}
      linkedin_user_enabled: {str(bool(executives_yaml)).lower()}
      pressrelease_enabled: false

      priority_keywords:{self._list_to_yaml(research_data.get('priority_keywords', []), 8)}
"""

        return yaml_config

    def _list_to_yaml(self, items: List[str], indent: int = 6) -> str:
        """Convert list to YAML format with proper indentation"""
        if not items:
            return " []"

        indent_str = " " * indent
        result = ""
        for item in items:
            result += f'\n{indent_str}- "{item}"'
        return result

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup http client"""
        await self.http_client.aclose()


# Global instance
_research_service = None

def get_research_service() -> CustomerResearchService:
    """Get or create the research service singleton"""
    global _research_service
    if _research_service is None:
        _research_service = CustomerResearchService()
    return _research_service
