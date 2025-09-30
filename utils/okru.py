import requests
from typing import List, Dict
import re
from datetime import datetime

def seconds_to_hhmmss(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02}:{minutes:02}:{secs:02}"

def iso_to_ddmmyyyy(date_str: str) -> str:
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%d-%m-%Y')
    except Exception:
        return "N/A"

def fetch_okru_data(urls: List[str]) -> List[Dict]:
    results = []
    for url in urls:
        try:
            resp = requests.get(url)
            if resp.status_code != 200:
                results.append({"error": f"Failed to fetch {url}"})
                continue
            html = resp.text

            title = re.search(r'<meta property="og:title" content="([^"]+)"', html)
            duration_match = re.search(r'class="vid-card_duration">([\d:]+)</div>', html)
            duration_in_seconds = None
            if duration_match:
                parts = list(map(int, duration_match.group(1).split(':')))
                if len(parts) == 3:
                    duration_in_seconds = parts[0]*3600 + parts[1]*60 + parts[2]
                elif len(parts) == 2:
                    duration_in_seconds = parts[0]*60 + parts[1]
                elif len(parts) == 1:
                    duration_in_seconds = parts[0]

            upload_date = "N/A"
            upload_date_match = re.search(r'<meta property="video:release_date" content="([^"]+)"', html)
            if upload_date_match:
                upload_date = iso_to_ddmmyyyy(upload_date_match.group(1))
            else:
                alt_date = re.search(r'"datePublished":"([^"]+)"', html)
                if alt_date:
                    upload_date = iso_to_ddmmyyyy(alt_date.group(1))

            views = re.search(r'<div class="vp-layer-info_i"><span>([^<]+)</span>', html)
            channel_url = re.search(r'/(group|profile)/([\w\d]+)', html)
            channel_name = re.search(r'name="([^"]+)" id="\d+"', html)
            subscribers = re.search(r'subscriberscount="(\d+)"', html)

            results.append({
                "title": title.group(1) if title else "N/A",
                "duration": seconds_to_hhmmss(duration_in_seconds) if duration_in_seconds is not None else "N/A",
                "views": views.group(1) if views else "N/A",
                "channel_url": f"https://ok.ru/{channel_url.group(1)}/{channel_url.group(2)}" if channel_url else "N/A",
                "channel_name": channel_name.group(1) if channel_name else "N/A",
                "subscribers": int(subscribers.group(1)) if subscribers else "N/A",
                "upload_date": upload_date
            })
        except Exception as e:
            results.append({"error": f"Error processing {url}: {str(e)}"})
    return results
