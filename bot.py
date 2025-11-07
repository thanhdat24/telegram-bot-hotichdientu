import os
import asyncio
import logging
from html import escape

import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---------- Logging ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

HIGHLIGHT_EMOJI = "🟢"  # mục có hồ sơ
ZERO_EMOJI = "⚪️"       # mục 0 hồ sơ

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")
PORT = int(os.getenv("PORT", "8080"))  # Railway cung cấp PORT
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL")  # ví dụ: https://your-service.up.railway.app

if not BOT_TOKEN:
    raise RuntimeError("Missing BOT_TOKEN")
if not BEARER_TOKEN:
    logger.warning("BEARER_TOKEN is empty; APIs có thể trả lỗi 401.")
if not WEBHOOK_BASE_URL:
    logger.warning("WEBHOOK_BASE_URL chưa có; hãy set lại sau khi có domain Railway.")

HEADERS = {
    "Authorization": f"Bearer {BEARER_TOKEN}" if BEARER_TOKEN else "",
    "Content-Type": "application/json",
}

# ====== Cấu hình API & payload cho từng lĩnh vực ======
ENDPOINTS = {
    "Đăng ký khai sinh": {
        "url": "https://hotichdientu.moj.gov.vn/v1/birth/search-approve-publish?page=0&size=10&sort=id,DESC",
        "body": {
            "searchKey": "",
            "registrationDate": [],
            "signStatus": None,
            "numberNo": "",
            "bookNoId": None,
            "rpGender": None,
            "rpBirthDate": "",
            "spFullName": "",
            "isApprove": True
        }
    },
    "Đăng ký khai tử": {
        "url": "https://hotichdientu.moj.gov.vn/v1/death/search-approve-publish?page=0&size=10&sort=id,DESC",
        "body": {
            "searchKey": "",
            "registrationDate": [],
            "bookNoId": None,
            "isApprove": True
        }
    },
    "Đăng ký kết hôn": {
        "url": "https://hotichdientu.moj.gov.vn/v1/marriage/search-approve-publish?page=0&size=10&sort=id,DESC",
        "body": {
            "searchKey": "",
            "registrationDate": [],
            "bookNoId": None,
            "isApprove": True
        }
    },
    "XNTT Hôn nhân": {
        "url": "https://hotichdientu.moj.gov.vn/v1/marital/search-approve-publish?page=0&size=10&sort=id,DESC",
        "body": {
            "searchKey": "",
            "registrationDate": [],
            "signStatus": None,
            "numberNo": "",
            "bookNoId": None,
            "rpGender": None,
            "rpBirthDate": "",
            "spFullName": "",
            "lastUpdated": 1762446099275,
            "isApprove": True
        }
    },
    "Đăng ký giám hộ": {
        "url": "https://hotichdientu.moj.gov.vn/v1/guardianship/search-approve-publish?page=0&size=10&sort=id,DESC",
        "body": {
            "searchKey": "",
            "registrationDate": [],
            "signStatus": None,
            "guardianBirthDate": None,
            "dependentBirthDate": None,
            "spFullName": "",
            "type": None,
            "isApprove": True
        }
    },
    "Đăng ký giám sát việc giám hộ": {
        "url": "https://hotichdientu.moj.gov.vn/v1/guardianship-supervision/search-approve-publish?page=0&size=10&sort=id,DESC",
        "body": {
            "searchKey": "",
            "registrationDate": [],
            "signStatus": None,
            "supervisorBirthDate": "",
            "numberNo": "",
            "type": None,
            "isApprove": True
        }
    },
    "Đăng ký nhận cha, mẹ, con": {
        "url": "https://hotichdientu.moj.gov.vn/v1/parent-child/search-approve-publish?page=0&size=10&sort=id,DESC",
        "body": {
            "searchKey": "",
            "registrationDate": [],
            "signStatus": None,
            "bookNoId": None,
            "childBirthDate": "",
            "parentBirthDate": "",
            "spFullName": "",
            "lastUpdated": 1762446648483,
            "isApprove": True
        }
    },
    "Cấp bản sao trích lục": {
        "url": "https://hotichdientu.moj.gov.vn/v1/guardianship/search-approve-publish?page=0&size=10&sort=id,DESC",
        "body": {
            "searchKey": "",
            "registrationDate": [],
            "signStatus": None,
            "guardianBirthDate": None,
            "dependentBirthDate": None,
            "spFullName": "",
            "type": None,
            "isApprove": True
        }
    }
}

def fetch_total(url: str, body: dict) -> int:
    """POST và lấy result.totalElements; lỗi thì trả 0."""
    try:
        r = requests.post(url, headers=HEADERS, json=body, timeout=15)
        r.raise_for_status()
        j = r.json()
        return int(j.get("result", {}).get("totalElements", 0))
    except Exception as e:
        logger.warning("fetch_total error for %s: %s", url, e)
        return 0

def format_lines(totals: dict[str, int]) -> str:
    """
    Giữ nguyên thứ tự các lĩnh vực.
    Mục có hồ sơ: biểu tượng 🟢 và in đậm.
    Mục không có hồ sơ: biểu tượng ⚪️ và text thường.
    """
    lines = ['<b>📊 Thống kê hồ sơ từng lĩnh vực:</b>']
    for name, total in totals.items():
        if total > 0:
            lines.append(f"- {HIGHLIGHT_EMOJI} <b>{escape(name)}: {total} hồ sơ</b>")
        else:
            lines.append(f"- {ZERO_EMOJI} {escape(name)}: {total} hồ sơ")
    return "\n".join(lines)

async def thongke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    totals = {}
    for label, cfg in ENDPOINTS.items():
        totals[label] = fetch_total(cfg["url"], cfg["body"])
    html = format_lines(totals)
    await update.message.reply_html(html)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Xin chào! Gõ /thongke để xem thống kê.")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong")

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("thongke", thongke))

    # Webhook path dùng BOT_TOKEN để Telegram gọi
    webhook_path = BOT_TOKEN
    webhook_url = f"{WEBHOOK_BASE_URL}/{webhook_path}" if WEBHOOK_BASE_URL else None
    logger.info("Starting webhook on 0.0.0.0:%s, path=/%s", PORT, webhook_path)
    if webhook_url:
        logger.info("Setting webhook URL to %s", webhook_url)

    # Chạy webhook (aiohttp server bên trong)
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=webhook_path,
        webhook_url=webhook_url,
        drop_pending_updates=True,
    )

if __name__ == "__main__":
    main()
