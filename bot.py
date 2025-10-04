import re
import csv
import io
import logging
import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, CallbackQueryHandler
)

from utils.youtube import fetch_youtube_data
from utils.telegram_scraper import scrape_telegram_channel
from utils.dailymotion import fetch_dailymotion_data
from utils.okru import fetch_okru_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PLATFORM_PATTERNS = {
    'YouTube': re.compile(r'(https?://)?(www\.)?(youtube\.com/(watch\?v=|shorts/|live/)|youtu\.be/[\w\-]+)'),
    'TelegramPublic': re.compile(r'(https?://)?t\.me/[\w_]+/\d+'),
    'TelegramPrivate': re.compile(r'(https?://)?t\.me/c/\d+/\d+'),
    'Dailymotion': re.compile(r'(https?://)?(www\.)?dailymotion\.com/video/[\w\d]+'),
    'Okru': re.compile(r'(https?://)?(www\.)?ok\.ru/video/\d+')
}

PLATFORMS = list(PLATFORM_PATTERNS.keys())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(p, callback_data=p)] for p in PLATFORMS]
    await update.message.reply_text(
        "Choose the platform to scrape:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    platform = query.data
    context.user_data['platform'] = platform
    await query.edit_message_text(f"Send the list of URLs (one per line) for {platform} scraping.")

async def url_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    platform = context.user_data.get('platform')
    if not platform:
        await update.message.reply_text("Please start with /start and select a platform first.")
        return

    urls = update.message.text.strip().split('\n')
    valid_urls = []
    invalid_urls = []
    pattern = PLATFORM_PATTERNS.get(platform)

    for url in urls:
        url = url.strip()
        if pattern and pattern.search(url):
            valid_urls.append(url)
        else:
            invalid_urls.append(url)

    if invalid_urls:
        await update.message.reply_text(
            f"The following URLs are invalid for {platform}:\n" + "\n".join(invalid_urls)
        )

    if not valid_urls:
        await update.message.reply_text("No valid URLs to process. Please try again.")
        return

    await update.message.reply_text(f"Processing {len(valid_urls)} URLs for {platform}...")

    results = []
    try:
        if platform == 'YouTube':
            results = fetch_youtube_data(valid_urls)
        elif platform in ('TelegramPublic', 'TelegramPrivate'):
            results = await scrape_telegram_channel(valid_urls)
        elif platform == 'Dailymotion':
            results = fetch_dailymotion_data(valid_urls)
        elif platform == 'Okru':
            results = fetch_okru_data(valid_urls)
        else:
            await update.message.reply_text("Unsupported platform.")
            return
    except Exception as e:
        logger.error(f"Error scraping data for platform {platform}: {e}")
        await update.message.reply_text("An error occurred while scraping the data.")
        return

    if not results:
        await update.message.reply_text("No data was scraped from the provided URLs.")
        return

    output = io.StringIO()
    headers = results[0].keys()
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    writer.writerows(results)
    output.seek(0)

    await update.message.reply_document(document=output, filename=f"{platform}_data.csv")

def main():
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    if not TOKEN:
        logger.error("Missing TELEGRAM_BOT_TOKEN environment variable.")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, url_handler))

    logger.info("Starting bot with polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
