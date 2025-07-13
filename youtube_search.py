import os
import json
import time
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass

import requests
from googleapiclient.discovery import build
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
    """A class to search YouTube videos and retrieve their transcripts."""
    
    def __init__(self, api_key: str, proxy: Optional[str] = None, max_retries: int = 3):
        """Initialize the YouTube searcher.
        
        Args:
            api_key: YouTube Data API v3 key
            proxy: Optional HTTP/HTTPS proxy URL (e.g., 'http://user:pass@host:port')
            max_retries: Maximum number of retries for failed requests
        """
        self.api_key = api_key
        self.max_retries = max_retries
        self.session = self._setup_session(proxy)
        self.youtube = self._init_youtube_client()
    
    def _setup_session(self, proxy: Optional[str] = None) -> requests.Session:
        """Set up a requests session with optional proxy."""
        session = requests.Session()
        
        if proxy:
            try:
                session.proxies = {
                    'http': proxy,
                    'https': proxy
                }
                # Test the proxy connection
                test_url = 'https://ipv4.webshare.io/'
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
        """Initialize the YouTube API client."""
        return build('youtube', 'v3',
                    developerKey=self.api_key,
                    cache_discovery=False,
                    static_discovery=False)
    
    def get_video_transcript(self, video_id: str) -> Optional[str]:
        """Get transcript for a YouTube video.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Transcript text if available, None otherwise
        """
        for attempt in range(self.max_retries):
            try:
                time.sleep(0.15)  # Rate limiting
                
                proxies = getattr(self.session, 'proxies', None)
                transcript_list = YouTubeTranscriptApi.list_transcripts(
                    video_id,
                    proxies=proxies
                )
                
                # Try to get English transcript first, then any available
                try:
                    transcript = transcript_list.find_transcript(['en'])
                except (NoTranscriptFound, VideoUnavailable):
                    transcript = next(iter(transcript_list), None)
                
                if not transcript:
                    logger.warning(f"No transcript available for video {video_id}")
                    return None
                
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
    
    def search_videos(self, query: str, max_results: int = 3, format: str = 'raw', include_full_transcript: bool = True) -> List[Union[YouTubeVideo, Dict, str]]:
        """Search for YouTube videos.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return (1-50)
            format: Output format - 'raw', 'slim_json', or 'slim_xml'
            include_full_transcript: Whether to include full transcript in the results
            
        Returns:
            List of YouTubeVideo objects or formatted results based on format parameter
        """
        if format not in ['raw', 'slim_json', 'slim_xml']:
            raise ValueError("format must be 'raw', 'slim_json', or 'slim_xml")
            
        max_results = max(1, min(10, max_results))  # Clamp between 1 and 10
        videos = []
        
        try:
            # Search for videos
            search_response = self.youtube.search().list(
                part="snippet",
                q=query,
                type="video",
                maxResults=max_results,
                order="relevance"
            ).execute()
            
            for item in search_response.get('items', []):
                try:
                    video_id = item.get('id', {}).get('videoId')
                    snippet = item.get('snippet', {})
                    
                    if not video_id or not snippet:
                        continue
                    
                    # Get video details including description
                    video_details = self.get_video_details(video_id)
                    
                    # Get transcript if available
                    transcript = None
                    transcript_preview = "[No transcript available]"
                    has_transcript = False
                    transcript_error = None
                    
                    try:
                        logger.info(f"Checking for transcript for video: {snippet.get('title')} ({video_id})")
                        
                        # Try direct transcript fetch first
                        try:
                            proxies = getattr(self.session, 'proxies', None)
                            logger.debug(f"Attempting to fetch transcript for video {video_id}")
                            
                            # First, list all available transcripts
                            try:
                                transcript_list = YouTubeTranscriptApi.list_transcripts(
                                    video_id,
                                    proxies=proxies
                                )
                                
                                # Log available languages
                                available_langs = [f"{t.language_code} ({t.language}){' [auto-generated]' if t.is_generated else ''}" 
                                                for t in transcript_list]
                                logger.info(f"Available transcripts for {video_id}: {', '.join(available_langs) if available_langs else 'None'}")
                                
                                if not list(transcript_list):
                                    logger.warning(f"No transcripts available for video {video_id}")
                                    transcript_error = "No transcripts available"
                                else:
                                    has_transcript = True
                                    
                                    # If we need full transcript or it's raw format, fetch it
                                    if include_full_transcript or format == 'raw':
                                        try:
                                            # Try English first
                                            transcript_obj = transcript_list.find_transcript(['en'])
                                            transcript_segments = transcript_obj.fetch()
                                            transcript = '\n'.join([t.text for t in transcript_segments])
                                            transcript_preview = transcript[:500] + ('...' if len(transcript) > 500 else '')
                                            logger.info(f"Successfully fetched English transcript for video {video_id}")
                                        except Exception as e:
                                            logger.warning(f"English transcript not available for video {video_id}, trying any available: {e}")
                                            # Fallback to any available transcript
                                            try:
                                                transcript_obj = next(iter(transcript_list))
                                                transcript_segments = transcript_obj.fetch()
                                                transcript = '\n'.join([t.text for t in transcript_segments])
                                                transcript_preview = transcript[:500] + ('...' if len(transcript) > 500 else '')
                                                logger.info(f"Successfully fetched {transcript_obj.language_code} transcript for video {video_id}")
                                            except Exception as inner_e:
                                                transcript_error = f"Could not fetch any transcript: {str(inner_e)}"
                                                logger.warning(f"{transcript_error} for video {video_id}")
                                                transcript_preview = "[Transcript available but could not be fetched]"
                                    else:
                                        transcript_preview = "[Transcript available]"
                                        
                            except Exception as e:
                                transcript_error = f"Error listing transcripts: {str(e)}"
                                logger.warning(f"Could not list transcripts for video {video_id}: {e}")
                                
                        except Exception as e:
                            transcript_error = f"Unexpected error: {str(e)}"
                            logger.error(f"Unexpected error while processing transcript for video {video_id}: {e}", exc_info=True)
                            
                    except Exception as e:
                        transcript_error = f"Critical error: {str(e)}"
                        logger.critical(f"Critical error processing video {video_id}: {e}", exc_info=True)
                    
                    # Add error information to transcript preview if available
                    if transcript_error and not transcript_preview.startswith("["):
                        transcript_preview = f"[Error: {transcript_error}]"
                    
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
                        videos.append(self.__format_slim_json(video, include_full_transcript))
                    elif format == 'slim_xml':
                        videos.append(self.__format_slim_xml(video, include_full_transcript))
                    else:
                        videos.append(video)
                    
                except Exception as e:
                    logger.error(f"Error processing video {video_id}: {e}", exc_info=True)
                    continue
                    
        except HttpError as e:
            if e.resp.status == 403:
                logger.error("API quota exceeded. Please check your Google Cloud Console.")
            else:
                logger.error(f"YouTube API error: {e}")
        except Exception as e:
            logger.error(f"Error searching for videos: {e}", exc_info=True)
            
        return videos
    
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
    
    def get_video_details(self, video_id: str) -> Dict[str, str]:
        """Get additional video details.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Dictionary containing video details
        """
        try:
            response = self.youtube.videos().list(
                part="snippet",
                id=video_id
            ).execute()
            
            if not response.get('items'):
                return {"description": "No description available", "channel_title": "Unknown"}
                
            snippet = response['items'][0].get('snippet', {})
            return {
                "description": snippet.get('description', 'No description available'),
                "channel_title": snippet.get('channelTitle', 'Unknown channel')
            }
            
        except Exception as e:
            logger.error(f"Error getting video details for {video_id}: {e}")
            return {
                "description": f"Error fetching details: {str(e)[:100]}",
                "channel_title": "Unknown"
            }
