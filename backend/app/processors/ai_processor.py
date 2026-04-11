"""AI processor for summarization and classification using Claude or OpenAI API"""

from typing import Dict, Any, List, Optional, Tuple
import json
import logging
import asyncio
import time
from anthropic import Anthropic
import re
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.schemas import CategoryType, SentimentType
from app.models.database import PlatformSettings
from app.core.prompt_loader import load_prompt_template, PromptTemplate, ModelConfig

logger = logging.getLogger(__name__)

# Timeout configuration for AI API calls
AI_API_TIMEOUT = 60.0  # 60 seconds per API call
AI_PROCESSING_TIMEOUT = 120.0  # 120 seconds total including retries

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
        """
        Initialize AIProcessor with either template system or legacy configuration

        If AI_PROMPT_TEMPLATE is set, load the template which defines all prompts
        and their individual model configurations. Otherwise, use legacy
        individual model settings from environment variables.
        """
        # Initialize circuit breaker for all modes (must be before early return)
        self.consecutive_failures = 0
        self.max_failures_before_circuit_break = 5
        self.circuit_broken = False
        self.circuit_break_time = None
        self.circuit_break_reset_seconds = 300  # Reset after 5 minutes
        
        # Try to load prompt template if configured
        self.template: Optional[PromptTemplate] = None
        if settings.ai_prompt_template:
            # Load template - raise error if it fails
            self.template = load_prompt_template(settings.ai_prompt_template)
            logger.info(f"Using prompt template: {settings.ai_prompt_template}")
            # Template mode - clients will be created dynamically per-prompt
            self.client = None
            self.client_type = None
            self.model = None
            self.model_tier = None
            self.provider = None
            self.max_tokens = None
            return  # Early return - template mode configured

        # Legacy mode - individual model configuration
        # Get model name from platform settings (for article processing = cheap model)
        # Provider config comes from environment variables
        self.model = settings.ai_model_cheap  # default from env
        self.model_tier = settings.ai_model_tier_cheap  # default from env

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
                base_url=settings.anthropic_api_base_url,
                timeout=AI_API_TIMEOUT  # Add timeout to prevent hanging
            )
            self.client_type = 'anthropic'
        elif self.provider == 'openai':
            if not OPENAI_AVAILABLE:
                raise ValueError("OpenAI package not installed. Run: pip install openai")
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY not configured")
            self.client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                timeout=AI_API_TIMEOUT  # Add timeout to prevent hanging
            )
            self.client_type = 'openai'
        else:
            raise ValueError(f"Unknown AI provider: {self.provider}. Set AI_PROVIDER_CHEAP to 'anthropic' or 'openai'")

        self.max_tokens = settings.max_tokens_summary
        # Circuit breaker already initialized at start of __init__

    def _create_client(self, model_config: ModelConfig) -> Tuple[Any, str]:
        """
        Create an AI client dynamically based on model configuration

        Args:
            model_config: ModelConfig from prompt template

        Returns:
            Tuple of (client, client_type)
        """
        if model_config.provider == 'anthropic':
            if not model_config.api_key:
                raise ValueError(f"{model_config.api_key_env} not configured")
            client = Anthropic(
                api_key=model_config.api_key,
                base_url=model_config.api_base,
                timeout=AI_API_TIMEOUT  # Add timeout to prevent hanging
            )
            return client, 'anthropic'

        elif model_config.provider == 'openai' or model_config.provider == 'lmstudio':
            # Both OpenAI and LM Studio use OpenAI-compatible API
            if not OPENAI_AVAILABLE:
                raise ValueError("OpenAI package not installed. Run: pip install openai")

            # LM Studio doesn't need an API key
            api_key = model_config.api_key if model_config.api_key else "lm-studio"

            client = OpenAI(
                api_key=api_key,
                base_url=model_config.api_base,
                timeout=AI_API_TIMEOUT  # Add timeout to prevent hanging
            )
            return client, 'openai'

        else:
            raise ValueError(f"Unknown provider: {model_config.provider}")

    def _call_ai(self, client: Any, client_type: str, model_name: str, prompt: str, max_tokens: int) -> str:
        """
        Make an AI API call (synchronous - will be wrapped in async context)

        Args:
            client: AI client (Anthropic or OpenAI)
            client_type: 'anthropic' or 'openai'
            model_name: Model name to use
            prompt: Prompt text
            max_tokens: Max tokens in response

        Returns:
            Response text from AI
            
        Note: This method is synchronous but will be called via asyncio.to_thread()
              to prevent blocking the event loop. Timeouts are configured on the
              client initialization.
        """
        start_time = time.time()
        
        try:
            if client_type == 'anthropic':
                response = client.messages.create(
                    model=model_name,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}]
                )
                result = response.content[0].text
            elif client_type == 'openai':
                response = client.chat.completions.create(
                    model=model_name,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}]
                )
                result = response.choices[0].message.content
            else:
                raise ValueError(f"Unknown client type: {client_type}")
            
            duration = time.time() - start_time
            logger.debug(f"AI API call completed in {duration:.2f}s (model: {model_name})")
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"AI API call failed after {duration:.2f}s: {e}")
            raise

    async def _call_ai_async(self, client: Any, client_type: str, model_name: str, prompt: str, max_tokens: int) -> str:
        """
        Async wrapper for AI API calls with timeout protection
        
        Runs the synchronous _call_ai in a thread pool to prevent blocking
        the event loop, with an additional timeout layer for safety.
        
        Args:
            client: AI client (Anthropic or OpenAI)
            client_type: 'anthropic' or 'openai'
            model_name: Model name to use
            prompt: Prompt text
            max_tokens: Max tokens in response
            
        Returns:
            Response text from AI
            
        Raises:
            asyncio.TimeoutError: If the call exceeds AI_PROCESSING_TIMEOUT
        """
        try:
            # Run synchronous AI call in thread pool with timeout
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    self._call_ai, client, client_type, model_name, prompt, max_tokens
                ),
                timeout=AI_PROCESSING_TIMEOUT
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"AI processing timeout after {AI_PROCESSING_TIMEOUT}s for model {model_name}")
            raise Exception(f"AI processing timeout after {AI_PROCESSING_TIMEOUT} seconds")

    def _extract_json_from_text(self, text: str) -> str:
        """
        Extract JSON from AI response text

        Handles responses that may have markdown code blocks or extra text
        """
        import re

        # Try to find JSON in markdown code block
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            return json_match.group(1)

        # Try to find raw JSON object
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json_match.group(0)

        # If nothing found, return the text as-is and let JSON parser fail
        return text.strip()

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
        # Check circuit breaker
        if self.circuit_broken:
            # Check if enough time has passed to reset
            if self.circuit_break_time and (time.time() - self.circuit_break_time) > self.circuit_break_reset_seconds:
                logger.info("Circuit breaker RESET - attempting to resume AI processing")
                self.circuit_broken = False
                self.consecutive_failures = 0
                self.circuit_break_time = None
            else:
                logger.warning("Circuit breaker OPEN - skipping AI processing, using defaults")
                return self._default_result(title, content)
        
        try:
            # MODE 1: Template system - 3-stage pipeline
            if self.template:
                # Prepare template variables
                keywords_text = f"Keywords: {', '.join(keywords or [])}" if keywords else ""
                competitors_text = f"Competitors: {', '.join(competitors or [])}" if competitors else ""
                content_truncated = content[:3500] if content else ""

                # ===== STAGE 1: RELEVANCE CHECK (Fast Filter) =====
                logger.debug(f"Stage 1: Relevance check for '{title[:50]}...'")

                relevance_prompt, relevance_model = self.template.format_prompt(
                    'relevance_check',
                    customer_name=customer_name,
                    title=title,
                    content=content_truncated,
                    keywords_text=keywords_text,
                    competitors_text=competitors_text
                )

                relevance_client, relevance_client_type = self._create_client(relevance_model)
                relevance_response = await self._call_ai_async(
                    relevance_client,
                    relevance_client_type,
                    relevance_model.model_name,
                    relevance_prompt,
                    relevance_model.max_tokens
                )
                relevance_data = json.loads(self._extract_json_from_text(relevance_response))

                # If not relevant, return immediately (save API costs)
                if not relevance_data.get('is_relevant', False):
                    logger.debug(f"Stage 1: Not relevant - {relevance_data.get('reason', 'N/A')}")
                    return {
                        'is_relevant': False,
                        'summary': relevance_data.get('reason', 'Not relevant to company'),
                        'category': 'unrelated',
                        'sentiment': 'neutral',
                        'entities': {'companies': [], 'technologies': [], 'people': []},
                        'tags': [],
                        'pain_points_opportunities': {'pain_points': [], 'opportunities': []},
                        'priority_score': 0.0
                    }

                logger.debug(f"Stage 1: Relevant - {relevance_data.get('reason', 'N/A')}")

                # ===== STAGE 2: CORE ANALYSIS =====
                logger.debug("Stage 2: Core analysis")

                core_prompt, core_model = self.template.format_prompt(
                    'core_analysis',
                    customer_name=customer_name,
                    title=title,
                    content=content_truncated,
                    source_type=source_type,
                    keywords_text=keywords_text,
                    competitors_text=competitors_text
                )

                core_client, core_client_type = self._create_client(core_model)
                core_response = await self._call_ai_async(
                    core_client,
                    core_client_type,
                    core_model.model_name,
                    core_prompt,
                    core_model.max_tokens
                )
                core_data = json.loads(self._extract_json_from_text(core_response))

                # Build result from core analysis
                result = {
                    'is_relevant': True,
                    'summary': core_data.get('summary', ''),
                    'category': core_data.get('category', 'other'),
                    'sentiment': core_data.get('sentiment', 'neutral'),
                    'entities': core_data.get('entities', {'companies': [], 'technologies': [], 'people': []}),
                    'tags': core_data.get('tags', []),
                    'priority_score': core_data.get('priority_score', 0.5),
                    'pain_points_opportunities': {'pain_points': [], 'opportunities': []}
                }

                # ===== STAGE 3: BUSINESS INSIGHTS (High-Value Only) =====
                # Only run for high-priority items to save API costs
                if result['priority_score'] >= 0.6:
                    logger.debug(f"Stage 3: Business insights (priority={result['priority_score']:.2f})")

                    try:
                        insights_prompt, insights_model = self.template.format_prompt(
                            'business_insights',
                            customer_name=customer_name,
                            title=title,
                            summary=result['summary'],
                            category=result['category']
                        )

                        insights_client, insights_client_type = self._create_client(insights_model)
                        insights_response = await self._call_ai_async(
                            insights_client,
                            insights_client_type,
                            insights_model.model_name,
                            insights_prompt,
                            insights_model.max_tokens
                        )
                        insights_data = json.loads(self._extract_json_from_text(insights_response))

                        result['pain_points_opportunities'] = {
                            'pain_points': insights_data.get('pain_points', []),
                            'opportunities': insights_data.get('opportunities', [])
                        }
                        logger.debug(f"Stage 3: Extracted {len(result['pain_points_opportunities']['pain_points'])} pain points, "
                                   f"{len(result['pain_points_opportunities']['opportunities'])} opportunities")
                    except Exception as e:
                        logger.warning(f"Stage 3 failed, continuing without insights: {e}")
                        # Continue with empty insights on error
                else:
                    logger.debug(f"Stage 3: Skipped (priority={result['priority_score']:.2f} < 0.6)")

                logger.debug(f"3-stage pipeline completed for '{title[:50]}...'")
                
                # Reset failure counter on success
                self.consecutive_failures = 0
                
                return result

            # MODE 2: Legacy configuration - use hardcoded prompts and pre-initialized client
            else:
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
                
                # Use async wrapper for legacy mode too
                response_text = await self._call_ai_async(
                    self.client,
                    self.client_type,
                    self.model,
                    prompt,
                    self.max_tokens
                )

            # Parse response
            result = self._parse_response(response_text)

            # Validate relevance claim against actual content
            if result['is_relevant']:
                result = self._validate_relevance_claim(
                    result,
                    title,
                    content,
                    customer_name,
                    keywords
                )

            logger.debug(f"Processed item: {title[:50]}...")
            
            # Reset failure counter on success
            self.consecutive_failures = 0
            
            return result

        except asyncio.TimeoutError:
            # Handle timeout specifically
            self.consecutive_failures += 1
            logger.error(f"AI processing timeout (failure {self.consecutive_failures}/{self.max_failures_before_circuit_break})")
            
            if self.consecutive_failures >= self.max_failures_before_circuit_break:
                self.circuit_broken = True
                self.circuit_break_time = time.time()
                logger.error(f"Circuit breaker OPENED after {self.consecutive_failures} consecutive failures")
            
            # Return default values on timeout
            return self._default_result(title, content)
            
        except Exception as e:
            self.consecutive_failures += 1
            logger.error(f"Error processing item with AI (failure {self.consecutive_failures}/{self.max_failures_before_circuit_break}): {e}")
            
            if self.consecutive_failures >= self.max_failures_before_circuit_break:
                self.circuit_broken = True
                self.circuit_break_time = time.time()
                logger.error(f"Circuit breaker OPENED after {self.consecutive_failures} consecutive failures")
            
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
        # Route to appropriate prompt based on model tier
        if self.model_tier == "small":
            return self._build_prompt_small(
                title, content, customer_name, source_type,
                keywords, competitors, priority_keywords, is_trusted_source
            )
        else:
            return self._build_prompt_frontier(
                title, content, customer_name, source_type,
                keywords, competitors, priority_keywords, is_trusted_source
            )

    def _build_prompt_frontier(
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
        """Build detailed prompt for frontier models (Sonnet, GPT-4, Opus)"""
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
   - market_news: Market trends, market position, analyst reports directly about customer or their market segment
   - industry_trend: Broader industry-wide trends, technology adoption, spending patterns, regulatory shifts — relevant to customer's sector even without direct customer mention
   - competitor: Competitor actions, competitive wins/losses, comparisons, regulatory/ESG/financial pressure on competitors, strategic moves by companies in the same space
   - challenge: Problems, outages, issues, criticisms, negative press
   - opportunity: Expansion, partnerships, growth areas, new markets
   - leadership: Executive changes, org changes, strategic shifts
   - partnership: Partnerships, acquisitions, collaborations, alliances
   - advertisement: Retail ads, deals, discounts, promotions, price comparisons, consumer offers, affiliate content, "best deal" articles
   - unrelated: Completely different industry/entity with no connection to customer, consumer advice, general tutorials, lifestyle content. Do NOT use for general industry trends or competitor news even if customer isn't mentioned.
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
- ✅ "Enterprises won't quit AI spending even without proven ROI" → is_relevant: true, category: industry_trend (sector-wide spending pattern)
- ✅ "AWS faces shareholder pressure over carbon disclosure" → is_relevant: true, category: competitor (regulatory/ESG pressure on a direct competitor)
- ✅ "Cloud spending up 30% as enterprises accelerate migration" → is_relevant: true, category: industry_trend (broad adoption trend relevant to sector)

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

    def _build_prompt_small(
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
        """Build simplified prompt for small models (Haiku, GPT-3.5, local models)"""

        # Build simple context
        keywords_text = f"Keywords: {', '.join(keywords[:5])}" if keywords else ""
        competitors_text = f"Competitors: {', '.join(competitors[:5])}" if competitors else ""

        return f"""Analyze this article about {customer_name}.

CONTENT:
Title: {title}
Text: {content[:2500]}

{keywords_text}
{competitors_text}

TASK: Output JSON ONLY with these fields:

1. "is_relevant": true or false
   - FIRST: Check if "{customer_name}" appears in the title or content
   - If NOT mentioned → MUST be false
   - If mentioned → true only if it's real company news (not ads/deals)

2. "summary": 2-3 sentences explaining what happened and why it matters

3. "category": ONE of these:
   product_update, financial, market_news, industry_trend, competitor, challenge, opportunity, leadership, partnership, advertisement, unrelated, other

4. "sentiment": positive, negative, neutral, or mixed

5. "entities": Extract these:
   {{"companies": ["list all companies"], "technologies": ["list tech/products"], "people": ["list people"]}}

6. "tags": List 3-5 relevant tags

7. "pain_points_opportunities":
   {{"pain_points": ["2-3 words", "2-3 words"], "opportunities": ["2-3 words", "2-3 words"]}}

   CRITICAL: Each item must be 2-3 words MAXIMUM. Examples:
   GOOD: "Network outage", "Budget cuts", "Market expansion"
   BAD: "Customers experiencing service issues" (too long!)

   If none found, use empty arrays: {{"pain_points": [], "opportunities": []}}

8. "priority_score": Number from 0.0 to 1.0
   - 0.8-1.0: Major news (leadership changes, big launches, competitive threats)
   - 0.4-0.7: Normal news (product updates, partnerships)
   - 0.1-0.3: Minor news
   - 0.0: Not relevant or ads

IMPORTANT:
- Output ONLY valid JSON, no other text
- If {customer_name} not mentioned → is_relevant MUST be false
- Pain points/opportunities: 2-3 words each, NO sentences

JSON:"""

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
                    'pain_points_opportunities': self._validate_pain_points_opportunities(data.get('pain_points_opportunities', {'pain_points': [], 'opportunities': []})),
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

    def _validate_relevance_claim(
        self,
        result: dict,
        title: str,
        content: str,
        customer_name: str,
        keywords: List[str]
    ) -> dict:
        """
        Validate that the AI's relevance claim is supported by actual mentions
        in the content. This prevents models from hallucinating relevance.
        """
        # Combine title and content for searching
        full_text = f"{title}\n{content or ''}".lower()

        # Check if customer name appears in content
        customer_name_lower = customer_name.lower()
        customer_mentioned = customer_name_lower in full_text

        # Check if any keywords appear in content
        keyword_mentioned = False
        if keywords:
            keyword_mentioned = any(keyword.lower() in full_text for keyword in keywords)

        # If neither customer name nor keywords appear, this is a hallucination
        if not customer_mentioned and not keyword_mentioned:
            logger.warning(
                f"Model claimed relevance but '{customer_name}' and keywords not found in content. "
                f"Title: {title[:100]}... - Marking as irrelevant."
            )
            result['is_relevant'] = False
            result['priority_score'] = 0.0
            result['category'] = 'unrelated'
            result['summary'] = f"Content does not actually mention {customer_name} or related keywords."

        return result

    def _validate_pain_points_opportunities(self, data) -> dict:
        """Validate pain_points_opportunities structure"""
        # If None, return empty structure
        if data is None:
            return {'pain_points': [], 'opportunities': []}

        # If it's a list (wrong format from model), log warning and return empty structure
        if isinstance(data, list):
            logger.warning(f"Model returned pain_points_opportunities as list instead of dict: {data}")
            return {'pain_points': [], 'opportunities': []}

        # If it's a dict, validate structure
        if isinstance(data, dict):
            pain_points = data.get('pain_points', [])
            opportunities = data.get('opportunities', [])

            # Ensure both are lists
            if not isinstance(pain_points, list):
                logger.warning(f"pain_points is not a list: {type(pain_points)}")
                pain_points = []
            if not isinstance(opportunities, list):
                logger.warning(f"opportunities is not a list: {type(opportunities)}")
                opportunities = []

            # Ensure all items are strings
            pain_points = [str(p) for p in pain_points if p]
            opportunities = [str(o) for o in opportunities if o]

            return {
                'pain_points': pain_points,
                'opportunities': opportunities
            }

        # Unknown format, log warning and return empty
        logger.warning(f"Unknown pain_points_opportunities format: {type(data)}")
        return {'pain_points': [], 'opportunities': []}

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

