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
    
    def __extract_post_id(self, url: str) -> Optional[str]:
        """Extract Reddit post ID from URL."""
        patterns = [
            r"reddit\.com/r/\w+/comments/(\w+)",
            r"redd\.it/(\w+)"
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def __get_post_data(self, post_id: str) -> Optional[RedditPost]:
        """Fetch and process data for a single Reddit post."""
        try:
            submission = self.reddit.submission(id=post_id)
            submission.comments.replace_more(limit=0)  # Load top-level comments only
            
            # Get top 5 comments by score
            comments = sorted(
                [
                    RedditComment(
                        author=comment.author.name if comment.author else "[deleted]",
                        score=comment.score,
                        body=comment.body,
                        created_utc=datetime.utcfromtimestamp(comment.created_utc).isoformat()
                    )
                    for comment in submission.comments
                    if not comment.stickied
                ],
                key=lambda x: x.score,
                reverse=True
            )[:5]
            
            return RedditPost(
                title=submission.title,
                author=submission.author.name if submission.author else "[deleted]",
                subreddit=submission.subreddit.display_name,
                score=submission.score,
                num_comments=submission.num_comments,
                created_utc=datetime.utcfromtimestamp(submission.created_utc).isoformat(),
                url=f"https://reddit.com{submission.permalink}",
                selftext=submission.selftext,
                comments=comments
            )
            
        except Exception as e:
            logger.error(f"Error fetching post {post_id}: {e}")
            return None

    def __format_slim_json(self, post: RedditPost) -> dict:
        """Format a RedditPost into a minimal JSON format."""
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

    def __format_slim_xml(self, post: RedditPost) -> str:
        """Format a RedditPost into a slim XML format optimized for LLM processing."""
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
                    post_id = self.__extract_post_id(clean_url)
                    
                    if post_id:
                        # Fetch post data
                        post_data = self.__get_post_data(post_id)
                        if post_data:
                            if format == 'slim_json':
                                results.append(self.__format_slim_json(post_data))
                            elif format == 'slim_xml':
                                results.append(self.__format_slim_xml(post_data))
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