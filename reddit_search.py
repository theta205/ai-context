import os
import json
import praw
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
from googlesearch import search
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class RedditSearcher:
    def __init__(self):
        """Initialize the Reddit searcher with PRAW and Google search."""
        # Initialize PRAW with environment variables
        self.reddit = praw.Reddit(
            client_id=os.getenv('REDDIT_CLIENT_ID'),
            client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
            user_agent=os.getenv('REDDIT_USER_AGENT', 'python:ai-context:v1.0 (by /u/yourusername)')
        )
    
    def _extract_post_id(self, url: str) -> Optional[str]:
        """Extract the post ID from a Reddit URL."""
        try:
            # Handle different Reddit URL formats
            if 'comments/' in url:
                # Format: https://www.reddit.com/r/subreddit/comments/post_id/title/
                match = re.search(r'comments/([a-z0-9]+)', url)
                if match:
                    return match.group(1)
            else:
                # Format: https://www.reddit.com/r/subreddit/.../post_id/
                path_parts = urlparse(url).path.rstrip('/').split('/')
                if path_parts and path_parts[-1]:
                    return path_parts[-1]
            return None
        except Exception as e:
            print(f"Error extracting post ID: {str(e)}")
            return None
    
    def _get_reddit_data(self, post_id: str) -> Optional[Dict[str, Any]]:
        """Fetch post data and comments using PRAW."""
        try:
            submission = self.reddit.submission(id=post_id)
            
            # Get post data
            post_data = {
                'title': submission.title,
                'author': str(submission.author) if submission.author else '[deleted]',
                'subreddit': submission.subreddit.display_name,
                'score': submission.score,
                'num_comments': submission.num_comments,
                'url': f"https://reddit.com{submission.permalink}",
                'selftext': submission.selftext,
                'created_utc': datetime.utcfromtimestamp(submission.created_utc).isoformat(),
                'comments': []
            }
            
            # Get top 5 comments
            submission.comments.replace_more(limit=0)  # Remove MoreComments objects
            for i, comment in enumerate(submission.comments[:5]):
                post_data['comments'].append({
                    'author': str(comment.author) if comment.author else '[deleted]',
                    'score': comment.score,
                    'body': comment.body,
                    'created_utc': datetime.utcfromtimestamp(comment.created_utc).isoformat()
                })
            
            return post_data
            
        except Exception as e:
            print(f"Error fetching Reddit data: {str(e)}")
            return None
    
    def search_reddit_via_google(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search for Reddit posts using Google and fetch full content using PRAW.
        
        Args:
            query: The search query string
            num_results: Number of results to return (default: 5)
            
        Returns:
            List of dictionaries containing post details and comments
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
            
            results = []
            for url in search_results:
                # Ensure it's a Reddit URL and not an ad or tracking URL
                if 'reddit.com' in url and not any(x in url for x in ['/ads/', '/advertising/', '/settings/']):
                    # Clean the URL (remove tracking parameters)
                    parsed = urlparse(url)
                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    
                    # Get post ID and fetch data using PRAW
                    post_id = self._extract_post_id(clean_url)
                    if post_id:
                        post_data = self._get_reddit_data(post_id)
                        if post_data:
                            results.append(post_data)
                            if len(results) >= num_results:
                                break
            
            return results
            
        except Exception as e:
            print(f"Error searching for Reddit posts: {str(e)}")
            return []

def main():
    try:
        # Check if credentials are set
        if not all([os.getenv('REDDIT_CLIENT_ID'), os.getenv('REDDIT_CLIENT_SECRET')]):
            print("Error: Reddit API credentials not found.")
            print("Please create a .env file with the following variables:")
            print("REDDIT_CLIENT_ID=your_client_id_here")
            print("REDDIT_CLIENT_SECRET=your_client_secret_here")
            print("REDDIT_USER_AGENT=your_user_agent_here (optional)")
            return
        
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
            results = searcher.search_reddit_via_google(query, num_results=2)  # Reduced to 2 for demo
            
            # Display results
            if not results:
                print("No Reddit posts found.")
                continue
            
            print(f"\nFound {len(results)} Reddit posts about '{query}':\n")
            
            # Save results to a JSON file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"reddit_search_{timestamp}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            print(f"Results have been saved to {filename}")
            print("\nSample of the first result:")
            
            # Display first result as sample
            if results:
                first_result = results[0]
                print(f"\nTitle: {first_result['title']}")
                print(f"Author: u/{first_result['author']}")
                print(f"Subreddit: r/{first_result['subreddit']}")
                print(f"Score: {first_result['score']} points")
                print(f"Comments: {first_result['num_comments']}")
                print(f"Posted: {first_result['created_utc']}")
                print(f"URL: {first_result['url']}")
                
                if first_result['selftext']:
                    print("\nPost Content:")
                    print(first_result['selftext'][:500] + ("..." if len(first_result['selftext']) > 500 else ""))
                
                if first_result['comments']:
                    print(f"\nTop {len(first_result['comments'])} comments:")
                    for i, comment in enumerate(first_result['comments'], 1):
                        print(f"\n{i}. u/{comment['author']} ({comment['score']} points)")
                        print(comment['body'][:200] + ("..." if len(comment['body']) > 200 else ""))
    
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()