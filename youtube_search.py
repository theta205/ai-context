import os
import json
from typing import List, Dict, Tuple, Optional
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class YouTubeSearcher:
    def __init__(self, api_key: str):
        """Initialize the YouTube searcher with API key."""
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
    
    def search_videos(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search for videos on YouTube."""
        request = self.youtube.search().list(
            part="snippet",
            q=query,
            type="video",
            maxResults=max_results,
            videoDuration="medium",
            relevanceLanguage="en"
        )
        response = request.execute()
        return response.get('items', [])
    
    def get_transcript(self, video_id: str) -> Optional[str]:
        """Get transcript for a video if available."""
        try:
            transcript = YouTubeTranscriptApi.get_transcript(
                video_id, 
                languages=['en']
            )
            return ' '.join([t['text'] for t in transcript])
        except Exception as e:
            print(f"Could not retrieve transcript for video {video_id}: {str(e)}")
            return None
    
    def calculate_similarity(self, query: str, transcript: str) -> float:
        """Calculate cosine similarity between query and transcript."""
        query_embedding = self.model.encode([query])
        transcript_embedding = self.model.encode([transcript])
        return cosine_similarity(query_embedding, transcript_embedding)[0][0]
    
    def find_relevant_videos(self, query: str, top_n: int = 3) -> List[Dict]:
        """Find the most relevant videos based on transcript analysis."""
        # Search for videos
        videos = self.search_videos(query)
        
        # Process each video
        results = []
        for video in videos:
            video_id = video['id']['videoId']
            title = video['snippet']['title']
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Get and process transcript
            transcript = self.get_transcript(video_id)
            if not transcript:
                continue
                
            # Calculate relevance score
            try:
                score = self.calculate_similarity(query, transcript)
                # Get a short excerpt from the transcript
                excerpt = ' '.join(transcript.split()[:30]) + '...'
                
                results.append({
                    'title': title,
                    'url': url,
                    'score': float(score),
                    'excerpt': excerpt
                })
            except Exception as e:
                print(f"Error processing video {title}: {str(e)}")
        
        # Sort by score in descending order and return top N
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_n]

def main():
    # Get YouTube API key from environment variables
    api_key = os.getenv('YOUTUBE_API_KEY')
    if not api_key:
        print("Error: YOUTUBE_API_KEY not found in environment variables.")
        print("Please create a .env file with YOUTUBE_API_KEY=your_api_key")
        return
    
    searcher = YouTubeSearcher(api_key)
    
    while True:
        query = input("\nEnter your search query (or 'quit' to exit): ")
        if query.lower() == 'quit':
            break
            
        print(f"\nSearching for videos about: {query}")
        results = searcher.find_relevant_videos(query)
        
        if not results:
            print("No relevant videos with transcripts found.")
            continue
            
        print(f"\nTop {len(results)} most relevant videos:")
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['title']}")
            print(f"   URL: {result['url']}")
            print(f"   Relevance: {result['score']:.3f}")
            print(f"   Excerpt: {result['excerpt']}")

if __name__ == "__main__":
    main()
