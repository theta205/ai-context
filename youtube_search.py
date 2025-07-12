import os
import json
import time
import requests
from typing import List, Dict, Any, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class YouTubeSearcher:
    def __init__(self, api_key: str):
        """Initialize the YouTube searcher with API key and proxy settings."""
        # Get proxy from environment
        self.proxy = os.getenv('HTTP_PROXY')
        self.session = requests.Session()
        
        # Configure proxy if available
        if self.proxy:
            try:
                print(f"Using HTTP proxy: {self.proxy}")
                
                # Set up the session with proxy
                self.session.proxies = {
                    'http': self.proxy,
                    'https': self.proxy
                }
                
                # Test the proxy connection
                test_url = 'https://ipv4.webshare.io/'
                response = self.session.get(test_url, timeout=10, verify=False)
                if response.status_code == 200:
                    print(f"Successfully connected to proxy. IP: {response.text.strip()}")
                else:
                    print(f"Warning: Proxy connection test failed with status {response.status_code}")
                
            except Exception as e:
                print(f"Error setting up proxy: {str(e)[:200]}...")
                print("Continuing without proxy...")
        
        # Initialize YouTube API client
        self.youtube = build('youtube', 'v3',
                           developerKey=api_key,
                           cache_discovery=False,
                           static_discovery=False)
    
    def get_video_transcript(self, video_id: str) -> Optional[str]:
        """Get transcript for a YouTube video using the proxy if available."""
        try:
            print(f"Fetching transcript for video {video_id}...")
            
            # Add a small delay before each transcript request
            time.sleep(0.15)
            
            # Try to get the transcript with proxy if available
            proxies = getattr(self, 'session', {}).proxies if hasattr(self, 'session') else None
            
            # Get transcript with proxy
            transcript_list = YouTubeTranscriptApi.list_transcripts(
                video_id,
                proxies=proxies
            )
            
            # Try to get English transcript first, then any available
            try:
                transcript = transcript_list.find_transcript(['en'])
            except:
                transcript = next(iter(transcript_list), None)
            
            if not transcript:
                print(f"No transcript available for video {video_id}")
                return None
                
            # Format the transcript as plain text
            formatter = TextFormatter()
            transcript_text = formatter.format_transcript(transcript.fetch())
            return transcript_text
            
        except Exception as e:
            print(f"Error getting transcript for video {video_id}: {str(e)[:200]}...")
            return None
    
    def search_videos(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        """Search for videos and return their details with snippets and transcripts."""
        try:
            # Search for videos
            search_response = self.youtube.search().list(
                part="snippet",
                q=query,
                type="video",
                maxResults=min(max_results, 10),
                order="relevance"
            ).execute()
            
            videos = []
            for item in search_response.get('items', [])[:max_results]:
                try:
                    video_id = item.get('id', {}).get('videoId')
                    snippet = item.get('snippet', {})
                    
                    if not video_id or not snippet:
                        continue
                    
                    # Get video details including description
                    video_details = self.get_video_details(video_id)
                    
                    # Get transcript if available
                    transcript = self.get_video_transcript(video_id)
                    
                    # Get the first few lines of the description as "snippets"
                    description = video_details.get('description', '')
                    snippets = [line.strip() for line in description.split('\n') if line.strip()][:5]
                    
                    videos.append({
                        'title': snippet.get('title', 'No Title'),
                        'url': f"https://www.youtube.com/watch?v={video_id}",
                        'channel': snippet.get('channelTitle', 'Unknown Channel'),
                        'published_at': snippet.get('publishedAt', ''),
                        'description': description[:200] + '...' if len(description) > 200 else description,
                        'snippets': snippets if snippets else ["No description available"],
                        'has_transcript': transcript is not None,
                        'transcript_preview': transcript[:500] + '...' if transcript else None
                    })
                except Exception as e:
                    print(f"Error processing video: {e}")
                    continue
                    
            return videos
            
        except HttpError as e:
            print(f"YouTube API error: {e}")
            if e.resp.status == 403:
                print("This might be due to API quota exceeded. Please check your Google Cloud Console.")
            return []
        except Exception as e:
            print(f"Error searching for videos: {e}")
            return []
    
    def get_video_details(self, video_id: str) -> Dict[str, str]:
        """Get additional video details including full description."""
        try:
            response = self.youtube.videos().list(
                part="snippet",
                id=video_id
            ).execute()
            
            if not response.get('items'):
                return {"description": "No description available"}
                
            snippet = response['items'][0].get('snippet', {})
            return {
                "description": snippet.get('description', 'No description available'),
                "channel_title": snippet.get('channelTitle', 'Unknown channel')
            }
            
        except Exception as e:
            return {"description": f"Error fetching details: {str(e)[:100]}", "channel_title": "Unknown"}

def main():
    # Get YouTube API key from environment variables
    api_key = os.getenv('YOUTUBE_API_KEY')
    if not api_key:
        print("Error: YOUTUBE_API_KEY not found in environment variables.")
        print("Please create a .env file with YOUTUBE_API_KEY=your_api_key")
        return
    
    # Check for proxy in environment variables
    http_proxy = os.getenv('HTTP_PROXY')
    if http_proxy:
        print(f"Using HTTP proxy: {http_proxy}")
    
    searcher = YouTubeSearcher(api_key)
    
    try:
        while True:
            query = input("\nEnter your search query (or 'quit' to exit): ").strip()
            if query.lower() == 'quit':
                break
                
            print(f"\nSearching for videos about: {query}")
            videos = searcher.search_videos(query)
            
            if not videos:
                print("No videos found. Please try a different search term.")
                continue
                
            print(f"\nFound {len(videos)} videos:")
            for i, video in enumerate(videos, 1):
                print(f"\n{i}. {video['title']}")
                print(f"   Channel: {video['channel']}")
                print(f"   Published: {video['published_at']}")
                print(f"   URL: {video['url']}")
                print(f"   Has Transcript: {'Yes' if video['has_transcript'] else 'No'}")
                
                # Print first 200 characters of the description
                print(f"\n   Description: {video['description']}")
                
                # Print transcript preview if available
                if video.get('transcript_preview'):
                    print("\n   Transcript Preview:")
                    print(f"   {video['transcript_preview']}")
                
                # Print first few snippets from the description
                if 'snippets' in video and video['snippets']:
                    print("\n   Snippets:")
                    for j, snippet in enumerate(video['snippets'], 1):
                        print(f"      {j}. {snippet}")
                
                print("\n" + "-"*80)
                
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
    finally:
        print("\nThank you for using YouTube Search!")

if __name__ == "__main__":
    main()
