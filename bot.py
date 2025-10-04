from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ConversationHandler, ContextTypes
)
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
import os
import re
import io
import csv
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")

PLATFORMS_PUBLIC = ['YouTube', 'TelegramPublic', 'Dailymotion', 'Okru']
PLATFORM_PRIVATE = 'TelegramPrivate'

PLATFORM_PATTERNS = {
    'YouTube': re.compile(r'(https?://)?(www\.)?(youtube\.com/(watch\?v=|shorts/|live/)|youtu\.be/[\w\-]+)'),
    'TelegramPublic': re.compile(r'(https?://)?t\.me/[\w_]+/\d+'),
    'TelegramPrivate': re.compile(r'(https?://)?t\.me/c/\d+/\d+'),
    'Dailymotion': re.compile(r'(https?://)?(www\.)?dailymotion\.com/video/[\w\d]+'),
    'Okru': re.compile(r'(https?://)?(www\.)?ok\.ru/video/\d+')
}

# Conversation states for private login
ASK_PHONE, ASK_CODE, ASK_2FA, WAITING_URLS_PRIVATE = range(4)

# Store Telethon clients per user_id
user_clients = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(p, callback_data=p)] for p in PLATFORMS_PUBLIC + [PLATFORM_PRIVATE]]
    await update.message.reply_text(
        "Choose platform to scrape:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data.clear()

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    platform = query.data
    await query.answer()
    context.user_data['platform'] = platform

    if platform == PLATFORM_PRIVATE:
        await query.edit_message_text("Please send your phone number with country code (e.g., +1234567890) to login:")
        return ASK_PHONE
    else:
        await query.edit_message_text(f"Send me the list of URLs (one per line) for {platform} scraping.")
        context.user_data['platform'] = platform
        return WAITING_URLS_PRIVATE  # Reuse to receive urls for public

# --- LOGIN FOR PRIVATE CHANNELS ---

async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    context.user_data['phone'] = phone
    user_id = update.message.from_user.id

    session_name = f"sessions/session_{user_id}"  # ensure sessions directory exists
    client = TelegramClient(session_name, API_ID, API_HASH)
    await client.connect()

    try:
        await client.send_code_request(phone)
    except Exception as e:
        await update.message.reply_text(f"Failed to send code: {e}. Please enter valid phone number.")
        return ASK_PHONE

    user_clients[user_id] = client
    await update.message.reply_text("Code sent! Please enter the code:")
    return ASK_CODE

async def ask_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    user_id = update.message.from_user.id
    phone = context.user_data.get('phone')
    client = user_clients.get(user_id)

    if not client:
        await update.message.reply_text("Session lost. Please /start again.")
        return ConversationHandler.END

    try:
        await client.sign_in(phone, code)
    except SessionPasswordNeededError:
        await update.message.reply_text("Two-step verification enabled. Please enter password:")
        return ASK_2FA
    except Exception as e:
        await update.message.reply_text(f"Sign in failed: {e}. Please /start again.")
        return ConversationHandler.END

    await update.message.reply_text("Logged in! Send Telegram private channel URLs (one per line) to scrape.")
    return WAITING_URLS_PRIVATE

async def ask_2fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    user_id = update.message.from_user.id
    client = user_clients.get(user_id)

    try:
        await client.sign_in(password=password)
    except Exception as e:
        await update.message.reply_text(f"2FA failed: {e}. Please /start again.")
        return ConversationHandler.END

    await update.message.reply_text("Logged in! Send Telegram private channel URLs (one per line) to scrape.")
    return WAITING_URLS_PRIVATE

# --- URL HANDLER FOR BOTH PUBLIC AND PRIVATE ---

async def url_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    platform = context.user_data.get('platform')
    user_id = update.message.from_user.id
    urls = update.message.text.strip().split('\n')

    if platform in PLATFORMS_PUBLIC:
        # Validate URLs
        pattern = PLATFORM_PATTERNS[platform]
        valid_urls = [u for u in urls if pattern.match(u)]
        invalid_urls = [u for u in urls if not pattern.match(u)]
        if invalid_urls:
            await update.message.reply_text("Invalid URLs:\n" + "\n".join(invalid_urls))
        if not valid_urls:
            await update.message.reply_text("No valid URLs provided.")
            return

        await update.message.reply_text(f"Scraping {len(valid_urls)} URLs for {platform}...")

        # Call your existing public scraper functions here (mocked)
        # e.g. results = fetch_youtube_data(valid_urls) etc.
        await update.message.reply_text("Public scraping not implemented here.")

    elif platform == PLATFORM_PRIVATE:
        client = user_clients.get(user_id)
        if not client or not await client.is_user_authorized():
            await update.message.reply_text("You must login first to scrape private channels. Use /start")
            return ConversationHandler.END

        pattern = PLATFORM_PATTERNS[platform]
        valid_urls = [u for u in urls if pattern.match(u)]
        invalid_urls = [u for u in urls if not pattern.match(u)]
        if invalid_urls:
            await update.message.reply_text("Invalid private Telegram URLs:\n" + "\n".join(invalid_urls))
        if not valid_urls:
            await update.message.reply_text("No valid URLs to process.")
            return

        await update.message.reply_text(f"Fetching data for {len(valid_urls)} private Telegram URLs...")

        results = []
        for url in valid_urls:
            try:
                m_private = re.match(r'https?://t\.me/c/(\d+)/(\d+)', url)
                if not m_private:
                    results.append({"error": f"Invalid private channel URL: {url}"})
                    continue
                channel_id = int(m_private.group(1))
                message_id = int(m_private.group(2))
                entity = await client.get_entity(int(f"-100{channel_id}"))
                message = await client.get_messages(entity, ids=message_id)

                results.append({
                    "channel": getattr(entity, "title", "Unknown"),
                    "post_url": url,
                    "message_id": message.id,
                    "text": message.message or "",
                    "views": getattr(message, "views", 0),
                    "date": message.date.isoformat() if message.date else ""
                })
            except Exception as e:
                results.append({"error": f"Failed scraping {url}: {e}"})

        if not results:
            await update.message.reply_text("No data scraped.")
            return

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
        output.seek(0)
        await update.message.reply_document(document=output, filename="private_telegram_data.csv")
    else:
        await update.message.reply_text("Unknown platform selected, please use /start")

# Define conversation for private login flow only
conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(button_handler)],
    states={
        ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone)],
        ASK_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_code)],
        ASK_2FA: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_2fa)],
        WAITING_URLS_PRIVATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, url_handler)]
    },
    fallbacks=[],
    allow_reentry=True
)

def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        logger.error("Missing TELEGRAM_BOT_TOKEN environment variable.")
        return

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    # For public platforms, URLs come after platform selection (handled in conv_handler WAITING_URLS_PRIVATE state)
    # No separate handler for public URLs needed outside conversation states

    logger.info("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
