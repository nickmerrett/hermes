#!/usr/bin/env python3
"""
Test YouTube transcript fetching for specific video IDs
"""
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

# Video IDs to test
test_videos = [
    "ccdhZTPnMWM",  # User confirmed has transcript
    "7muYSvhI-sY",  # From error logs
    "9GhT1mp5Edk",  # From error logs
    "enLbj0igyx4",  # From error logs
]

for video_id in test_videos:
    print(f"\n{'='*60}")
    print(f"Testing video: {video_id}")
    print(f"URL: https://www.youtube.com/watch?v={video_id}")
    print(f"{'='*60}")

    try:
        # Try to get transcript
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])

        # Success!
        transcript_text = ' '.join([segment['text'] for segment in transcript])
        print(f"✅ SUCCESS: Fetched transcript ({len(transcript_text)} chars)")
        print(f"First 200 chars: {transcript_text[:200]}...")

    except TranscriptsDisabled:
        print(f"❌ FAILED: Transcripts are disabled for this video")

    except NoTranscriptFound:
        print(f"❌ FAILED: No transcript found in requested language")

        # Try to list available languages
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            print(f"Available transcripts:")
            for transcript in transcript_list:
                print(f"  - {transcript.language} ({transcript.language_code}) - Generated: {transcript.is_generated}")
        except Exception as e:
            print(f"  Could not list available transcripts: {e}")

    except Exception as e:
        print(f"❌ FAILED: Unexpected error: {type(e).__name__}: {e}")

        # Try to get more info about available transcripts
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            print(f"Available transcripts:")
            for transcript in transcript_list:
                print(f"  - {transcript.language} ({transcript.language_code}) - Generated: {transcript.is_generated}")
        except Exception as list_error:
            print(f"  Could not list available transcripts: {list_error}")

print(f"\n{'='*60}")
print("Test complete!")
print(f"{'='*60}")
