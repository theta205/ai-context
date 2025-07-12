import os
from typing import List, Dict, Any, Optional
from googlesearch import search
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class RedditSearcher:
    def __init__(self):
        """Initialize the Reddit searcher."""
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def _get_reddit_title(self, url: str) -> str:
        """Extract the title from a Reddit URL."""
        try:
            # Parse the URL
            parsed = urlparse(url)
            # Get the last part of the path
            path_parts = parsed.path.rstrip('/').split('/')
            if path_parts and path_parts[-1]:
                # Replace underscores with spaces and capitalize first letters
                title = path_parts[-1].replace('_', ' ').title()
                return title
            return "[Title not found]"
        except Exception as e:
            print(f"Error parsing URL: {str(e)}")
            return "[Title not found]"
    
    def search_reddit_via_google(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        """
        Search for Reddit posts using Google and return the top results.
        
        Args:
            query: The search query string
            num_results: Number of results to return (default: 5)
            
        Returns:
            List of dictionaries containing 'title' and 'url' of Reddit posts
        """
        try:
            # Add site:reddit.com to the query to only get Reddit results
            search_query = f"{query} site:reddit.com"
            
            # Use Google to search for Reddit posts
            search_results = search(
                search_query,
                num_results=num_results * 2,  # Get more results in case some aren't valid
                lang='en',
                sleep_interval=2  # Be nice to Google's servers
            )
            
            # Filter and process results
            results = []
            for url in search_results:
                # Ensure it's a Reddit URL and not an ad or tracking URL
                if 'reddit.com' in url and not any(x in url for x in ['/ads/', '/advertising/', '/settings/']):
                    # Clean the URL (remove tracking parameters)
                    parsed = urlparse(url)
                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    
                    # Get the title from the page
                    title = self._get_reddit_title(clean_url)
                    
                    results.append({
                        'title': title,
                        'url': clean_url
                    })
                    
                    if len(results) >= num_results:
                        break
            
            return results
            
        except Exception as e:
            print(f"Error searching Google for Reddit posts: {str(e)}")
            return []

def main():
    try:
        searcher = RedditSearcher()
        
        while True:
            # Get search query from user
            query = input("\nEnter your search query (or 'quit' to exit): ").strip()
            if not query:
                print("No search query provided.")
                continue
            if query.lower() == 'quit':
                break
            
            # Perform the search
            print(f"\nSearching for Reddit posts about: {query}")
            results = searcher.search_reddit_via_google(query, num_results=5)
            
            # Display results
            if not results:
                print("No Reddit posts found.")
                continue
            
            print(f"\nTop {len(results)} Reddit posts about '{query}':")
            for i, result in enumerate(results, 1):
                print(f"\n{i}. {result['title']}")
                print(f"   {result['url']}")
    
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()