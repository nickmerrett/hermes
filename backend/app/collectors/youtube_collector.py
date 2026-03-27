"""YouTube collector for monitoring video content via transcripts"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
import time
import random
import asyncio
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
try:
    # New API (v1.2+)
    from youtube_transcript_api.exceptions import RequestBlocked, IpBlocked, NoTranscriptFound
except ImportError:
    # Old API (v0.6)
    from youtube_transcript_api._errors import TranscriptsDisabled as RequestBlocked, NoTranscriptFound
    IpBlocked = RequestBlocked
from sqlalchemy.orm import Session

from app.collectors.base import RateLimitedCollector
from app.models.schemas import IntelligenceItemCreate
from app.config.settings import settings


def get_youtube_settings(db: Session = None) -> dict:
    """
    Get YouTube collector settings from platform settings

    Returns default values if not configured
    """
    if not db:
        # Return defaults if no DB session
        return {
            'min_views': 100,
            'min_channel_subscribers': 1000,
            'enable_keyword_search': True,
            'lookback_days': 30,
            'max_videos_per_channel': 10,
            'max_videos_per_search': 5,
            'transcript_language': 'en'
        }

    try:
        from app.api.settings import get_platform_settings
        platform_settings = get_platform_settings(db)

        collector_config = platform_settings.get('collector_config', {})
        youtube_config = collector_config.get('youtube', {})

        return {
            'min_views': youtube_config.get('min_views', 100),
            'min_channel_subscribers': youtube_config.get('min_channel_subscribers', 1000),
            'lookback_days': youtube_config.get('lookback_days', 30),
            'max_videos_per_channel': youtube_config.get('max_videos_per_channel', 10),
            'max_videos_per_search': youtube_config.get('max_videos_per_search', 5),
            'transcript_language': youtube_config.get('transcript_language', 'en')
        }
    except Exception:
        # Return defaults on error
        return {
            'min_views': 100,
            'min_channel_subscribers': 1000,
            'enable_keyword_search': True,
            'lookback_days': 30,
            'max_videos_per_channel': 10,
            'max_videos_per_search': 5,
            'transcript_language': 'en'
        }


class YouTubeCollector(RateLimitedCollector):
    """
    Collector for YouTube video content via transcripts

    Monitors:
    - Specific YouTube channels
    - Keyword searches across YouTube
    - Video transcripts (auto-generated and manual)

    Features:
    - Fetches video metadata via YouTube Data API v3
    - Downloads transcripts when available
    - Processes transcript text like news articles
    - Skips videos without transcripts
    - Configurable channels and search terms
    """

    def __init__(self, customer_config: Dict[str, Any], db: Session = None):
        super().__init__(customer_config, rate_limit=100)

        # YouTube API credentials
        self.api_key = settings.youtube_api_key
        if not self.api_key:
            raise Exception("YouTube API key not configured. Please set YOUTUBE_API_KEY environment variable.")

        # Initialize YouTube API client
        self.youtube = build('youtube', 'v3', developerKey=self.api_key)

        # Get customer configuration
        config = customer_config.get('config', {})

        # YouTube channels to monitor (by channel ID)
        self.channels = config.get('youtube_channels', [])

        # Keywords to search for
        self.youtube_keywords = config.get('youtube_keywords', self.keywords[:3])  # Use first 3 customer keywords

        # Load configurable settings from platform settings
        youtube_settings = get_youtube_settings(db)

        # Quality filters
        self.min_views = youtube_settings.get('min_views', 100)
        self.min_channel_subscribers = youtube_settings.get('min_channel_subscribers', 1000)

        # Feature flags
        self.enable_keyword_search = youtube_settings.get('enable_keyword_search', True)

        # Collection settings (can be overridden per customer)
        self.lookback_days = config.get('youtube_lookback_days', youtube_settings.get('lookback_days', 30))
        self.max_videos_per_channel = config.get('youtube_max_videos_per_channel', youtube_settings.get('max_videos_per_channel', 10))
        self.max_videos_per_search = config.get('youtube_max_videos_per_search', youtube_settings.get('max_videos_per_search', 5))
        self.transcript_language = config.get('youtube_transcript_language', youtube_settings.get('transcript_language', 'en'))

        # Initialize transcript API client (new API v1.2+)
        self.transcript_api = YouTubeTranscriptApi()

        # Cache for channel subscriber counts (to avoid repeated API calls)
        self.channel_subscriber_cache = {}

    def get_source_type(self) -> str:
        return "youtube"

    async def collect(self) -> List[IntelligenceItemCreate]:
        """
        Collect YouTube videos and their transcripts

        Returns:
            List of IntelligenceItemCreate objects
        """
        items = []
        self.transcript_success_count = 0
        self.transcript_fail_count = 0

        # Calculate date threshold
        published_after = (datetime.utcnow() - timedelta(days=self.lookback_days)).isoformat() + 'Z'

        try:
            # Monitor specific channels
            for channel_config in self.channels:
                if not self._check_rate_limit():
                    self.logger.warning("Rate limit reached, stopping collection")
                    break

                channel_id = channel_config.get('channel_id') if isinstance(channel_config, dict) else channel_config
                channel_name = channel_config.get('name', 'Unknown') if isinstance(channel_config, dict) else 'Unknown'

                self.logger.info(f"Collecting from YouTube channel: {channel_name} ({channel_id})")

                # Get recent videos from channel
                try:
                    channel_items = await self._collect_from_channel(channel_id, channel_name, published_after)
                    items.extend(channel_items)
                except Exception as e:
                    self.logger.error(f"Error collecting from channel {channel_id}: {e}")
                    continue

            # Search by keywords (if enabled)
            if self.enable_keyword_search:
                for keyword in self.youtube_keywords:
                    if not self._check_rate_limit():
                        self.logger.warning("Rate limit reached, stopping collection")
                        break

                    self.logger.info(f"Searching YouTube for: {keyword}")

                    try:
                        search_items = await self._search_videos(keyword, published_after)
                        items.extend(search_items)
                    except Exception as e:
                        self.logger.error(f"Error searching for '{keyword}': {e}")
                        continue
            else:
                self.logger.debug("YouTube keyword search disabled in platform settings")

            # Log summary with transcript success rate
            if len(items) > 0:
                transcript_rate = (self.transcript_success_count / len(items) * 100) if len(items) > 0 else 0
                self.logger.info(
                    f"Collected {len(items)} items from YouTube: "
                    f"{self.transcript_success_count} with transcripts ({transcript_rate:.0f}%), "
                    f"{self.transcript_fail_count} using descriptions only"
                )
            else:
                self.logger.info("Collected 0 items from YouTube")

        except Exception as e:
            self.logger.error(f"Error collecting from YouTube: {e}")
            raise

        return items

    async def _collect_from_channel(self, channel_id: str, channel_name: str, published_after: str) -> List[IntelligenceItemCreate]:
        """Collect recent videos from a specific channel"""
        items = []

        try:
            # Search for videos in this channel
            request = self.youtube.search().list(
                part='id,snippet',
                channelId=channel_id,
                type='video',
                publishedAfter=published_after,
                order='date',
                maxResults=self.max_videos_per_channel
            )

            response = request.execute()

            for video_item in response.get('items', []):
                if not self._check_rate_limit():
                    break

                video_id = video_item['id']['videoId']
                snippet = video_item['snippet']

                # Process the video
                item = await self._process_video(video_id, snippet, channel_name)
                if item:
                    items.append(item)

        except HttpError as e:
            self.logger.error(f"YouTube API error for channel {channel_id}: {e}")

        return items

    async def _search_videos(self, keyword: str, published_after: str) -> List[IntelligenceItemCreate]:
        """Search for videos by keyword"""
        items = []

        try:
            # Search for videos
            request = self.youtube.search().list(
                part='id,snippet',
                q=keyword,
                type='video',
                publishedAfter=published_after,
                order='relevance',
                maxResults=self.max_videos_per_search
            )

            response = request.execute()

            for video_item in response.get('items', []):
                if not self._check_rate_limit():
                    break

                video_id = video_item['id']['videoId']
                snippet = video_item['snippet']

                # Check if content is relevant before processing
                title = snippet['title']
                description = snippet['description']

                if not self._should_collect_item(title, description):
                    continue

                # Process the video
                item = await self._process_video(video_id, snippet)
                if item:
                    items.append(item)

        except HttpError as e:
            self.logger.error(f"YouTube API error for keyword '{keyword}': {e}")

        return items

    async def _process_video(self, video_id: str, snippet: dict, channel_name: str = None) -> IntelligenceItemCreate | None:
        """Process a single video into an IntelligenceItemCreate"""

        try:
            title = snippet['title']
            description = snippet['description']
            published_at = snippet['publishedAt']
            channel_title = channel_name or snippet.get('channelTitle', 'Unknown')

            # Parse published date
            published_date = datetime.strptime(published_at, '%Y-%m-%dT%H:%M:%SZ')

            # Try to get transcript
            transcript_text = None
            transcript_available = False

            try:
                # Fetch transcript using new API (v1.2+)
                # Wrap in asyncio.to_thread with timeout to prevent hanging
                transcript_list = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.transcript_api.fetch,
                        video_id,
                        [self.transcript_language, 'en']  # Fallback to English
                    ),
                    timeout=15.0  # 15 second timeout for transcript fetch
                )

                # Combine transcript segments
                transcript_text = ' '.join([segment['text'] for segment in transcript_list])
                transcript_available = True
                self.transcript_success_count += 1

                self.logger.debug(f"Transcript fetched for video: {title} ({len(transcript_text)} chars)")

            except asyncio.TimeoutError:
                self.logger.warning(f"Timeout fetching transcript for {video_id} (15s limit)")
                self.transcript_fail_count += 1
                # Continue without transcript - will use description
            except NoTranscriptFound:
                self.logger.debug(f"No transcript available for video: {title}")
                self.transcript_fail_count += 1
                # Continue without transcript - will use description
            except (RequestBlocked, IpBlocked) as e:
                # YouTube is rate limiting/blocking our IP (common on cloud providers)
                self.logger.debug(f"YouTube blocked transcript request for {video_id}: {type(e).__name__}")
                self.transcript_fail_count += 1
                # Continue without transcript - will use description
            except Exception as e:
                # Catch any other errors
                error_str = str(e).lower()
                if 'too many requests' in error_str or '429' in error_str:
                    self.logger.debug(f"Rate limited by YouTube for video {video_id}")
                    self.transcript_fail_count += 1
                else:
                    self.logger.warning(f"Error fetching transcript for {video_id}: {e}")
                    self.transcript_fail_count += 1

            # Add delay between transcript requests to avoid rate limiting
            # Use asyncio.sleep instead of time.sleep to avoid blocking
            await asyncio.sleep(random.uniform(1.0, 3.0))

            # Determine content
            if transcript_text:
                # Use full transcript as content
                content = f"{description}\n\n--- Video Transcript ---\n\n{transcript_text}"
            else:
                # Fall back to description only
                content = description

                # If description is too short, skip this video
                if len(description) < 50:
                    self.logger.debug(f"Skipping video without transcript or meaningful description: {title}")
                    return None

            # Check relevance with full content
            if not self._should_collect_item(title, content):
                return None

            # Get video URL
            url = f"https://www.youtube.com/watch?v={video_id}"

            # Get additional metadata
            video_details = self._get_video_details(video_id)

            # Apply quality filters
            view_count = video_details.get('view_count', 0)
            if view_count < self.min_views:
                self.logger.debug(f"Skipping video {video_id}: {view_count} views < {self.min_views} minimum")
                return None

            # Get channel subscriber count
            channel_id = snippet.get('channelId')
            if channel_id:
                subscriber_count = self._get_channel_subscriber_count(channel_id)
                if subscriber_count < self.min_channel_subscribers:
                    self.logger.debug(f"Skipping video {video_id}: channel has {subscriber_count} subscribers < {self.min_channel_subscribers} minimum")
                    return None

            # Create item
            return self._create_item(
                title=f"[{channel_title}] {title}",
                content=content,
                url=url,
                published_date=published_date,
                raw_data={
                    'video_id': video_id,
                    'channel': channel_title,
                    'published_at': published_at,
                    'transcript_available': transcript_available,
                    'transcript_length': len(transcript_text) if transcript_text else 0,
                    'view_count': video_details.get('view_count'),
                    'like_count': video_details.get('like_count'),
                    'comment_count': video_details.get('comment_count'),
                    'duration': video_details.get('duration'),
                }
            )

        except Exception as e:
            self.logger.error(f"Error processing YouTube video {video_id}: {e}")
            return None

    def _get_video_details(self, video_id: str) -> dict:
        """Get additional video metadata (views, likes, duration)"""
        try:
            request = self.youtube.videos().list(
                part='statistics,contentDetails',
                id=video_id
            )

            response = request.execute()

            if response.get('items'):
                item = response['items'][0]
                statistics = item.get('statistics', {})
                content_details = item.get('contentDetails', {})

                return {
                    'view_count': int(statistics.get('viewCount', 0)),
                    'like_count': int(statistics.get('likeCount', 0)),
                    'comment_count': int(statistics.get('commentCount', 0)),
                    'duration': content_details.get('duration', 'Unknown')
                }
        except Exception as e:
            self.logger.warning(f"Error fetching video details for {video_id}: {e}")

        return {}

    def _get_channel_subscriber_count(self, channel_id: str) -> int:
        """
        Get channel subscriber count with caching

        Args:
            channel_id: YouTube channel ID

        Returns:
            Subscriber count (0 if unavailable or error)
        """
        # Check cache first
        if channel_id in self.channel_subscriber_cache:
            return self.channel_subscriber_cache[channel_id]

        try:
            request = self.youtube.channels().list(
                part='statistics',
                id=channel_id
            )

            response = request.execute()

            if response.get('items'):
                statistics = response['items'][0].get('statistics', {})
                subscriber_count = int(statistics.get('subscriberCount', 0))

                # Cache the result
                self.channel_subscriber_cache[channel_id] = subscriber_count

                return subscriber_count
        except Exception as e:
            self.logger.warning(f"Error fetching channel subscriber count for {channel_id}: {e}")

        # Cache 0 on error to avoid repeated failures
        self.channel_subscriber_cache[channel_id] = 0
        return 0
