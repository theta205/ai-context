# Content Search Tools

This repository contains Python tools for searching and analyzing content from YouTube and Reddit.

## 1. YouTube Video Search by Transcript

A Python tool that finds the most relevant YouTube videos by analyzing video transcripts using semantic search.

### Features

- Searches YouTube for videos matching your query
- Analyzes video transcripts for semantic relevance
- Ranks videos based on content similarity to your query
- Returns top results with relevance scores and excerpts

### Setup

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Get a YouTube Data API v3 key from the [Google Cloud Console](https://console.cloud.google.com/)
4. Create a `.env` file and add your API key:
   ```
   YOUTUBE_API_KEY=your_api_key_here
   ```

### Usage

Run the script:
```bash
python youtube_search.py
```

Enter your search query when prompted. The script will return the most relevant videos based on transcript analysis.

## 2. Reddit Post Search with Comments

A Python tool that searches Reddit posts and retrieves full content including top comments using PRAW (Python Reddit API Wrapper).

### Features

- Searches Reddit posts using Google search
- Retrieves full post content including text and metadata
- Fetches top 5 comments for each post
- Saves results to a JSON file with timestamp
- Displays a summary of the first result in the console

### Additional Setup

1. Create a Reddit app at [Reddit App Preferences](https://www.reddit.com/prefs/apps/)
2. Add your Reddit API credentials to the `.env` file:
   ```
   REDDIT_CLIENT_ID=your_client_id_here
   REDDIT_CLIENT_SECRET=your_client_secret_here
   REDDIT_USER_AGENT=python:ai-context:v1.0 (by /u/yourusername)
   ```

### Usage

Run the script:
```bash
python reddit_search.py
```

Enter your search query when prompted. The script will:
1. Search for relevant Reddit posts
2. Save full results to a JSON file
3. Display a summary of the first result in the console

### Example Output
```
Found 2 Reddit posts about 'how to make deviled eggs':

Results have been saved to reddit_search_20250712_190523.json

Sample of the first result:

Title: Hitting tips for anyone that wants them
Author: u/Skrimpy6
Subreddit: r/Homeplate
Score: 13 points
Comments: 17
Posted: 2023-07-04T21:39:21
URL: https://reddit.com/r/Homeplate/comments/14qrszb/hitting_tips_for_anyone_that_wants_them/

Post Content:
i see a lot of people asking for hitting tips for themselves or for their kids...

Top 5 comments:
1. u/Just_Natural_9027 (8 points)
   The problem with a lot of this advice is feel is not real and is just going to cause paralysis by analysis...

## Requirements

- Python 3.7+
- YouTube Data API v3 key
- Reddit API credentials
- Internet connection

## License

MIT

## Notes

- For best results with the Reddit search, ensure your Reddit app has the necessary permissions
- The Reddit search uses Google to find relevant posts before fetching detailed information via PRAW
- Results are cached in JSON files with timestamps for future reference
