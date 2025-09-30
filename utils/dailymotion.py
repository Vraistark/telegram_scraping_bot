import requests
from typing import List, Dict

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

        results.append({
            "id": video_data.get('id'),
            "title": video_data.get('title'),
            "description": video_data.get('description'),
            "created_time": video_data.get('created_time'),
            "duration": video_data.get('duration'),
            "views_total": video_data.get('views_total'),
            "likes_total": video_data.get('likes_total'),
            "owner": video_data.get('owner'),
            "tags": ', '.join(video_data.get('tags', [])),
            "channel_name": owner_data.get('username', ''),
            "following_total": owner_data.get('following_total', 0)
        })
    return results
