import re
import requests
from typing import List, Dict

import os

API_KEYS = [
    os.getenv("YOUR_YOUTUBE_API_KEY_1"),
    os.getenv("YOUR_YOUTUBE_API_KEY_2"),
    # Add more keys as needed
]


current_key_index = 0

def get_next_api_key():
    global current_key_index
    key = API_KEYS[current_key_index]
    current_key_index = (current_key_index + 1) % len(API_KEYS)
    return key

def extract_video_id(url: str) -> str:
    try:
        regex = r'(?:v=|\/shorts\/|\/live\/|\.be\/|\/embed\/|\/watch\?v=|\/watch\?.*?v=)([a-zA-Z0-9_-]{11})'
        match = re.search(regex, url)
        if match:
            return match.group(1)
        return None
    except Exception:
        return None

def format_duration(duration: str) -> str:
    import isodate
    try:
        duration_sec = int(isodate.parse_duration(duration).total_seconds())
        hours = duration_sec // 3600
        minutes = (duration_sec % 3600) // 60
        seconds = duration_sec % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    except Exception:
        return "00:00:00"

def fetch_youtube_data(urls: List[str]) -> List[Dict]:
    video_ids = [extract_video_id(url) for url in urls]
    video_ids = [vid for vid in video_ids if vid]

    if not video_ids:
        return []

    all_results = []
    CHUNK_SIZE = 50
    for i in range(0, len(video_ids), CHUNK_SIZE):
        chunk = video_ids[i:i+CHUNK_SIZE]
        api_key = get_next_api_key()
        endpoint = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics,contentDetails&id={','.join(chunk)}&key={api_key}"
        resp = requests.get(endpoint)
        if resp.status_code != 200:
            continue
        data = resp.json()
        for item in data.get('items', []):
            snippet = item.get('snippet', {})
            stats = item.get('statistics', {})
            content = item.get('contentDetails', {})
            duration = format_duration(content.get('duration', 'PT0S'))

            all_results.append({
                "title": snippet.get('title', ''),
                "videoId": item.get('id', ''),
                "views": stats.get('viewCount', '0'),
                "duration": duration,
                "channelId": snippet.get('channelId', ''),
                "channelTitle": snippet.get('channelTitle', ''),
                "publishDate": snippet.get('publishedAt', '').split("T")[0],
                "likes": stats.get('likeCount', '0'),
                "comments": stats.get('commentCount', '0'),
                "thumbnail": snippet.get('thumbnails', {}).get('high', {}).get('url', '')
            })
    return all_results
