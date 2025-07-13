import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv
from youtube_search import YouTubeSearcher

# Create output directory if it doesn't exist
os.makedirs('youtube_results', exist_ok=True)

def save_results(results, query, format_type):
    """Save search results to a file with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"youtube_results/youtube_{query}_{format_type}_{timestamp}"
    
    try:
        if format_type in ['raw', 'slim_json']:
            # For raw and slim_json, save as pretty-printed JSON
            with open(f"{filename}.json", 'w', encoding='utf-8') as f:
                if format_type == 'raw':
                    # Convert YouTubeVideo objects to dict for raw format
                    json_data = []
                    for video in results:
                        if hasattr(video, '__dict__'):
                            video_dict = video.__dict__.copy()
                            # Convert any non-serializable fields
                            if 'snippets' in video_dict:
                                video_dict['snippets'] = list(video_dict['snippets'])
                            # Ensure transcript is a string
                            if 'full_transcript' in video_dict and video_dict['full_transcript'] is not None:
                                if not isinstance(video_dict['full_transcript'], str):
                                    video_dict['full_transcript'] = str(video_dict['full_transcript'])
                            json_data.append(video_dict)
                        else:
                            json_data.append(video)
                    json.dump(json_data, f, indent=2, ensure_ascii=False)
                else:  # slim_json
                    # For slim_json, results should already be serializable
                    json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"Saved {len(results)} results to {filename}.json")
            
        elif format_type == 'slim_xml':
            with open(f"{filename}.xml", 'w', encoding='utf-8') as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                f.write('<youtube_results>\n')
                for item in results:
                    f.write('  <video>\n')
                    f.write(f'    {item}\n')
                    f.write('  </video>\n')
                f.write('</youtube_results>')
            print(f"Saved {len(results)} results to {filename}.xml")
            
    except Exception as e:
        print(f"Error saving {format_type} results: {e}")

# Load environment variables
load_dotenv()

# Get API key and proxy from environment variables
api_key = os.getenv('YOUTUBE_API_KEY')
proxy = os.getenv('HTTP_PROXY', '')

if not api_key:
    raise ValueError("YOUTUBE_API_KEY not found in environment variables. "
                    "Please create a .env file with your API key.")

# Initialize searcher
print(f"Using API key: {api_key[:4]}...{api_key[-4:]}")
if proxy:
    print(f"Using proxy: {proxy}")

searcher = YouTubeSearcher(api_key=api_key, proxy=proxy)

def test_search(query: str, max_results: int = 3):
    """Test search with all formats and save results to files."""
    print(f"\nSearching for: {query}")
    
    # Test all formats
    for format_type in ['raw', 'slim_json', 'slim_xml']:
        print(f"\n{'='*80}")
        print(f"Testing format: {format_type.upper()}")
        print(f"{'='*80}")
        
        try:
            # Perform search with the current format
            start_time = time.time()
            results = searcher.search_videos(
                query=query,
                max_results=max_results,
                format=format_type,
                include_full_transcript=True
            )
            elapsed = time.time() - start_time
            print(f"Search completed in {elapsed:.2f} seconds")
            # Save results to file
            save_results(
                results,
                query.lower().replace(' ', '_'),
                format_type
            )
            
            # Print sample output
            if results:
                print(f"\nSample output ({format_type}):")
                sample = results[0]
                if format_type == 'raw':
                    if hasattr(sample, 'title'):
                        print(f"Title: {sample.title}")
                        print(f"URL: {sample.url}")
                        print(f"Channel: {sample.channel}")
                        print(f"Has Transcript: {sample.has_transcript}")
                        if sample.full_transcript:
                            print("\nFull transcript available in saved file")
                    else:
                        print(json.dumps(sample, indent=2, ensure_ascii=False)[:500] + '...')
                elif format_type == 'slim_json':
                    print(json.dumps(sample, indent=2, ensure_ascii=False)[:500] + '...')
                else:  # slim_xml
                    print(str(sample)[:500] + '...')
            
            print(f"\nSearch completed in {elapsed:.2f} seconds")
            
        except Exception as e:
            print(f"Error with format {format_type}: {e}")

if __name__ == "__main__":
    test_search("python programming", max_results=3)
    print("\nAll searches completed. Check the 'youtube_results' directory for output files.")