import time
import os
import requests
from config import get_scrapers

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def send_telegram_notification(job: dict):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    text = (
        f"🤖 <b>New Job Posting Alert!</b>\n\n"
        f"<b>Title:</b> {job['title']}\n"
        f"<b>Source:</b> {job['source']}\n"
        f"<b>Details:</b> {job['summary']}\n\n"
        f"🔗 <a href='{job['link']}'>Apply Here</a>"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")


def run_loop():
    scrapers = get_scrapers()
    print("🚀 Job Scraper Service Started...")
    
    while True:
        all_new_jobs = []
        
        for scraper in scrapers:
            try:
                found_jobs = scraper.fetch_jobs()
                all_new_jobs.extend(found_jobs)
            except Exception as e:
                print(f"Error running {scraper.source_name}: {e}")

        if all_new_jobs:
            print(f"\n✨ Found {len(all_new_jobs)} new job(s) across all sources:")
            for job in all_new_jobs:
                print(f"📌 [{job['source']}] {job['title']}")
                print(f"🔗 {job['link']}")
                print(f"📍 {job['summary']}\n")
                send_telegram_notification(job)
        else:
            print("No new jobs found across any sources this cycle.")

        time.sleep(3600)


if __name__ == "__main__":
    run_loop()