import os
import time
import requests
from dotenv import load_dotenv
from config import get_scrapers

# Load variables from .env file into os.environ
load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()


def send_telegram_message(text: str, disable_notification: bool = False) -> bool:
    """Generic helper to send any text message to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing in .env")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "disable_notification": disable_notification  # True = Silent message (no sound/vibration)
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Telegram Request Failed: {e}")
        return False


def send_telegram_notification(job: dict) -> bool:
    """Formats and sends an individual job alert."""
    text = (
        f"🤖 <b>New Job Posting Alert!</b>\n\n"
        f"<b>Title:</b> {job['title']}\n"
        f"<b>Source:</b> {job['source']}\n"
        f"<b>Details:</b> {job['summary']}\n\n"
        f"🔗 <a href='{job['link']}'>Apply Here</a>"
    )
    success = send_telegram_message(text)
    if success:
        print(f"✅ Telegram notification sent for: {job['title']}")
    return success


def run_loop():
    print("🚀 Job Scraper Service Started...")
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ WARNING: Telegram credentials are not loaded correctly!")
    else:
        print("✅ Telegram credentials loaded successfully.")

    scrapers = get_scrapers()

    while True:
        # Print check start locally to Pi logs (silent on Telegram)
        print("\n🔍 Running hourly check...")
        
        # Optional: Send silent Telegram ping that check started
        send_telegram_message("🔍 Running hourly check...", disable_notification=True)
        total_new_jobs = 0
        
        for scraper in scrapers:
            source_label = getattr(scraper, "source_name", scraper.__class__.__name__)
            try:
                found_jobs = scraper.fetch_jobs()
                
                for job in found_jobs:
                    total_new_jobs += 1
                    print(f"📌 [{job['source']}] {job['title']}")
                    print(f"🔗 {job['link']}")
                    print(f"📍 {job['summary']}")
                    
                    send_telegram_notification(job)
                    print()
                    
            except Exception as e:
                print(f"Error running {source_label}: {e}")

        # Summary output after checking all scrapers
        if total_new_jobs > 0:
            summary_msg = f"📊 <b>Scan Complete:</b> Found and alerted for <b>{total_new_jobs}</b> new job(s)!"
            print(f"✨ {summary_msg}")
            send_telegram_message(summary_msg)
        else:
            no_jobs_msg = "ℹ️ <b>Scan Complete:</b> No new jobs found this cycle."
            print("No new jobs found across any sources this cycle.")
            send_telegram_message(no_jobs_msg, disable_notification=True)

        time.sleep(3600)


if __name__ == "__main__":
    run_loop()