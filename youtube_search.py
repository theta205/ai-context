import os
from typing import List, Dict, Any, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class YouTubeSearcher:
    def __init__(self, api_key: str):
        """Initialize the YouTube searcher with API key."""
        self.youtube = build('youtube', 'v3',
                           developerKey=api_key,
                           cache_discovery=False,
                           static_discovery=False)
    
    def search_videos(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        """Search for videos and return their details with snippets."""
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
                    
                    # Get the first few lines of the description as "snippets"
                    description = video_details.get('description', '')
                    snippets = [line.strip() for line in description.split('\n') if line.strip()][:5]
                    
                    videos.append({
                        'title': snippet.get('title', 'No Title'),
                        'url': f"https://www.youtube.com/watch?v={video_id}",
                        'channel': snippet.get('channelTitle', 'Unknown Channel'),
                        'published_at': snippet.get('publishedAt', ''),
                        'description': description[:200] + '...' if len(description) > 200 else description,
                        'snippets': snippets if snippets else ["No description available"]
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
            return {"description": f"Error fetching details: {str(e)[:100]}"}

def main():
    # Get YouTube API key from environment variables
    api_key = os.getenv('YOUTUBE_API_KEY')
    if not api_key:
        print("Error: YOUTUBE_API_KEY not found in environment variables.")
        print("Please create a .env file with YOUTUBE_API_KEY=your_api_key")
        return
    
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
                
                # Print first 200 characters of the description
                print(f"   Description: {video['description']}")
                
                # Print first few snippets from the description
                if 'snippets' in video and video['snippets']:
                    print("   Snippets:")
                    for j, snippet in enumerate(video['snippets'], 1):
                        print(f"      {j}. {snippet}")
                
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
    finally:
        print("\nThank you for using YouTube Search!")

if __name__ == "__main__":
    main()
