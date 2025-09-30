import os
from telethon.sync import TelegramClient
from telethon.errors import FloodWaitError, ChannelPrivateError
from telethon.tl.types import PeerChannel, DocumentAttributeAudio, MessageMediaDocument
import time
import csv
import re

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")


client = TelegramClient('session_name', api_id, api_hash)

async def scrape_telegram_channel(urls):
    results = []

    await client.start()
    for url in urls:
        try:
            # Extract channel info from URL
            channel_identifier = None
            m_private = re.match(r'https://t\.me/c/(\d+)/(\d+)', url)
            m_public = re.match(r'https://t\.me/([\w_]+)/(\d+)', url)

            if m_private:
                channel_id = int(m_private.group(1))
                message_id = int(m_private.group(2))
                channel_identifier = f'-100{channel_id}'
            elif m_public:
                channel_identifier = m_public.group(1)
                message_id = int(m_public.group(2))
            else:
                continue

            channel = await client.get_entity(channel_identifier)
            message = await client.get_messages(channel, ids=message_id)

            results.append({
                "channel": getattr(channel, 'title', 'Unknown'),
                "post_url": url,
                "message_id": message.id,
                "text": message.message or '',
                "views": getattr(message, 'views', 0),
                "date": message.date.isoformat()
            })

        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
        except ChannelPrivateError:
            results.append({"error": f"Channel is private or inaccessible: {url}"})
        except Exception as e:
            results.append({"error": f"Error processing {url}: {str(e)}"})

    return results
