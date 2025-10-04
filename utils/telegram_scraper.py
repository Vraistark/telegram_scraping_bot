import os
import re
import asyncio
from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChannelPrivateError

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")

# Use a dedicated session file for this scraper
SESSION_NAME = 'telegram_scraper_session'
client = TelegramClient(SESSION_NAME, api_id, api_hash)

async def scrape_telegram_channel(urls):
    results = []
    # Ensure client is connected and authorized
    await client.start()
    for url in urls:
        try:
            # Match private and public telegram message URLs
            m_private = re.match(r'https?://t\.me/c/(\d+)/(\d+)', url)
            m_public = re.match(r'https?://t\.me/([\w_]+)/(\d+)', url)

            if m_private:
                channel_id = int(m_private.group(1))
                message_id = int(m_private.group(2))
                channel_identifier = int(f"-100{channel_id}")  # channel ID for Telethon
            elif m_public:
                channel_identifier = m_public.group(1)
                message_id = int(m_public.group(2))
            else:
                # Skip invalid URLs
                continue

            channel = await client.get_entity(channel_identifier)
            message = await client.get_messages(channel, ids=message_id)

            results.append({
                "channel": getattr(channel, 'title', 'Unknown'),
                "post_url": url,
                "message_id": message.id,
                "text": message.message or '',
                "views": getattr(message, 'views', 0),
                "date": message.date.isoformat() if message.date else ''
            })

        except FloodWaitError as e:
            # Wait for the time Telegram requests before trying again
            print(f"FloodWaitError: sleeping {e.seconds} seconds...")
            await asyncio.sleep(e.seconds)
        except ChannelPrivateError:
            results.append({"error": f"Channel is private or inaccessible: {url}"})
        except Exception as e:
            results.append({"error": f"Error processing {url}: {str(e)}"})

    return results

# Example usage:
# if __name__ == "__main__":
#     urls = [
#         "https://t.me/somepublicchannel/123",
#         "https://t.me/c/123456789/10"
#     ]
#     scraped_data = asyncio.run(scrape_telegram_channel(urls))
#     print(scraped_data)
