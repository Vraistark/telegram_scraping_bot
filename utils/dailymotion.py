import requests
from typing import List, Dict
from datetime import datetime, timedelta

def seconds_to_hhmmss(seconds: int) -> str:
    return str(timedelta(seconds=seconds))

def unix_to_ddmmyyyy(timestamp: int) -> str:
    return datetime.utcfromtimestamp(timestamp).strftime('%d-%m-%Y')

def fetch_dailymotion_data(urls: List[str]) -> List[Dict]:
    results = []
    for url in urls:
        video_id = url.split('/')[-1]
        api_url = f'https://api.dailymotion.com/video/{video_id}?fields=id,title,description,created_time,duration,views_total,likes_total,owner,tags'
        resp = requests.get(api_url)
        if resp.status_code != 200:
            results.append({"error": f"Failed to fetch data for {url}"})
            continue
        video_data = resp.json()

        owner_id = video_data.get('owner', '')
        owner_resp = requests.get(f'https://api.dailymotion.com/user/{owner_id}?fields=id,username,following_total')
        owner_data = owner_resp.json() if owner_resp.status_code == 200 else {}

        created_time = video_data.get('created_time')
        duration = video_data.get('duration')

        results.append({
            "id": video_data.get('id'),
            "title": video_data.get('title'),
            "description": video_data.get('description'),
            "created_time": unix_to_ddmmyyyy(created_time) if created_time else "N/A",
            "duration": seconds_to_hhmmss(duration) if duration else "N/A",
            "views_total": video_data.get('views_total'),
            "likes_total": video_data.get('likes_total'),
            "owner": video_data.get('owner'),
            "tags": ', '.join(video_data.get('tags', [])),
            "channel_name": owner_data.get('username', ''),
            "following_total": owner_data.get('following_total', 0)
        })
    return results
