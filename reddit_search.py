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
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
        self.reddit = self._setup_reddit()
        self.timings = {}
        
    @staticmethod
    def _timeit(func):
        """Decorator to time function execution."""
        def wrapper(self, *args, **kwargs):
            start_time = time.time()
            result = func(self, *args, **kwargs)
            elapsed = time.time() - start_time
            
            # Store timing info
            func_name = func.__name__
            if not hasattr(self, 'timings'):
                self.timings = {}
                
            if func_name not in self.timings:
                self.timings[func_name] = []
                
            self.timings[func_name].append(elapsed)
            
            logger.debug(f"{func_name} executed in {elapsed:.4f} seconds")
            return result
        return wrapper
        
    def print_timings(self):
        """Print timing statistics for all tracked functions."""
        print("\n=== Function Timings ===")
        for func_name, times in self.timings.items():
            if times:
                print(f"{func_name}: {sum(times)/len(times):.4f}s avg ({len(times)} calls)")
    
    @_timeit
    def _setup_reddit(self):
        """Set up PRAW Reddit instance."""
        return praw.Reddit(
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

    @_timeit
    def __get_post_data(self, post_id: str, include_comments: bool = True, comment_limit: int = 5) -> Optional[RedditPost]:
        """Fetch and process data for a single Reddit post."""
        try:
            time_start = time.time()
            submission = self.reddit.submission(id=post_id)
            submission.comments.replace_more(limit=0)  # Load top-level comments only
            time_end = time.time()
            print(f"time elapsed for PRAW: {time_end - time_start} in seconds")
            
            # Get top comments by score
            comments = []
            if include_comments:
                time_start = time.time()
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
                )[:comment_limit]
                time_end = time.time()
                print(f"time elapsed: {time_end - time_start} in seconds")
            
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

    def __format_slim_xml(self, posts: Union[RedditPost, List[RedditPost]]) -> str:
        """Format one or more RedditPost objects into a slim XML format optimized for LLM processing.
        
        Args:
            posts: A single RedditPost or a list of RedditPost objects
            
        Returns:
            str: XML string containing all posts
        """
        from html import unescape        
        # Initialize the lines list
        lines = []
        #posts = {"posts": posts}
        # Ensure we're working with a list, even if a single post is provided
        if not isinstance(posts, list):
            posts = [posts]
        
        # Start building the XML document
        lines.append('<reddit_posts>')
        
        for post in posts:
            if not post:
                continue
                
            try:
                # Post wrapper
                lines.append('<post>')
                
                # Post metadata
                if hasattr(post, 'title') and post.title:
                    lines.append(f'<title>{unescape(str(post.title))}</title>')
                elif isinstance(post, dict) and 'title' in post:
                    lines.append(f'<title>{unescape(str(post["title"]))}</title>')
                    
                if hasattr(post, 'subreddit') and post.subreddit:
                    lines.append(f'<subreddit>{post.subreddit}</subreddit>')
                elif isinstance(post, dict) and 'subreddit' in post:
                    lines.append(f'<subreddit>{post["subreddit"]}</subreddit>')
                    
                if hasattr(post, 'url') and post.url:
                    lines.append(f'<url>{post.url}</url>')
                elif isinstance(post, dict) and 'url' in post:
                    lines.append(f'<url>{post["url"]}</url>')
                
                # Selftext (if exists)
                selftext = None
                if hasattr(post, 'selftext') and post.selftext:
                    selftext = post.selftext
                elif isinstance(post, dict) and 'selftext' in post:
                    selftext = post['selftext']
                    
                if selftext:
                    lines.append('<selftext>')
                    lines.append(f'{unescape(str(selftext))}')
                    lines.append('</selftext>')
                
                # Comments (if exist)
                comments = []
                if hasattr(post, 'comments') and post.comments:
                    comments = post.comments
                elif isinstance(post, dict) and 'comments' in post:
                    comments = post['comments']
                    
                if comments:
                    lines.append('<comments>')
                    for comment in comments:
                        try:
                            body = None
                            if hasattr(comment, 'body') and comment.body:
                                body = comment.body
                            elif isinstance(comment, dict) and 'body' in comment:
                                body = comment['body']
                                
                            if body:
                                body = ' '.join(unescape(str(body)).split())
                                lines.append(f'<comment>{body}</comment>')
                        except Exception as e:
                            logger.error(f"Error formatting comment: {e}")
                            continue
                    lines.append('</comments>')
                
                lines.append('</post>')
                
            except Exception as e:
                logger.error(f"Error formatting post: {e}")
                continue
        
        lines.append('</reddit_posts>')
        return '\n'.join(lines)

    @_timeit
    def search(
        self,
        query: str,
        num_results: int = 5,
        format: str = 'raw',
        include_comments: bool = True,
        comment_limit: int = 5
    ) -> Union[List[RedditPost], List[Union[dict, str]]]:
        """Search for Reddit posts using Google search.
        
        Args:
            query: The search query
            num_results: Maximum number of results to return (1-25, default: 5)
            format: Output format - 'raw' for full objects, 'slim_json' for minimal JSON,
                   'slim_xml' for minimal XML
            include_comments: Whether to include comments in the results (default: True)
            comment_limit: Maximum number of comments to include per post (default: 5)
        
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
            time_start = time.time()
            posts = []
            for url in search(term=search_query, num_results=num_results * 2):
                time_end = time.time()
                print(f"time elapsed for Google search: {time_end - time_start} in seconds")
                try:
                    # Clean the URL and extract post ID
                    parsed = urlparse(url)
                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    post_id = self.__extract_post_id(clean_url)
                    
                    if post_id:
                        # Fetch post data
                        post_data = self.__get_post_data(
                            post_id, 
                            include_comments=include_comments, 
                            comment_limit=comment_limit
                        )
                        if post_data:
                            if format in ['raw', 'slim_json']:
                                if format == 'slim_json':
                                    results.append(self.__format_slim_json(post_data))
                                else:
                                    results.append(post_data)
                            else:  # slim_xml - collect posts first
                                posts.append(post_data)
                            
                            if len(posts) + len(results) >= num_results:
                                break
                                
                except Exception as e:
                    logger.warning(f"Error processing URL {url}: {e}")
                    continue
                    
            # If using slim_xml format, format all posts at once
            if format == 'slim_xml' and posts:
                results.append(self.__format_slim_xml(posts[:num_results]))
                
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