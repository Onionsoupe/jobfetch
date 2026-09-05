import os
import time
import requests
from dotenv import load_dotenv
from config import get_scrapers

# Load variables from .env file into os.environ
load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()


def send_telegram_notification(job: dict) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing in .env")
        return False

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
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"✅ Telegram notification sent for: {job['title']}")
            return True
        else:
            print(f"❌ Telegram API Error ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"❌ Telegram Request Failed: {e}")
        return False


def run_loop():
    print("🚀 Job Scraper Service Started...")
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ WARNING: Telegram credentials are not loaded correctly!")
    else:
        print("✅ Telegram credentials loaded successfully.")

    scrapers = get_scrapers()

    while True:
        total_new_jobs = 0
        
        for scraper in scrapers:
            source_label = getattr(scraper, "source_name", scraper.__class__.__name__)
            try:
                # 1. Fetch new jobs from this specific scraper
                found_jobs = scraper.fetch_jobs()
                
                # 2. Process & alert immediately per job
                for job in found_jobs:
                    total_new_jobs += 1
                    print(f"📌 [{job['source']}] {job['title']}")
                    print(f"🔗 {job['link']}")
                    print(f"📍 {job['summary']}")
                    
                    # Send alert right away
                    send_telegram_notification(job)
                    print()  # Spacer line in log
                    
            except Exception as e:
                print(f"Error running {source_label}: {e}")

        if total_new_jobs == 0:
            print("No new jobs found across any sources this cycle.")

        time.sleep(3600)


if __name__ == "__main__":
    run_loop()