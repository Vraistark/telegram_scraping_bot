import re
import csv
import io
import logging
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

# Validate URL by platform
PLATFORM_PATTERNS = {
    'YouTube': re.compile(r'(youtube\.com/(watch\?v=|shorts/|live/)|youtu\.be/)'),
    'TelegramPublic': re.compile(r't\.me/[\w_]+/\d+'),
    'TelegramPrivate': re.compile(r't\.me/c/\d+/\d+'),
    'Dailymotion': re.compile(r'dailymotion\.com/video/[\w\d]+'),
    'Okru': re.compile(r'ok\.ru/video/\d+')
}

PLATFORMS = ['YouTube', 'TelegramPublic', 'TelegramPrivate', 'Dailymotion', 'Okru']

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(p, callback_data=p)] for p in PLATFORMS]
    await update.message.reply_text(
        "Choose the platform to scrape data from:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    platform = query.data
    context.user_data['platform'] = platform
    await query.edit_message_text(f"Send me the list of URLs (one per line) for {platform} scraping.")

async def url_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    platform = context.user_data.get('platform')
    if not platform:
        await update.message.reply_text("Please select a platform first using /start.")
        return

    urls = update.message.text.strip().split('\n')
    valid_urls = []
    invalid_urls = []

    pattern = PLATFORM_PATTERNS.get(platform)
    if not pattern:
        await update.message.reply_text("Invalid platform selected.")
        return

    for url in urls:
        if pattern.search(url):
            valid_urls.append(url.strip())
        else:
            invalid_urls.append(url.strip())

    if invalid_urls:
        await update.message.reply_text(
            f"Some URLs are invalid for {platform}:\n" + "\n".join(invalid_urls)
        )

    if not valid_urls:
        await update.message.reply_text("No valid URLs to process.")
        return

    await update.message.reply_text(f"Processing {len(valid_urls)} URLs for {platform}...")

    results = []
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

    # Create CSV in memory
    output = io.StringIO()
    if results:
        headers = results[0].keys()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerows(results)
    else:
        await update.message.reply_text("No data was scraped from the provided URLs.")
        return

    output.seek(0)
    await update.message.reply_document(document=output, filename=f"{platform}_data.csv")

def main():
    import os
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, url_handler))

    print("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
