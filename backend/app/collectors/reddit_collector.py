"""Reddit collector for monitoring subreddit mentions and discussions"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
import asyncpraw
from asyncpraw.exceptions import AsyncPRAWException
from anthropic import Anthropic
from sqlalchemy.orm import Session

from app.collectors.base import RateLimitedCollector
from app.models.schemas import IntelligenceItemCreate
from app.models.database import PlatformSettings
from app.config.settings import settings


def get_reddit_settings(db: Session = None) -> Dict[str, Any]:
    """
    Get Reddit collector settings from database

    Returns default settings if database not available or not configured
    """
    if db:
        try:
            setting = db.query(PlatformSettings).filter(
                PlatformSettings.key == 'collector_config'
            ).first()

            if setting and setting.value and 'reddit' in setting.value:
                return setting.value['reddit']
        except Exception as e:
            # Database might not be available during initialization
            pass

    # Return defaults
    return {
        'min_upvotes': 5,
        'min_comments': 3,
        'large_thread_threshold': 10,
        'max_comments_analyze': 15,
        'posts_per_subreddit': 10,
        'lookback_days': 7
    }


class RedditCollector(RateLimitedCollector):
    """
    Collector for Reddit mentions and discussions

    Monitors:
    - Subreddit mentions of company/keywords
    - Relevant discussions
    - Product launches and reviews

    Features:
    - Engagement filtering (min upvotes/comments)
    - AI-powered thread summarization for large discussions
    - Quality filtering (spam, deleted posts)

    Settings are configurable via platform settings (collector_config.reddit)
    """

    def __init__(self, customer_config: Dict[str, Any], db: Session = None):
        super().__init__(customer_config, rate_limit=60)

        # Store Reddit API credentials
        self.reddit_client_id = settings.reddit_client_id
        self.reddit_client_secret = settings.reddit_client_secret
        self.reddit_user_agent = settings.reddit_user_agent or 'CustomerIntelligenceTool/1.0'

        # Initialize Anthropic client for thread summarization
        self.anthropic = Anthropic(api_key=settings.anthropic_api_key)

        # Load configurable settings from database
        reddit_settings = get_reddit_settings(db)
        self.MIN_UPVOTES = reddit_settings.get('min_upvotes', 5)
        self.MIN_COMMENTS = reddit_settings.get('min_comments', 3)
        self.LARGE_THREAD_THRESHOLD = reddit_settings.get('large_thread_threshold', 10)
        self.MAX_COMMENTS_TO_ANALYZE = reddit_settings.get('max_comments_analyze', 15)
        self.posts_per_subreddit = reddit_settings.get('posts_per_subreddit', 10)
        self.lookback_days = reddit_settings.get('lookback_days', 7)

        # Default subreddits to monitor
        self.subreddits = customer_config.get('config', {}).get(
            'reddit_subreddits',
            ['technology', 'business', 'startups', 'programming', 'news']
        )

    def get_source_type(self) -> str:
        return "reddit"

    async def collect(self) -> List[IntelligenceItemCreate]:
        """
        Collect Reddit posts and comments mentioning the customer

        Returns:
            List of IntelligenceItemCreate objects
        """
        items = []

        if not self.reddit_client_id or not self.reddit_client_secret:
            self.logger.warning("Reddit API credentials not configured")
            return items

        # Use async context manager for Reddit client
        async with asyncpraw.Reddit(
            client_id=self.reddit_client_id,
            client_secret=self.reddit_client_secret,
            user_agent=self.reddit_user_agent
        ) as reddit:
            try:
                # Search across specified subreddits
                for keyword in self.keywords[:5]:  # Limit keywords to avoid rate limiting
                    if not self._check_rate_limit():
                        self.logger.warning("Rate limit reached, stopping collection")
                        break

                    # Search for posts
                    search_query = f'"{keyword}"' if ' ' in keyword else keyword

                    for subreddit_name in self.subreddits:
                        try:
                            subreddit = await reddit.subreddit(subreddit_name)

                            # Search in subreddit (last week)
                            async for submission in subreddit.search(
                                search_query,
                                time_filter='week',
                                sort='relevance',
                                limit=self.posts_per_subreddit
                            ):
                                item = await self._process_submission(submission)
                                if item:
                                    items.append(item)

                        except AsyncPRAWException as e:
                            self.logger.error(f"Error searching r/{subreddit_name}: {e}")
                            continue

                self.logger.info(f"Collected {len(items)} items from Reddit")

            except Exception as e:
                self.logger.error(f"Error collecting from Reddit: {e}")
                raise

        return items

    async def _process_submission(self, submission) -> IntelligenceItemCreate | None:
        """
        Process a Reddit submission into an IntelligenceItemCreate

        Args:
            submission: AsyncPRAW submission object

        Returns:
            IntelligenceItemCreate or None
        """
        try:
            # Quality filtering - skip deleted/removed posts
            if submission.removed_by_category or submission.author is None:
                self.logger.debug(f"Skipping removed/deleted post: {submission.id}")
                return None

            title = submission.title

            # Engagement filtering - must meet minimum threshold
            if submission.score < self.MIN_UPVOTES and submission.num_comments < self.MIN_COMMENTS:
                self.logger.debug(
                    f"Skipping low-engagement post: {title[:50]}... "
                    f"(score: {submission.score}, comments: {submission.num_comments})"
                )
                return None

            # Get post content
            content = submission.selftext or ""

            # Check relevance
            if not self._should_collect_item(title, content):
                return None

            # Fetch comments
            comment_list = []
            comment_count = 0
            try:
                if submission.comments:
                    await submission.comments.replace_more(limit=0)
                    comment_list = await submission.comments.list()
                    comment_list = comment_list or []  # Handle None case
                    comment_count = len(comment_list)
            except Exception as e:
                self.logger.warning(f"Error fetching comments for {submission.id}: {e}")
                comment_list = []
                comment_count = 0

            # Decide on content strategy based on comment count
            if comment_count >= self.LARGE_THREAD_THRESHOLD:
                # Large discussion - use AI summarization
                content = await self._summarize_thread(submission, content, comment_list)
                summarized = True
            elif comment_count > 0:
                # Small thread - append top 2-3 comments verbatim
                top_comments = sorted(
                    comment_list,
                    key=lambda c: c.score if hasattr(c, 'score') else 0,
                    reverse=True
                )[:3]

                for i, comment in enumerate(top_comments):
                    if hasattr(comment, 'body') and comment.body:
                        content += f"\n\nComment #{i+1} ({comment.score} upvotes): {comment.body[:500]}"
                summarized = False
            else:
                # No comments
                summarized = False

            # Parse published date
            published_date = datetime.fromtimestamp(submission.created_utc)

            # Get subreddit display name
            subreddit = submission.subreddit
            subreddit_name = subreddit.display_name

            # Create item
            return self._create_item(
                title=f"[r/{subreddit_name}] {title}",
                content=content,
                url=f"https://reddit.com{submission.permalink}",
                published_date=published_date,
                raw_data={
                    'subreddit': subreddit_name,
                    'author': str(submission.author) if submission.author else '[deleted]',
                    'score': submission.score,
                    'num_comments': submission.num_comments,
                    'upvote_ratio': submission.upvote_ratio,
                    'is_self': submission.is_self,
                    'link_flair_text': submission.link_flair_text,
                    'ai_summarized': summarized,
                }
            )

        except Exception as e:
            self.logger.error(f"Error processing Reddit submission: {e}")
            return None

    async def _summarize_thread(self, submission, post_content: str, comment_list: list) -> str:
        """
        Use AI to summarize a Reddit thread with many comments

        Args:
            submission: AsyncPRAW submission object
            post_content: Original post text
            comment_list: List of comment objects

        Returns:
            Summarized content including post and discussion
        """
        try:
            # Get top comments by score
            top_comments = sorted(
                comment_list,
                key=lambda c: c.score if hasattr(c, 'score') else 0,
                reverse=True
            )[:self.MAX_COMMENTS_TO_ANALYZE]

            # Build discussion text
            discussion_text = f"Original Post:\n{post_content or '[No text content]'}\n\n"
            discussion_text += f"Discussion ({submission.num_comments} comments, {submission.score} upvotes):\n\n"

            for i, comment in enumerate(top_comments):
                if hasattr(comment, 'body') and comment.body:
                    author = str(comment.author) if comment.author else '[deleted]'
                    score = comment.score if hasattr(comment, 'score') else 0
                    discussion_text += f"Comment {i+1} by {author} ({score} upvotes):\n{comment.body}\n\n"

            # Use Claude to summarize
            prompt = f"""Summarize this Reddit discussion in 2-3 concise paragraphs. Include:
1. What the post is about
2. Overall community sentiment (positive, negative, mixed, neutral)
3. Key points from the discussion
4. Any consensus or notable disagreements

Reddit Thread:
{discussion_text}

Provide a factual, objective summary suitable for business intelligence."""

            response = self.anthropic.messages.create(
                model=settings.ai_model,
                max_tokens=500,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            summary = response.content[0].text

            # Format final content
            final_content = f"{post_content}\n\n--- Discussion Summary ---\n{summary}"

            self.logger.info(f"AI-summarized thread with {len(top_comments)} comments")
            return final_content

        except Exception as e:
            self.logger.error(f"Error summarizing thread: {e}")
            # Fallback to simple concatenation
            fallback = post_content or ""
            if len(top_comments) > 0:
                fallback += f"\n\n[Discussion with {submission.num_comments} comments - summarization failed]"
                fallback += f"\n\nTop comment: {top_comments[0].body[:500]}"
            return fallback
