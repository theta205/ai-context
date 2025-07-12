import os
import json
import re
import logging
from typing import List, Dict, Any, Optional, Union
from urllib.parse import urlparse
from datetime import datetime
from dataclasses import dataclass, asdict
import xml.etree.ElementTree as ET
import praw
from googlesearch import search
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

@dataclass
class RedditComment:
    """Data class representing a Reddit comment."""
    author: str
    score: int
    body: str
    created_utc: str

@dataclass
class RedditPost:
    """Data class representing a Reddit post with its top comments."""
    title: str
    author: str
    subreddit: str
    score: int
    num_comments: int
    url: str
    selftext: str
    created_utc: str
    comments: List[RedditComment]

class RedditSearcher:
    """A class to search and fetch Reddit posts and comments.
    
    This class provides methods to search for Reddit posts using Google search
    and fetch detailed information including top comments using PRAW.
    
    Args:
        client_id: Reddit API client ID
        client_secret: Reddit API client secret
        user_agent: User agent string for the Reddit API
    """
    
    # Class-level constant for the site to search
    SEARCH_SITE = 'reddit.com'
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Initialize the Reddit searcher with API credentials."""
        self.client_id = client_id or os.getenv('REDDIT_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('REDDIT_CLIENT_SECRET')
        self.user_agent = user_agent or os.getenv(
            'REDDIT_USER_AGENT',
            'python:ai-context:v1.0 (by /u/yourusername)'
        )
        
        if not all([self.client_id, self.client_secret]):
            logger.warning(
                "Reddit API credentials not provided. Some functionality may be limited."
            )
        
        # Initialize PRAW client
        self.reddit = praw.Reddit(
            client_id=self.client_id,
            client_secret=self.client_secret,
            user_agent=self.user_agent
        )
    
    def _extract_post_id(self, url: str) -> Optional[str]:
        """Extract the post ID from a Reddit URL.
        
        Args:
            url: The Reddit post URL
            
        Returns:
            The post ID if found, None otherwise
        """
        try:
            # Handle different Reddit URL formats
            if 'comments/' in url:
                match = re.search(r'comments/([a-z0-9]+)', url)
                return match.group(1) if match else None
            
            # Handle short URLs and other formats
            path_parts = urlparse(url).path.rstrip('/').split('/')
            return path_parts[-1] if path_parts and path_parts[-1] else None
            
        except Exception as e:
            logger.error(f"Error extracting post ID from URL {url}: {e}")
            return None
    
    def _get_post_data(self, post_id: str) -> Optional[RedditPost]:
        """Fetch post data and comments using PRAW.
        
        Args:
            post_id: The Reddit post ID
            
        Returns:
            RedditPost object if successful, None otherwise
        """
        try:
            submission = self.reddit.submission(id=post_id)
            
            # Get top 5 comments
            submission.comments.replace_more(limit=0)
            comments = [
                RedditComment(
                    author=str(comment.author) if comment.author else '[deleted]',
                    score=comment.score,
                    body=comment.body,
                    created_utc=datetime.utcfromtimestamp(comment.created_utc).isoformat()
                )
                for comment in submission.comments[:5]
            ]
            
            return RedditPost(
                title=submission.title,
                author=str(submission.author) if submission.author else '[deleted]',
                subreddit=submission.subreddit.display_name,
                score=submission.score,
                num_comments=submission.num_comments,
                url=f"https://reddit.com{submission.permalink}",
                selftext=submission.selftext,
                created_utc=datetime.utcfromtimestamp(submission.created_utc).isoformat(),
                comments=comments
            )
            
        except Exception as e:
            logger.error(f"Error fetching Reddit data for post {post_id}: {e}")
            return None
    
    def _format_slim_json(self, post: RedditPost) -> dict:
        """Format a RedditPost into a slim JSON format.
        
        Args:
            post: The RedditPost to format
            
        Returns:
            dict: A dictionary with title, subreddit, url, selftext, and comments
        """
        return {
            "title": post.title,
            "subreddit": post.subreddit,
            "url": post.url,
            "selftext": post.selftext,
            "comments": [
                {"body": comment.body}
                for comment in post.comments
            ]
        }

    def _format_slim_xml(self, post: RedditPost) -> str:
        """Format a RedditPost into a slim XML format optimized for LLM processing.
        
        Args:
            post: The RedditPost to format
            
        Returns:
            str: XML string with simplified structure and unescaped characters
        """
        # Unescape special characters in text content
        from html import unescape
        
        # Build XML content with clear section separation
        lines = []
        
        # Title section
        lines.append('<title>' + unescape(post.title) + '</title>\n')
        lines.append('<subreddit>' + post.subreddit + '</subreddit>\n')
        lines.append('<url>' + post.url + '</url>\n')
        
        # Selftext section (if exists)
        if post.selftext:
            lines.append('<selftext>')
            lines.append(unescape(post.selftext))
            lines.append('</selftext>\n')
        
        # Comments section (if exists)
        if post.comments:
            lines.append('<comments>\n')
            for comment in post.comments:
                # Clean and unescape comment body
                body = unescape(comment.body)
                # Replace HTML entities and normalize whitespace
                body = ' '.join(body.split())
                lines.append('<comment>' + body + '</comment>\n')
            lines.append('</comments>')
        
        return ''.join(lines)

    def search(
        self,
        query: str,
        num_results: int = 5,
        format: str = 'raw'
    ) -> Union[List[RedditPost], List[Union[dict, str]]]:
        """Search for Reddit posts using Google search.
        
        Args:
            query: The search query
            num_results: Maximum number of results to return (1-25, default: 5)
            format: Output format - 'raw' for full objects, 'slim_json' for minimal JSON,
                   'slim_xml' for minimal XML
            
        Returns:
            List of RedditPost objects or formatted strings, depending on format
            
        Raises:
            ValueError: If query is empty, num_results is invalid, or format is invalid
        """
        if format not in ['raw', 'slim_json', 'slim_xml']:
            raise ValueError("format must be 'raw', 'slim_json', or 'slim_xml'")
        
        if not query:
            raise ValueError("Search query cannot be empty")
            
        if not (1 <= num_results <= 25):
            raise ValueError("num_results must be between 1 and 25")
            
        search_query = f"{query} site:{self.SEARCH_SITE}"
        results = []
        
        try:
            # Search for Reddit posts using Google
            for url in search(term=search_query, num_results=num_results * 2):
                try:
                    # Clean the URL and extract post ID
                    parsed = urlparse(url)
                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    post_id = self._extract_post_id(clean_url)
                    
                    if post_id:
                        # Fetch post data
                        post_data = self._get_post_data(post_id)
                        if post_data:
                            if format == 'slim_json':
                                results.append(self._format_slim_json(post_data))
                            elif format == 'slim_xml':
                                results.append(self._format_slim_xml(post_data))
                            else:
                                results.append(post_data)
                            if len(results) >= num_results:
                                break
                                
                except Exception as e:
                    logger.warning(f"Error processing URL {url}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error performing search: {e}")
            
        return results

def save_results_to_file(posts: List[Union[RedditPost, Dict, str]], filename: str = None) -> str:
    """Save search results to a JSON or XML file.
    
    Args:
        posts: List of RedditPost objects or dictionaries
        filename: Output filename (default: reddit_search_<timestamp>.json or reddit_search_<timestamp>.xml)
        
    Returns:
        The name of the output file
    """
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if isinstance(posts[0], str):
            filename = f"reddit_search_{timestamp}.xml"
        else:
            filename = f"reddit_search_{timestamp}.json"
    
    # Convert RedditPost objects to dictionaries if needed
    if not isinstance(posts[0], str):
        serializable_posts = [
            asdict(post) if hasattr(post, '__dataclass_fields__') else post
            for post in posts
        ]
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(serializable_posts, f, indent=2, ensure_ascii=False)
    else:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(posts[0])
    
    return filename

def main():
    """Command-line interface for the Reddit search tool."""
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
            query = input("\nEnter your search query (or 'quit' to exit): ").strip()
            if query.lower() == 'quit':
                break
                
            if not query:
                print("Please enter a search query.")
                continue
                
            print(f"\nSearching for: {query}")
            results = searcher.search(query)
            
            if not results:
                print("No results found.")
                continue
                
            # Save results to file
            filename = save_results_to_file(results)
            print(f"\nFound {len(results)} results. Saved to {filename}")
            
            # Display first result as a sample
            first_result = results[0]
            if isinstance(first_result, str):
                print("\nSample of the first result:")
                print(first_result)
            else:
                print("\nSample of the first result:")
                print(f"\nTitle: {first_result.title}")
                print(f"Author: u/{first_result.author}")
                print(f"Subreddit: r/{first_result.subreddit}")
                print(f"Score: {first_result.score} points")
                print(f"Comments: {first_result.num_comments}")
                print(f"Posted: {first_result.created_utc}")
                print(f"URL: {first_result.url}")
                
                if first_result.selftext:
                    print("\nPost Content:")
                    print(first_result.selftext[:500] + 
                         ("..." if len(first_result.selftext) > 500 else ""))
                
                if first_result.comments:
                    print(f"\nTop {len(first_result.comments)} comments:")
                    for i, comment in enumerate(first_result.comments, 1):
                        print(f"\n{i}. u/{comment.author} ({comment.score} points)")
                        print(comment.body[:200] + 
                             ("..." if len(comment.body) > 200 else ""))
    
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()