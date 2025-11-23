"""AI processor for summarization and classification using Claude or OpenAI API"""

from typing import Dict, Any, List, Optional
import json
import logging
from anthropic import Anthropic
import re
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.schemas import CategoryType, SentimentType
from app.models.database import PlatformSettings

logger = logging.getLogger(__name__)

# Import OpenAI (will be optional)
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI package not installed. OpenAI models will not be available.")


class AIProcessor:
    """
    Processes intelligence items using Claude AI for:
    - Summarization
    - Classification (category)
    - Sentiment analysis
    - Entity extraction
    - Priority scoring
    """

    def __init__(self, db: Optional[Session] = None):
        # Get model name from platform settings (for article processing = cheap model)
        # Provider config comes from environment variables
        self.model = settings.ai_model_cheap  # default from env

        if db:
            ai_config_row = db.query(PlatformSettings).filter(
                PlatformSettings.key == 'ai_config'
            ).first()
            if ai_config_row and isinstance(ai_config_row.value, dict):
                config = ai_config_row.value
                # Get cheap model name from platform settings (GUI)
                self.model = config.get('model_cheap', settings.ai_model_cheap)

        # Get provider from environment settings (economy model)
        self.provider = settings.ai_provider_cheap

        # Initialize the appropriate client based on provider
        if self.provider == 'anthropic':
            if not settings.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY not configured")
            self.client = Anthropic(
                api_key=settings.anthropic_api_key,
                base_url=settings.anthropic_api_base_url
            )
            self.client_type = 'anthropic'
        elif self.provider == 'openai':
            if not OPENAI_AVAILABLE:
                raise ValueError("OpenAI package not installed. Run: pip install openai")
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY not configured")
            self.client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url
            )
            self.client_type = 'openai'
        else:
            raise ValueError(f"Unknown AI provider: {self.provider}. Set AI_PROVIDER_CHEAP to 'anthropic' or 'openai'")

        self.max_tokens = settings.max_tokens_summary

    async def process_item(
        self,
        title: str,
        content: str,
        customer_name: str,
        source_type: str,
        keywords: List[str] = None,
        competitors: List[str] = None,
        priority_keywords: List[str] = None,
        is_trusted_source: bool = False
    ) -> Dict[str, Any]:
        """
        Process an intelligence item with AI

        Args:
            title: Item title
            content: Item content
            customer_name: Customer/company name
            source_type: Type of source
            keywords: Customer keywords for relevance checking
            competitors: List of competitor names
            priority_keywords: Keywords that indicate high priority
            is_trusted_source: If True, never mark as unrelated/advertisement (newsroom RSS, press releases)

        Returns:
            Dict with summary, category, sentiment, entities, tags, priority_score
        """
        try:
            # Build the analysis prompt
            prompt = self._build_prompt(
                title,
                content,
                customer_name,
                source_type,
                keywords or [],
                competitors or [],
                priority_keywords or [],
                is_trusted_source
            )

            # Call AI API based on provider
            if self.client_type == 'anthropic':
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                response_text = response.content[0].text
            elif self.client_type == 'openai':
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                response_text = response.choices[0].message.content
            else:
                raise ValueError(f"Unknown client type: {self.client_type}")

            # Parse response
            result = self._parse_response(response_text)

            logger.debug(f"Processed item: {title[:50]}...")
            return result

        except Exception as e:
            logger.error(f"Error processing item with AI: {e}")
            # Return default values on error
            return self._default_result(title, content)

    def _build_prompt(
        self,
        title: str,
        content: str,
        customer_name: str,
        source_type: str,
        keywords: List[str],
        competitors: List[str],
        priority_keywords: List[str],
        is_trusted_source: bool = False
    ) -> str:
        """
        Build the analysis prompt for Claude

        Args:
            title: Item title
            content: Item content
            customer_name: Customer name
            source_type: Source type
            keywords: Customer keywords
            competitors: Competitor names
            priority_keywords: High priority keywords
            is_trusted_source: If True, never mark as unrelated/advertisement

        Returns:
            Prompt string
        """
        # Build source-specific guidance
        source_guidance = self._get_source_specific_guidance(source_type)

        # Build competitor context
        competitor_context = ""
        if competitors:
            competitor_context = f"\nKNOWN COMPETITORS: {', '.join(competitors[:10])}"

        # Build keyword context
        keyword_context = ""
        if keywords:
            keyword_context = f"\nMONITORING KEYWORDS: {', '.join(keywords[:10])}"

        # Build priority keyword context
        priority_context = ""
        if priority_keywords:
            priority_context = f"\nHIGH PRIORITY KEYWORDS (boost score if mentioned): {', '.join(priority_keywords[:10])}"

        # Build trusted source guidance
        trusted_source_guidance = ""
        if is_trusted_source:
            trusted_source_guidance = f"""

⚠️  IMPORTANT: This content is from a TRUSTED SOURCE (official company newsroom, press release, or verified RSS feed).
- NEVER mark as "unrelated" or "advertisement"
- Always treat as relevant (is_relevant: true)
- These are official communications from {customer_name} or authoritative sources
- If unsure about category, use "product_update", "financial", "leadership", or "other" - NOT "unrelated" or "advertisement"
"""

        return f"""You are an AI analyst helping a technical sales team monitor intelligence about {customer_name}.

Your goal is to provide ACTIONABLE insights that help sales professionals:
- Identify sales opportunities
- Stay ahead of competitive threats
- Understand customer challenges and needs
- Prepare for conversations with relevant context

===== CONTEXT =====
Customer Being Monitored: {customer_name}{competitor_context}{keyword_context}{priority_context}{trusted_source_guidance}

===== CONTENT TO ANALYZE =====
Source Type: {source_type}
Title: {title}
Content:
{content[:3500]}

{source_guidance}

===== ANALYSIS REQUIRED =====

1. IS_RELEVANT (true/false): Is this actually about {customer_name} the company/organization?
   - FALSE if:
     * Retail advertisements or deals selling {customer_name}'s products/services (e.g., "NBN plans from $59", "Get NBN for less", "Best NBN deals")
     * Consumer promotions, discounts, or offers from resellers/retailers
     * Price comparison articles or "best deal" listicles
     * General consumer advice articles (e.g., "How to choose an NBN plan")
     * Sponsored content or affiliate marketing
     * About a different company/entity entirely
     * Spam or completely unrelated content
   - TRUE if:
     * Genuine news ABOUT {customer_name} as a company (strategy, operations, performance, challenges)
     * Executive announcements, company initiatives, or policy changes
     * Industry analysis with substantive mention of {customer_name}
     * Competitor moves that directly impact {customer_name}
     * Regulatory/government actions affecting {customer_name}

2. SUMMARY (2-4 sentences): Create an ACTION-ORIENTED summary that answers:
   - WHAT happened?
   - WHY does this matter to a sales professional?
   - WHAT are the implications (opportunities, risks, talking points)?

   Examples of good summaries:
   - "{customer_name} announced a major product launch targeting enterprise customers. This creates upsell opportunities for existing accounts and provides competitive differentiation in new deals. Sales teams should emphasize the new features in upcoming pitches."
   - "CEO announced major restructuring with 15% staff cuts. This signals budget constraints and cost-cutting mode. Sales strategy should focus on ROI and cost savings rather than premium features."
   - "Competitor Acme Corp won a major deal with Fortune 500 client. This is a competitive loss in the enterprise segment. Sales should be prepared to address why prospects might be considering Acme and highlight our advantages."

3. CATEGORY: Choose ONE from:
   - product_update: New products, features, releases, product announcements FROM {customer_name}
   - financial: Earnings, funding, revenue, financial performance, budget changes
   - market_news: Market trends, industry analysis, market position
   - competitor: Competitor actions, competitive wins/losses, comparisons
   - challenge: Problems, outages, issues, criticisms, negative press
   - opportunity: Expansion, partnerships, growth areas, new markets
   - leadership: Executive changes, org changes, strategic shifts
   - partnership: Partnerships, acquisitions, collaborations, alliances
   - advertisement: Retail ads, deals, discounts, promotions, price comparisons, consumer offers, affiliate content, "best deal" articles
   - unrelated: Different company/entity, consumer advice, general tutorials, not relevant to company intelligence
   - other: Doesn't fit above categories

4. SENTIMENT: positive, negative, neutral, or mixed
   - Consider impact on sales opportunities

5. ENTITIES: Extract mentioned entities (be thorough):
   - companies: ALL companies mentioned (including {customer_name} and competitors)
   - technologies: Specific technologies, products, platforms mentioned
   - people: Executives, leaders, key personnel mentioned

6. TAGS: 3-6 highly relevant tags for filtering/search

7. PAIN_POINTS_OPPORTUNITIES: Identify business pain points and sales opportunities:
   - pain_points: List 0-3 specific business challenges (3 WORDS MAXIMUM!!!)
     GOOD (2-3 words): "FTTN reliability issues", "Enterprise churn risk", "Cloud migration delays"
     BAD (too long): "Enterprise customers with strong ESG procurement criteria may prioritize NBN"
     BAD (too long): "Customer vulnerability to service degradation during peak demand periods"
   - opportunities: List 0-3 specific sales opportunities (3 WORDS MAXIMUM!!!)
     GOOD (2-3 words): "FTTP upgrade campaign", "Disaster recovery positioning", "Bundle migration offers"
     BAD (too long): "Opportunity to align sales messaging with NBN Co's sustainability initiatives"
     BAD (too long): "Positioning superior service quality and resilience as value drivers"

   ULTRA CRITICAL REQUIREMENTS:
   - Each entry MUST be 3 words or less - NO EXCEPTIONS!
   - Use ONLY keywords/noun phrases, NEVER full sentences
   - DO NOT combine multiple points into one entry - split them up!
   - If you have multiple ideas, create SEPARATE short entries for each
   - If you write more than 3 words, START OVER and cut it down
   - Empty arrays are better than long entries
   ONLY include if explicitly mentioned or strongly implied. If none found, use empty arrays.

8. PRIORITY_SCORE (0.0-1.0): How URGENT is this for the sales team?

   Score HIGH (0.8-1.0) if:
   - Major competitive win/loss or threat
   - Leadership changes affecting buying decisions
   - Significant product launches or partnerships
   - Financial troubles indicating risk or opportunity
   - Contains priority keywords: {', '.join(priority_keywords[:5]) if priority_keywords else 'N/A'}
   - Major outages or challenges creating sales opportunities

   Score MEDIUM (0.4-0.7) if:
   - General product updates or announcements
   - Industry news affecting customer
   - Minor partnerships or expansions
   - Routine financial news

   Score LOW (0.1-0.3) if:
   - Routine announcements with minimal impact
   - Generic industry content
   - Old news or updates

   Score 0.0 if:
   - Not relevant (is_relevant = false)
   - Advertisement, retail deal, consumer promotion, or spam
   - Price comparison or "best deal" content

CRITICAL FILTERING EXAMPLES:
- ❌ "Best NBN plans for 2025" → is_relevant: false, category: advertisement
- ❌ "Optus NBN 100 now $79/month" → is_relevant: false, category: advertisement
- ❌ "How to choose the right NBN speed tier" → is_relevant: false, category: unrelated
- ✅ "NBN Co announces major network upgrade rollout" → is_relevant: true, category: product_update
- ✅ "NBN Co CEO discusses infrastructure challenges" → is_relevant: true, category: leadership

CRITICAL: If any known competitors are mentioned, ALWAYS include them in entities.companies and consider setting category to "competitor" if they're a focus of the content.

Format response as JSON:
{{
  "is_relevant": true,
  "summary": "Actionable summary here...",
  "category": "category_name",
  "sentiment": "positive",
  "entities": {{
    "companies": ["Company1", "Company2"],
    "technologies": ["Tech1", "Tech2"],
    "people": ["Person1", "Person2"]
  }},
  "tags": ["tag1", "tag2", "tag3"],
  "pain_points_opportunities": {{
    "pain_points": ["Pain point 1", "Pain point 2"],
    "opportunities": ["Opportunity 1", "Opportunity 2"]
  }},
  "priority_score": 0.0
}}"""

    def _get_source_specific_guidance(self, source_type: str) -> str:
        """Get source-specific analysis guidance"""
        guidance_map = {
            "linkedin_user": """
===== SOURCE-SPECIFIC GUIDANCE (LinkedIn Post) =====
This is a LinkedIn post from a key executive or industry leader.
Focus on:
- Strategic insights and thought leadership
- Organizational changes or announcements
- Industry trends from their perspective
- Relationship-building opportunities (congratulate on achievements, reference their insights)
LinkedIn posts often signal strategic direction before official announcements.""",

            "news_api": """
===== SOURCE-SPECIFIC GUIDANCE (News Article) =====
This is a news article from media sources.
Focus on:
- Market impact and public perception
- Competitive positioning changes
- Crisis management opportunities
- How this affects the company's reputation and buying decisions""",

            "reddit": """
===== SOURCE-SPECIFIC GUIDANCE (Reddit Discussion) =====
This is community discussion from Reddit.
Focus on:
- Customer sentiment and pain points
- Product feedback and feature requests
- Competitive comparisons from real users
- Support issues or frustrations that create opportunities""",

            "stock": """
===== SOURCE-SPECIFIC GUIDANCE (Financial Data) =====
This is financial/stock market data.
Focus on:
- Financial health indicators
- Growth trajectory and stability
- Investment in R&D or expansion
- Budget constraints or spending changes affecting purchasing""",

            "twitter": """
===== SOURCE-SPECIFIC GUIDANCE (Twitter/X Post) =====
This is a social media post.
Focus on:
- Real-time reactions to events
- Customer service issues going viral
- Brand perception changes
- Rapid response opportunities""",
        }

        return guidance_map.get(source_type, "")

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse Claude's response into structured data

        Args:
            response_text: Response from Claude

        Returns:
            Parsed dict
        """
        try:
            # Extract JSON from response (in case Claude adds extra text)
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)

                # Validate and normalize
                return {
                    'is_relevant': data.get('is_relevant', True),
                    'summary': data.get('summary', ''),
                    'category': self._validate_category(data.get('category', 'other')),
                    'sentiment': self._validate_sentiment(data.get('sentiment', 'neutral')),
                    'entities': data.get('entities', {}),
                    'tags': data.get('tags', []),
                    'pain_points_opportunities': data.get('pain_points_opportunities', {'pain_points': [], 'opportunities': []}),
                    'priority_score': self._validate_priority(data.get('priority_score', 0.5))
                }
            else:
                logger.warning("No JSON found in Claude response")
                return self._default_result("", "")

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing Claude response as JSON: {e}")
            return self._default_result("", "")

    def _validate_category(self, category: str) -> str:
        """Validate and normalize category"""
        try:
            # Check if valid category
            CategoryType(category.lower())
            return category.lower()
        except ValueError:
            return "other"

    def _validate_sentiment(self, sentiment: str) -> str:
        """Validate and normalize sentiment"""
        try:
            SentimentType(sentiment.lower())
            return sentiment.lower()
        except ValueError:
            return "neutral"

    def _validate_priority(self, score: float) -> float:
        """Validate priority score is in range"""
        try:
            score = float(score)
            return max(0.0, min(1.0, score))
        except (TypeError, ValueError):
            return 0.5

    def _default_result(self, title: str, content: str) -> Dict[str, Any]:
        """
        Generate default result when AI processing fails

        Args:
            title: Item title
            content: Item content

        Returns:
            Default processing result
        """
        # Create a simple summary from title
        summary = title[:200] if title else content[:200]

        return {
            'is_relevant': True,
            'summary': summary,
            'category': 'other',
            'sentiment': 'neutral',
            'entities': {
                'companies': [],
                'technologies': [],
                'people': []
            },
            'tags': [],
            'pain_points_opportunities': {
                'pain_points': [],
                'opportunities': []
            },
            'priority_score': 0.5
        }

    async def batch_process(
        self,
        items: List[Dict[str, Any]],
        customer_name: str,
        keywords: List[str] = None,
        competitors: List[str] = None,
        priority_keywords: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Process multiple items in batch

        Args:
            items: List of items with title, content, source_type
            customer_name: Customer name
            keywords: Customer keywords for relevance checking
            competitors: List of competitor names
            priority_keywords: Keywords that indicate high priority

        Returns:
            List of processing results
        """
        results = []

        for item in items:
            result = await self.process_item(
                title=item.get('title', ''),
                content=item.get('content', ''),
                customer_name=customer_name,
                source_type=item.get('source_type', 'unknown'),
                keywords=keywords,
                competitors=competitors,
                priority_keywords=priority_keywords
            )
            results.append(result)

        return results


# Global instance
_ai_processor: Optional[AIProcessor] = None


def get_ai_processor(db: Optional[Session] = None) -> AIProcessor:
    """
    Get or create AI processor instance

    Args:
        db: Optional database session to fetch model config from platform settings.
            If provided, creates a new instance with the latest model config.
            If None, returns cached instance with default model.
    """
    global _ai_processor

    # If db session provided, create new instance to get latest model config
    if db:
        return AIProcessor(db)

    # Otherwise use cached instance
    if _ai_processor is None:
        _ai_processor = AIProcessor()
    return _ai_processor
