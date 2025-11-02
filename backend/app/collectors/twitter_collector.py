"""Twitter/X collector for social media monitoring"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
import tweepy
from tweepy.errors import TweepyException

from app.collectors.base import RateLimitedCollector
from app.models.schemas import IntelligenceItemCreate
from app.config.settings import settings


class TwitterCollector(RateLimitedCollector):
    """
    Collector for Twitter/X mentions and posts

    Monitors:
    - Company's official tweets
    - Mentions of company/keywords
    - Hashtags
    - Sentiment from community
    """

    def __init__(self, customer_config: Dict[str, Any]):
        super().__init__(customer_config, rate_limit=100)

        # Initialize Twitter API v2
        if settings.twitter_bearer_token:
            self.client = tweepy.Client(
                bearer_token=settings.twitter_bearer_token,
                wait_on_rate_limit=True
            )
        else:
            self.client = None
            self.logger.warning("Twitter API credentials not configured")

        self.twitter_handle = customer_config.get('config', {}).get('twitter_handle')
        self.lookback_days = 7

    def get_source_type(self) -> str:
        return "twitter"

    async def collect(self) -> List[IntelligenceItemCreate]:
        """
        Collect tweets about the customer

        Returns:
            List of IntelligenceItemCreate objects
        """
        items = []

        if not self.client:
            self.logger.warning("Twitter client not initialized")
            return items

        try:
            # Collect from official account if specified
            if self.twitter_handle:
                account_items = self._collect_from_account(self.twitter_handle)
                items.extend(account_items)

            # Search for mentions and keywords
            for keyword in self.keywords[:5]:  # Limit to avoid rate limiting
                if not self._check_rate_limit():
                    break

                search_items = self._search_tweets(keyword)
                items.extend(search_items)

            self.logger.info(f"Collected {len(items)} items from Twitter")

        except Exception as e:
            self.logger.error(f"Error collecting from Twitter: {e}")
            raise

        return items

    def _collect_from_account(self, handle: str) -> List[IntelligenceItemCreate]:
        """Collect tweets from a specific Twitter account"""
        items = []

        try:
            # Remove @ if present
            handle = handle.lstrip('@')

            # Get user
            user = self.client.get_user(username=handle)
            if not user.data:
                self.logger.warning(f"Twitter user @{handle} not found")
                return items

            user_id = user.data.id

            # Get recent tweets
            tweets = self.client.get_users_tweets(
                id=user_id,
                max_results=25,
                tweet_fields=['created_at', 'public_metrics', 'entities', 'referenced_tweets'],
                exclude=['retweets', 'replies']
            )

            if tweets.data:
                cutoff_date = datetime.now(datetime.timezone.utc) - timedelta(days=self.lookback_days)

                for tweet in tweets.data:
                    if tweet.created_at < cutoff_date:
                        continue

                    item = self._process_tweet(tweet, handle)
                    if item:
                        items.append(item)

        except TweepyException as e:
            self.logger.error(f"Error collecting from @{handle}: {e}")

        return items

    def _search_tweets(self, keyword: str) -> List[IntelligenceItemCreate]:
        """Search for tweets containing keyword"""
        items = []

        try:
            # Build search query
            query = f'"{keyword}"' if ' ' in keyword else keyword
            query += ' -is:retweet lang:en'  # Exclude retweets, English only

            # Calculate start time
            start_time = datetime.now(datetime.timezone.utc) - timedelta(days=self.lookback_days)

            # Search recent tweets
            tweets = self.client.search_recent_tweets(
                query=query,
                max_results=25,
                tweet_fields=['created_at', 'public_metrics', 'author_id', 'entities'],
                start_time=start_time
            )

            if tweets.data:
                for tweet in tweets.data:
                    item = self._process_tweet(tweet)
                    if item:
                        items.append(item)

        except TweepyException as e:
            self.logger.error(f"Error searching Twitter for '{keyword}': {e}")

        return items

    def _process_tweet(
        self,
        tweet,
        author_handle: str = None
    ) -> IntelligenceItemCreate | None:
        """
        Process a tweet into an IntelligenceItemCreate

        Args:
            tweet: Tweepy tweet object
            author_handle: Twitter handle of author (if known)

        Returns:
            IntelligenceItemCreate or None
        """
        try:
            text = tweet.text

            # Check relevance
            if not self._should_collect_item(text, ""):
                return None

            # Build title and content
            author = f"@{author_handle}" if author_handle else "Twitter"
            title = f"[{author}] {text[:100]}{'...' if len(text) > 100 else ''}"
            content = text

            # Add metrics to content
            if hasattr(tweet, 'public_metrics') and tweet.public_metrics:
                metrics = tweet.public_metrics
                content += f"\n\nEngagement: {metrics.get('like_count', 0)} likes, "
                content += f"{metrics.get('retweet_count', 0)} retweets, "
                content += f"{metrics.get('reply_count', 0)} replies"

            # Build URL
            tweet_id = tweet.id
            url = f"https://twitter.com/i/web/status/{tweet_id}"
            if author_handle:
                url = f"https://twitter.com/{author_handle}/status/{tweet_id}"

            return self._create_item(
                title=title,
                content=content,
                url=url,
                published_date=tweet.created_at,
                raw_data={
                    'tweet_id': str(tweet_id),
                    'author_handle': author_handle,
                    'author_id': str(tweet.author_id) if hasattr(tweet, 'author_id') else None,
                    'metrics': tweet.public_metrics if hasattr(tweet, 'public_metrics') else {},
                    'entities': tweet.entities if hasattr(tweet, 'entities') else {},
                }
            )

        except Exception as e:
            self.logger.error(f"Error processing tweet: {e}")
            return None
