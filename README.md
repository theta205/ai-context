# YouTube Video Search by Transcript

A Python tool that finds the most relevant YouTube videos by analyzing video transcripts using semantic search.

## Features

- Searches YouTube for videos matching your query
- Analyzes video transcripts for semantic relevance
- Ranks videos based on content similarity to your query
- Returns top results with relevance scores and excerpts

## Setup

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

## Usage

Run the script:
```bash
python youtube_search.py
```

Enter your search query when prompted. The script will return the most relevant videos based on transcript analysis.

## Example Output
```
Enter your search query (or 'quit' to exit): machine learning basics

Searching for videos about: machine learning basics

Top 3 most relevant videos:

1. Machine Learning Basics | What Is Machine Learning? | Introduction To Machine Learning
   URL: https://www.youtube.com/watch?v=example1
   Relevance: 0.857
   Excerpt: In this video, we'll cover the basics of machine learning...

2. Machine Learning Full Course - Learn Machine Learning 10 Hours
   URL: https://www.youtube.com/watch?v=example2
   Relevance: 0.821
   Excerpt: This complete machine learning course will take you from the basics...
```

## Requirements

- Python 3.7+
- YouTube Data API v3 key
- Internet connection

## License

MIT
