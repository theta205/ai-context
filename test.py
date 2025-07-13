import os
from dotenv import load_dotenv
from reddit_search import RedditSearcher, save_results_to_file

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # Initialize the RedditSearcher with environment variables
    searcher = RedditSearcher(
        client_id=os.getenv('REDDIT_CLIENT_ID'),
        client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
        user_agent=os.getenv('REDDIT_USER_AGENT', 'python:ai-context:v1.0')
    )
    
    # Example search
    query = "best 1440p monitors"
    print(f"Searching for: {query}")
    
    try:
        # Perform the search with timing enabled
        results = searcher.search(
            query, 
            num_results=3, 
            format='slim_xml',  # or 'slim_json' or 'slim_xml'
            include_comments=True,
            comment_limit=5
        )
        
        if not results:
            print("No results found.")
            return
        else:
            print(f"Found {len(results)} results.")    
        # Save results to a file
        filename = save_results_to_file(results)
        print(f"\nFound {len(results)} results. Saved to {filename}")
        
        # Print timing summary
        print("\n=== Performance Summary ===")
        searcher.print_timings()
    
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()