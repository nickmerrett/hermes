"""Analytics API endpoints"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from anthropic import Anthropic
from typing import Optional

from app.core.database import get_db
from app.models import schemas
from app.models.database import IntelligenceItem, ProcessedIntelligence, Customer, DailySummary, PlatformSettings
from app.config.settings import settings
from app.core.prompt_loader import load_prompt_template, PromptTemplate
import logging

logger = logging.getLogger(__name__)

# Import OpenAI (optional)
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI package not installed. OpenAI models will not be available for daily summaries.")
router = APIRouter()


def _create_ai_client_from_model_config(model_config):
    """Helper to create AI client from template model config"""
    if model_config.provider == 'anthropic':
        if not model_config.api_key:
            raise ValueError(f"{model_config.api_key_env} not configured")
        return Anthropic(api_key=model_config.api_key, base_url=model_config.api_base), 'anthropic'
    elif model_config.provider in ['openai', 'lmstudio']:
        if not OPENAI_AVAILABLE:
            raise ValueError("OpenAI package not installed")
        api_key = model_config.api_key if model_config.api_key else "lm-studio"
        return OpenAI(api_key=api_key, base_url=model_config.api_base), 'openai'
    else:
        raise ValueError(f"Unknown provider: {model_config.provider}")


@router.get("/summary", response_model=schemas.AnalyticsSummary)
async def get_analytics_summary(db: Session = Depends(get_db)):
    """Get analytics summary across all intelligence items"""

    # Total items
    total_items = db.query(IntelligenceItem).count()

    # Items by category
    category_counts = db.query(
        ProcessedIntelligence.category,
        func.count(ProcessedIntelligence.id)
    ).group_by(ProcessedIntelligence.category).all()
    items_by_category = {cat: count for cat, count in category_counts if cat}

    # Items by sentiment
    sentiment_counts = db.query(
        ProcessedIntelligence.sentiment,
        func.count(ProcessedIntelligence.id)
    ).group_by(ProcessedIntelligence.sentiment).all()
    items_by_sentiment = {sent: count for sent, count in sentiment_counts if sent}

    # Items by source
    source_counts = db.query(
        IntelligenceItem.source_type,
        func.count(IntelligenceItem.id)
    ).group_by(IntelligenceItem.source_type).all()
    items_by_source = {src: count for src, count in source_counts}

    # Recent items (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_items_count = db.query(IntelligenceItem).filter(
        IntelligenceItem.collected_date >= yesterday
    ).count()

    # High priority items (priority > 0.7)
    high_priority_items = db.query(ProcessedIntelligence).filter(
        ProcessedIntelligence.priority_score > 0.7
    ).count()

    # Number of customers
    customers_monitored = db.query(Customer).count()

    return schemas.AnalyticsSummary(
        total_items=total_items,
        items_by_category=items_by_category,
        items_by_sentiment=items_by_sentiment,
        items_by_source=items_by_source,
        recent_items_count=recent_items_count,
        high_priority_items=high_priority_items,
        customers_monitored=customers_monitored
    )


@router.get("/daily-summary/{customer_id}")
async def get_daily_summary(customer_id: int, db: Session = Depends(get_db)):
    """Get daily summary of items collected in the last 24 hours for a specific customer"""

    yesterday = datetime.utcnow() - timedelta(days=1)

    # Get items from last 24 hours for this customer
    recent_items = db.query(IntelligenceItem).join(
        ProcessedIntelligence,
        IntelligenceItem.id == ProcessedIntelligence.item_id,
        isouter=True
    ).filter(
        IntelligenceItem.customer_id == customer_id,
        IntelligenceItem.collected_date >= yesterday
    ).order_by(
        ProcessedIntelligence.priority_score.desc().nullslast(),
        IntelligenceItem.collected_date.desc()
    ).limit(20).all()

    # Count by category
    category_counts = db.query(
        ProcessedIntelligence.category,
        func.count(ProcessedIntelligence.id)
    ).join(
        IntelligenceItem,
        IntelligenceItem.id == ProcessedIntelligence.item_id
    ).filter(
        IntelligenceItem.customer_id == customer_id,
        IntelligenceItem.collected_date >= yesterday
    ).group_by(ProcessedIntelligence.category).all()

    # Count high priority items
    high_priority_count = db.query(IntelligenceItem).join(
        ProcessedIntelligence,
        IntelligenceItem.id == ProcessedIntelligence.item_id
    ).filter(
        IntelligenceItem.customer_id == customer_id,
        IntelligenceItem.collected_date >= yesterday,
        ProcessedIntelligence.priority_score >= 0.7
    ).count()

    return {
        "customer_id": customer_id,
        "period": "last_24_hours",
        "total_items": len(recent_items),
        "high_priority_count": high_priority_count,
        "items_by_category": {cat: count for cat, count in category_counts if cat},
        "recent_items": [
            {
                "id": item.id,
                "title": item.title,
                "summary": item.processed.summary if item.processed else None,
                "category": item.processed.category if item.processed else None,
                "priority_score": item.processed.priority_score if item.processed else None,
                "sentiment": item.processed.sentiment if item.processed else None,
                "url": item.url,
                "published_date": item.published_date,
                "collected_date": item.collected_date,
                "source_type": item.source_type
            }
            for item in recent_items
        ]
    }


@router.get("/daily-summary-ai/{customer_id}")
async def get_daily_summary_ai(
    customer_id: int,
    force_refresh: bool = False,
    persona: str = None,
    custom_persona_text: str = None,
    db: Session = Depends(get_db)
):
    """
    Get or generate an AI-powered textual summary of the last 24 hours for a customer

    Args:
        customer_id: Customer ID
        force_refresh: If True, bypass cache and regenerate summary
        persona: Persona key to use from template (e.g., 'executive', 'technical', 'sales')
        custom_persona_text: Custom persona instructions (overrides persona key)
        db: Database session
    """

    # Get customer info
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        return {"error": "Customer not found"}

    # Check for cached summary (from today only)
    if not force_refresh:
        # Only use cache from today (not old summaries)
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today = datetime.utcnow().date()

        cached_summary = db.query(DailySummary).filter(
            DailySummary.customer_id == customer_id,
            DailySummary.generated_at >= today_start,  # Only today's summaries
            func.date(DailySummary.summary_date) == today
        ).order_by(DailySummary.generated_at.desc()).first()

        if cached_summary:
            logger.info(f"Returning cached daily summary for {customer.name} (generated {cached_summary.generated_at})")
            return {
                "customer_id": customer_id,
                "customer_name": customer.name,
                "period": "last_24_hours",
                "total_items": cached_summary.total_items,
                "high_priority_count": cached_summary.high_priority_count,
                "items_by_category": cached_summary.items_by_category or {},
                "summary": cached_summary.summary_text,
                "cached": True,
                "generated_at": cached_summary.generated_at
            }

    # If force_refresh or no cache from today, return None to trigger placeholder
    # Frontend will show "No summary generated for today"
    if not force_refresh:
        logger.info(f"No summary found for {customer.name} today - returning null to show placeholder")
        return None

    # No cache or forced refresh - generate new summary
    yesterday = datetime.utcnow() - timedelta(days=1)

    # Get items from last 24 hours for this customer
    recent_items = db.query(IntelligenceItem).join(
        ProcessedIntelligence,
        IntelligenceItem.id == ProcessedIntelligence.item_id,
        isouter=True
    ).filter(
        IntelligenceItem.customer_id == customer_id,
        IntelligenceItem.collected_date >= yesterday
    ).order_by(
        ProcessedIntelligence.priority_score.desc().nullslast(),
        IntelligenceItem.collected_date.desc()
    ).limit(50).all()  # Get top 50 for summarization

    if not recent_items:
        return {
            "customer_id": customer_id,
            "customer_name": customer.name,
            "period": "last_24_hours",
            "total_items": 0,
            "summary": f"No new intelligence items were collected for {customer.name} in the last 24 hours."
        }

    # Prepare items for AI summarization
    items_text = []
    for idx, item in enumerate(recent_items[:20], 1):  # Limit to top 20 for token usage
        priority = "HIGH" if item.processed and item.processed.priority_score >= 0.7 else "MEDIUM" if item.processed and item.processed.priority_score >= 0.5 else "LOW"
        category = item.processed.category if item.processed else "unknown"
        sentiment = item.processed.sentiment if item.processed else "neutral"
        summary = item.processed.summary if item.processed else item.title

        items_text.append(
            f"{idx}. [{priority}] [{category}] {item.title}\n"
            f"   Summary: {summary}\n"
            f"   Sentiment: {sentiment}\n"
            f"   Source: {item.source_type}"
        )

    # Group by category for context
    category_counts = {}
    for item in recent_items:
        if item.processed:
            cat = item.processed.category
            category_counts[cat] = category_counts.get(cat, 0) + 1

    # Generate AI summary
    try:
        if not settings.anthropic_api_key:
            return {
                "customer_id": customer_id,
                "customer_name": customer.name,
                "period": "last_24_hours",
                "total_items": len(recent_items),
                "summary": "AI summarization is not available (API key not configured)."
            }

        # Get model from environment variables (or UI override if enabled)
        premium_model = settings.ai_model  # Default from env

        # Only check database for model override if MODEL_OVERRIDE_IN_UI is enabled
        if settings.model_override_in_ui:
            ai_config_settings = db.query(PlatformSettings).filter(
                PlatformSettings.key == 'ai_config'
            ).first()
            if ai_config_settings and isinstance(ai_config_settings.value, dict):
                config = ai_config_settings.value
                premium_model = config.get('model', settings.ai_model)

        # Load template system if configured
        template: Optional[PromptTemplate] = None
        if settings.ai_prompt_template:
            # Load template - raise error if it fails
            template = load_prompt_template(settings.ai_prompt_template)
            logger.info(f"Using prompt template for daily summary: {settings.ai_prompt_template}")

        # MODE 1: Template system
        if template:
            try:
                # Format items for template
                items_formatted = chr(10).join(items_text)
                categories_formatted = ', '.join([f"{cat} ({count})" for cat, count in category_counts.items()])
                high_priority = sum(1 for item in recent_items if item.processed and item.processed.priority_score >= 0.7)

                # Determine persona instructions
                persona_instructions = ""
                if custom_persona_text:
                    # Custom persona text provided - use it directly
                    persona_instructions = custom_persona_text
                    logger.info(f"Using custom persona text for daily summary")
                elif persona:
                    # Persona key provided - lookup from template
                    try:
                        persona_instructions = template.get_persona(persona)
                        logger.info(f"Using persona '{persona}' from template for daily summary")
                    except ValueError as e:
                        logger.warning(f"Persona '{persona}' not found in template, using default: {e}")
                        # Fall back to no persona instructions
                        persona_instructions = ""

                # Get prompt and model from template
                prompt, model_config = template.format_prompt(
                    'daily_summary',
                    customer_name=customer.name,
                    total_items=len(recent_items),
                    high_priority_count=high_priority,
                    categories=categories_formatted,
                    items=items_formatted,
                    persona_instructions=persona_instructions
                )

                # Create client from model config
                client, client_type = _create_ai_client_from_model_config(model_config)
                premium_model = model_config.model_name
                max_tokens = model_config.max_tokens

                logger.info(f"Generated daily summary prompt using template with model {premium_model}")

            except Exception as e:
                logger.error(f"Error using template for daily summary: {e}")
                return {
                    "customer_id": customer_id,
                    "customer_name": customer.name,
                    "period": "last_24_hours",
                    "total_items": len(recent_items),
                    "summary": f"AI summarization failed: {str(e)}"
                }

        # MODE 2: Legacy configuration
        else:
            # Get custom prompt from platform settings if available
            briefing_settings = db.query(PlatformSettings).filter(
                PlatformSettings.key == 'daily_briefing'
            ).first()

            # Get provider from environment settings (premium model for daily summaries)
            provider = settings.ai_provider

            # Initialize the appropriate client based on provider
            if provider == 'anthropic':
                if not settings.anthropic_api_key:
                    return {
                        "customer_id": customer_id,
                        "customer_name": customer.name,
                        "period": "last_24_hours",
                        "total_items": len(recent_items),
                        "summary": "AI summarization is not available (ANTHROPIC_API_KEY not configured)."
                    }
                client = Anthropic(
                    api_key=settings.anthropic_api_key,
                    base_url=settings.anthropic_api_base_url
                )
                client_type = 'anthropic'
            elif provider == 'openai':
                if not OPENAI_AVAILABLE:
                    return {
                        "customer_id": customer_id,
                        "customer_name": customer.name,
                        "period": "last_24_hours",
                        "total_items": len(recent_items),
                        "summary": "AI summarization is not available (OpenAI package not installed. Run: pip install openai)."
                    }
                if not settings.openai_api_key:
                    return {
                        "customer_id": customer_id,
                        "customer_name": customer.name,
                        "period": "last_24_hours",
                        "total_items": len(recent_items),
                        "summary": "AI summarization is not available (OPENAI_API_KEY not configured)."
                    }
                client = OpenAI(
                    api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url
                )
                client_type = 'openai'
            else:
                return {
                    "customer_id": customer_id,
                    "customer_name": customer.name,
                    "period": "last_24_hours",
                    "total_items": len(recent_items),
                    "summary": f"AI summarization is not available (Unknown provider: {provider}. Set AI_PROVIDER to 'anthropic' or 'openai')."
                }

            # Use custom prompt or fall back to default
            if briefing_settings and briefing_settings.value.get('prompt'):
                custom_instructions = briefing_settings.value['prompt']
            else:
                # Default prompt
                custom_instructions = """Generate a concise daily briefing summarizing the key intelligence collected today. Focus on:
- Most important developments
- Emerging trends and patterns
- Notable competitor activities
- Strategic opportunities and risks

Keep the summary professional, actionable, and under 300 words."""

            # Build the full prompt with context
            prompt = f"""You are an executive intelligence briefing assistant. Generate a daily briefing for {customer.name} based on the intelligence collected in the last 24 hours.

**Intelligence Overview:**
- Total items collected: {len(recent_items)}
- High priority items: {sum(1 for item in recent_items if item.processed and item.processed.priority_score >= 0.7)}
- Categories: {', '.join([f"{cat} ({count})" for cat, count in category_counts.items()])}

**Top Intelligence Items:**
{chr(10).join(items_text)}

**Your Task:**
{custom_instructions}

Write the briefing now:"""
            max_tokens = 1200

        # Call AI API based on provider
        if client_type == 'anthropic':
            response = client.messages.create(
                model=premium_model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            summary_text = response.content[0].text
        elif client_type == 'openai':
            response = client.chat.completions.create(
                model=premium_model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            summary_text = response.choices[0].message.content
        else:
            raise ValueError(f"Unknown client type: {client_type}")

        # Save summary to database
        summary_record = DailySummary(
            customer_id=customer_id,
            summary_date=datetime.utcnow(),
            summary_text=summary_text,
            total_items=len(recent_items),
            high_priority_count=sum(1 for item in recent_items if item.processed and item.processed.priority_score >= 0.7),
            items_by_category=category_counts
        )
        db.add(summary_record)
        db.commit()
        db.refresh(summary_record)

        logger.info(f"Generated and saved new daily summary for {customer.name}")

        return {
            "customer_id": customer_id,
            "customer_name": customer.name,
            "period": "last_24_hours",
            "total_items": len(recent_items),
            "high_priority_count": sum(1 for item in recent_items if item.processed and item.processed.priority_score >= 0.7),
            "items_by_category": category_counts,
            "summary": summary_text,
            "cached": False,
            "generated_at": summary_record.generated_at
        }

    except Exception as e:
        logger.error(f"Error generating AI summary: {e}")
        return {
            "customer_id": customer_id,
            "customer_name": customer.name,
            "period": "last_24_hours",
            "total_items": len(recent_items),
            "summary": f"Error generating AI summary: {str(e)}"
        }
