import os
import json
import time
import logging
import concurrent.futures
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass
from functools import lru_cache

import requests
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
from youtube_transcript_api.formatters import TextFormatter
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('YouTubeSearcher')

@dataclass
class YouTubeVideo:
    """Data class to store YouTube video information."""
    video_id: str
    title: str
    url: str
    channel: str
    published_at: str
    description: str
    has_transcript: bool
    transcript_preview: Optional[str] = None
    full_transcript: Optional[str] = None

class YouTubeSearcher:
    """A class to search YouTube videos and retrieve their transcripts with parallel processing."""
    
    def __init__(self, api_key: str, proxy: Optional[str] = None, max_retries: int = 3, max_workers: int = 5):
        """Initialize the YouTube searcher.
        
        Args:
            api_key: YouTube Data API v3 key
            proxy: Optional HTTP/HTTPS proxy URL
            max_retries: Maximum number of retries for failed requests
            max_workers: Maximum number of worker threads for parallel processing
        """
        self.api_key = api_key
        self.max_retries = max_retries
        self.max_workers = max_workers
        self.session = self._setup_session(proxy)
        self.youtube_base_url = "https://www.googleapis.com/youtube/v3"
        self._timings = {}
    
    def _timeit(self, name: str):
        """Context manager to time a block of code."""
        class Timer:
            def __init__(self, parent, name):
                self.parent = parent
                self.name = name
                self.start = None
            
            def __enter__(self):
                self.start = time.time()
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                duration = time.time() - self.start
                if self.name not in self.parent._timings:
                    self.parent._timings[self.name] = []
                self.parent._timings[self.name].append(duration)
                logger.debug(f"{self.name} took {duration:.2f} seconds")
        
        return Timer(self, name)

    def get_timings(self) -> Dict[str, List[float]]:
        """Get the recorded timing information."""
        return self._timings

    def print_timing_summary(self):
        """Print a summary of the recorded timings."""
        if not self._timings:
            print("No timing information available.")
            return
            
        print("\n=== Timing Summary ===")
        for name, timings in self._timings.items():
            if timings:
                total = sum(timings)
                avg = total / len(timings)
                print(f"{name}: {total:.2f}s total, {avg:.2f}s avg, {len(timings)} calls")
        print("====================\n")
    
    def _setup_session(self, proxy: Optional[str] = None) -> requests.Session:
        """Set up a requests session with optional proxy."""
        session = requests.Session()
        
        if proxy:
            try:
                session.proxies = {
                    'http': proxy,
                    'https': proxy
                }
                # Test the proxy connection with a simple HTTP request
                test_url = 'http://ipv4.webshare.io/'
                response = session.get(test_url, timeout=10, verify=False)
                if response.status_code == 200:
                    logger.info(f"Successfully connected to proxy. IP: {response.text.strip()}")
                else:
                    logger.warning(f"Proxy connection test failed with status {response.status_code}")
            except Exception as e:
                logger.error(f"Error setting up proxy: {e}")
                logger.info("Continuing without proxy...")
                session.proxies = {}
        
        return session
    
    def _init_youtube_client(self):
        """Initialize the YouTube API client with direct HTTP requests."""
        self.youtube_base_url = "https://www.googleapis.com/youtube/v3"
        return None  # We won't use the build client anymore

    @lru_cache(maxsize=100)
    def get_video_transcript(self, video_id: str) -> Optional[str]:
        """Get transcript for a YouTube video with caching."""
        with self._timeit("get_video_transcript"):
            for attempt in range(self.max_retries):
                try:
                    time.sleep(0.05)  # Reduced rate limiting
                    
                    proxies = getattr(self.session, 'proxies', None)
                    with self._timeit("list_transcripts"):
                        transcript_list = YouTubeTranscriptApi.list_transcripts(
                            video_id,
                            proxies=proxies
                        )
                    
                    # Try to get English transcript first, then any available
                    try:
                        with self._timeit("find_english_transcript"):
                            transcript = transcript_list.find_transcript(['en'])
                    except (NoTranscriptFound, VideoUnavailable):
                        with self._timeit("find_any_transcript"):
                            transcript = next(iter(transcript_list), None)
                    
                    if not transcript:
                        logger.warning(f"No transcript available for video {video_id}")
                        return None
                    
                    with self._timeit("fetch_transcript"):
                        formatter = TextFormatter()
                        return formatter.format_transcript(transcript.fetch())
                        
                except TranscriptsDisabled:
                    logger.debug(f"Transcripts are disabled for video {video_id}")
                    return None
                except VideoUnavailable:
                    logger.warning(f"Video {video_id} is unavailable")
                    return None
                except Exception as e:
                    if attempt == self.max_retries - 1:
                        logger.error(f"Failed to get transcript after {self.max_retries} attempts: {e}")
                        return None
                    logger.warning(f"Attempt {attempt + 1} failed, retrying...")
                    time.sleep(1)  # Backoff before retry
            return None

    def _process_video(self, item: dict, format: str, include_full_transcript: bool) -> Union[YouTubeVideo, Dict, str, None]:
        """Process a single video item and return the formatted result."""
        try:
            video_id = item.get('id', {}).get('videoId')
            snippet = item.get('snippet', {})
            
            if not video_id or not snippet:
                return None
            
            # Get video details including description
            with self._timeit("get_video_details"):
                video_details = self.get_video_details(video_id)
            
            # Get transcript if needed
            transcript = None
            transcript_preview = "[Transcript not fetched]"
            has_transcript = False
            
            if include_full_transcript or format in ['raw', 'slim_xml']:
                transcript = self.get_video_transcript(video_id)
                has_transcript = transcript is not None
                transcript_preview = transcript[:500] + '...' if transcript else "[No transcript available]"
            
            video = YouTubeVideo(
                video_id=video_id,
                title=snippet.get('title', 'No Title'),
                url=f"https://www.youtube.com/watch?v={video_id}",
                channel=snippet.get('channelTitle', 'Unknown Channel'),
                published_at=snippet.get('publishedAt', ''),
                description=video_details.get('description', ''),
                has_transcript=has_transcript,
                transcript_preview=transcript_preview,
                full_transcript=transcript if ((include_full_transcript or format == 'raw') and transcript) else None
            )
            
            # Format the result based on the requested format
            if format == 'slim_json':
                return self.__format_slim_json(video, include_full_transcript)
            elif format == 'slim_xml':
                return self.__format_slim_xml(video, include_full_transcript)
            else:
                return video
                
        except Exception as e:
            logger.error(f"Error processing video {video_id if 'video_id' in locals() else 'unknown'}: {e}", exc_info=True)
            return None

    def search_videos(self, query: str, max_results: int = 3, format: str = 'raw', include_full_transcript: bool = True) -> List[Union[YouTubeVideo, Dict, str]]:
        """Search for YouTube videos with parallel processing."""
        start_time = time.time()
        self._timings.clear()
        
        if format not in ['raw', 'slim_json', 'slim_xml']:
            raise ValueError("format must be 'raw', 'slim_json', or 'slim_xml'")
            
        max_results = max(1, min(10, max_results))
        videos = []
        
        try:
            # Step 1: Perform the initial search to get video IDs
            with self._timeit("youtube_search"):
                url = f"{self.youtube_base_url}/search"
                params = {
                    'part': 'snippet',
                    'q': query,
                    'type': 'video',
                    'maxResults': max_results,
                    'order': 'relevance',
                    'key': self.api_key
                }
                response = self.session.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
            
            items = data.get('items', [])
            logger.info(f"Found {len(items)} videos for query: {query}")
            
            # Step 2: Process videos in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Create a future for each video
                future_to_item = {
                    executor.submit(
                        self._process_video,
                        item,
                        format,
                        include_full_transcript
                    ): item for item in items
                }
                
                # Process completed futures as they complete
                for future in concurrent.futures.as_completed(future_to_item):
                    result = future.result()
                    if result is not None:
                        videos.append(result)
            
            total_time = time.time() - start_time
            logger.info(f"Search completed in {total_time:.2f} seconds")
            self.print_timing_summary()
            
            return videos
            
        except Exception as e:
            logger.error(f"Error searching for videos: {e}", exc_info=True)
            return []
    
    def get_video_details(self, video_id: str) -> Dict[str, str]:
        """Get additional video details using direct HTTP request."""
        for attempt in range(self.max_retries):
            try:
                url = f"{self.youtube_base_url}/videos"
                params = {
                    'part': 'snippet',
                    'id': video_id,
                    'key': self.api_key
                }
                
                response = self.session.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if not data.get('items'):
                    return {
                        "description": "No description available", 
                        "channel_title": "Unknown"
                    }
                    
                snippet = data['items'][0].get('snippet', {})
                return {
                    "description": snippet.get('description', 'No description available'),
                    "channel_title": snippet.get('channelTitle', 'Unknown channel')
                }
                
            except Exception as e:
                if attempt == self.max_retries - 1:  # Last attempt
                    logger.error(f"Failed to get video details for {video_id} after {self.max_retries} attempts: {e}")
                    return {
                        "description": f"Error fetching details: {str(e)[:100]}",
                        "channel_title": "Unknown"
                    }
                
                wait_time = (2 ** attempt) * 0.5  # Exponential backoff
                logger.warning(f"Attempt {attempt + 1} failed for {video_id}, retrying in {wait_time:.1f}s...")
                time.sleep(wait_time)
    
    def __format_slim_json(self, video: YouTubeVideo, include_full_transcript: bool = False) -> Dict[str, Any]:
        """Format a YouTubeVideo into a minimal JSON format."""
        result = {
            "title": video.title,
            "channel": video.channel,
            "url": video.url,
            "published_at": video.published_at,
            "description": video.description[:500] + ('...' if len(video.description) > 500 else ''),
            "has_transcript": video.has_transcript,
            "transcript_preview": video.transcript_preview
        }
        
        if include_full_transcript and video.full_transcript:
            result["full_transcript"] = video.full_transcript
            
        return result
    
    def __format_slim_xml(self, video: YouTubeVideo, include_full_transcript: bool = False) -> str:
        """Format a YouTubeVideo into a slim XML format optimized for LLM processing."""
        def escape_xml(text):
            if not text:
                return ""
            return (
                str(text)
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&apos;')
            )
        
        # Unescape special characters in the content
        from html import unescape
        
        # Build XML content with clear section separation and minimal nesting
        lines = []
        
        # Video metadata section
        lines.append(f'<title>{escape_xml(video.title)}</title>')
        lines.append(f'<channel>{escape_xml(video.channel)}</channel>')
        lines.append(f'<url>{escape_xml(video.url)}</url>')
        lines.append(f'<published>{escape_xml(video.published_at)}</published>')        
        # Description section
        description = unescape(video.description[:500] + ('...' if len(video.description) > 500 else ''))
        lines.append(f'<description>\n{escape_xml(description)}\n</description>')
        
        # Transcript section
        if video.transcript_preview:
            transcript_preview = unescape(video.transcript_preview)
            lines.append(f'<transcript_preview>\n{escape_xml(transcript_preview)}\n</transcript_preview>')
        
        # Full transcript if requested and available
        if include_full_transcript and video.full_transcript:
            full_transcript = unescape(video.full_transcript)
            lines.append(f'<full_transcript>\n{escape_xml(full_transcript)}\n</full_transcript>')
        
        return '\n'.join(lines)
