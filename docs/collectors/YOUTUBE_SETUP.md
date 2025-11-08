# YouTube Collector Setup Guide

The YouTube collector monitors YouTube channels and searches for video content via transcripts.

## Features

- ✅ Monitor specific YouTube channels
- ✅ Search YouTube by keywords
- ✅ Fetch video transcripts automatically
- ✅ Process transcripts like news articles
- ✅ Track video metadata (views, likes, comments)
- ✅ Skip videos without transcripts
- ✅ Works with auto-generated and manual captions

## Prerequisites

### 1. Python Dependencies

Install required packages:

```bash
pip install google-api-python-client youtube-transcript-api
```

Or add to `requirements.txt`:
```
google-api-python-client>=2.100.0
youtube-transcript-api>=1.2.3
```

**Important:** We use version 1.2.3+ which has a different API than older versions.

### 2. YouTube Data API v3 Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable **YouTube Data API v3**:
   - Navigate to "APIs & Services" → "Library"
   - Search for "YouTube Data API v3"
   - Click "Enable"
4. Create API credentials:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "API Key"
   - Copy the API key
5. (Optional) Restrict the API key:
   - Click on the key to edit
   - Under "API restrictions", select "Restrict key"
   - Choose "YouTube Data API v3"

### 3. Set Environment Variable

If you don't have a `.env` file, copy from the example:

```bash
cp backend/.env.example backend/.env
```

Then add your YouTube API key to `backend/.env`:

```bash
YOUTUBE_API_KEY=your_api_key_here
```

Or set as environment variable:
```bash
export YOUTUBE_API_KEY=your_api_key_here
```

## Configuration

### Platform-Wide Settings

Configure YouTube collection behavior in **Platform Settings → Collector Configuration → YouTube Collector:**

#### Collection Options

- **Enable Keyword Search** (default: ON)
  - When enabled: Searches YouTube for videos matching customer keywords
  - When disabled: Only monitors videos from explicitly configured channels
  - Disable this to reduce noise and only track trusted channels

#### Quality Filters

- **Minimum Views**: Videos must have at least this many views (default: 100)
- **Minimum Channel Subscribers**: Channel must have at least this many subscribers (default: 1,000)

These filters help reduce noise by excluding:
- Low-quality or unpopular videos
- Videos from small/unestablished channels
- Spam or low-engagement content

**Note:** These filters apply to both channel monitoring and keyword searches.

### Per-Customer Configuration

Add YouTube configuration to customer YAML or via UI:

```yaml
customers:
  - name: "Example Company"
    keywords:
      - "example company"
      - "CEO name"
      - "product launch"
    collection_config:
      youtube_enabled: true
      youtube_channels:
        - channel_id: "UCxxxxxxxxxxxxxxxxxxxxxx"
          name: "Company Official Channel"
        - channel_id: "UCyyyyyyyyyyyyyyyyyyyyyyyy"
          name: "Industry News Channel"
      youtube_lookback_days: 30  # Optional, default: 30
      youtube_max_videos_per_channel: 10  # Optional, default: 10
      youtube_max_videos_per_search: 5  # Optional, default: 5
      youtube_transcript_language: "en"  # Optional, default: "en"
```

**Note:** YouTube searches automatically use the customer's general keywords (first 3 by default). No need to specify separate YouTube keywords.

### Finding YouTube Channel IDs

**Method 1: From Channel URL**
- Channel URL: `https://www.youtube.com/@ChannelName` or `https://www.youtube.com/c/ChannelName`
- View page source and search for `"channelId":"`
- Or use: `https://www.youtube.com/@ChannelName/about` → Right-click → View Page Source → Search for "channelId"

**Method 2: Using a tool**
- Visit: https://commentpicker.com/youtube-channel-id.php
- Paste channel URL
- Get channel ID

**Method 3: From video**
- Open any video from the channel
- Channel ID is in the page source

### Collection Interval

Default: Every 12 hours

Configure in Platform Settings → Collection Timing:
- YouTube: 12 hours (recommended)
- Can be set from 1-168 hours

## API Quota

YouTube Data API v3 has a quota of **10,000 units/day** (free tier).

**Cost per operation:**
- Search: 100 units
- Video list: 1 unit
- Channel list: 1 unit

**Estimated usage:**
- Monitoring 5 channels with 10 videos each: ~55 units
- Searching 3 keywords with 5 results each: ~315 units
- **Total per collection:** ~370 units
- **Collections per day at 12-hour interval:** 2
- **Daily usage:** ~740 units (well under 10,000 limit)

## How It Works

1. **Channel Monitoring**: Fetches recent videos from configured channels
2. **Keyword Search**: Searches YouTube for specified keywords
3. **Transcript Fetching**: Attempts to download transcript for each video
   - Tries configured language (default: English)
   - Falls back to English if not available
   - Skips video if no transcript available
4. **Content Processing**: Treats transcript as text content
5. **Relevance Check**: AI filters based on customer keywords
6. **Intelligence Item**: Created with transcript, metadata, and video link

## Transcript Availability

**High Availability:**
- Major channels (tech companies, news outlets)
- Professional content creators
- Educational channels
- Corporate channels

**Lower Availability:**
- Small independent creators
- Gaming streams
- Live streams (unless archived with transcripts)
- Very old videos

**Estimated Coverage:** 60-80% of professionally produced content

## Limitations

- Only processes videos with available transcripts
- Auto-generated transcripts may have errors
- API quota limits (10,000 units/day)
- Transcripts in configured language only
- No analysis of visual content (video/audio)

## Troubleshooting

### "YouTube API key not configured"
- Ensure `YOUTUBE_API_KEY` is set in `.env`
- Restart backend server after adding key

### "YouTube API error: quotaExceeded"
- Daily quota reached (10,000 units)
- Wait until quota resets (midnight Pacific Time)
- Reduce collection frequency or number of searches

### "No transcript available"
- Video doesn't have captions/subtitles
- This is expected - collector will skip these videos
- Try monitoring channels known to provide transcripts

### "Transcripts disabled"
- Channel owner disabled transcripts
- Collector will skip these videos

### "YouTube blocked transcript request" or "Rate limited"
- **YouTube aggressively rate limits transcript requests**
- If running on cloud providers (AWS, GCP, Azure), YouTube may block your IP
- The collector adds 1-3 second delays between requests to help
- For high-volume usage, consider residential proxies (see youtube-transcript-api docs)
- Fallback: Videos without transcripts will use descriptions instead

## Best Practices

1. **Start with key channels**: Monitor 3-5 important channels first
2. **Use specific keywords**: "CEO name interview" better than just "CEO"
3. **Set realistic intervals**: 12-24 hours recommended
4. **Monitor quota usage**: Check Google Cloud Console
5. **Focus on professional content**: Better transcript availability

## Example Intelligence Items

**From Channel:**
```
Title: [TechCorp Official] Q4 2025 Earnings Call
Source: youtube
Content: [Video description]

--- Video Transcript ---

Thank you for joining TechCorp's Q4 earnings call.
I'm CEO Jane Smith. This quarter we achieved record
revenue of $2.5 billion, up 25% year over year...

[Full transcript continues...]

Metadata:
- Views: 15,234
- Likes: 892
- Comments: 124
- Duration: PT45M12S
```

**From Keyword Search:**
```
Title: [Industry Weekly] Interview with TechCorp CTO on AI Strategy
Source: youtube
Content: In this episode we sit down with TechCorp's CTO...

--- Video Transcript ---

Host: Welcome to Industry Weekly. Today we have
TechCorp's CTO discussing their new AI initiatives...

[Interview transcript...]
```

## Support

For issues or questions:
- Check YouTube Data API documentation
- Review Google Cloud Console quota page
- Check Hermes logs for detailed error messages
