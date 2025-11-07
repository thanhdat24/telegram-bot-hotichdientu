import os
import asyncio
import logging
from html import escape

import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---------------- Logging ----------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

HIGHLIGHT_EMOJI = "🟢"
ZERO_EMOJI = "⚪️"

load_dotenv()

# ---------------- ENV & sanitize ----------------
def _clean(s: str) -> str:
    if not s:
        return ""
    s = "".join(ch for ch in s if 32 <= ord(ch) <= 126)
    return s.strip()

BOT_TOKEN = _clean(os.getenv("BOT_TOKEN"))
BEARER_TOKEN = _clean(os.getenv("BEARER_TOKEN"))
PORT = int(os.getenv("PORT", "8080"))
WEBHOOK_BASE_URL = _clean(os.getenv("WEBHOOK_BASE_URL")).rstrip("/")

if WEBHOOK_BASE_URL.lower().startswith(("http://localhost", "http://127.0.0.1")):
    logger.warning("WEBHOOK_BASE_URL trỏ localhost, sẽ bỏ qua để tránh lỗi. Hãy đặt HTTPS public: https://<app>.up.railway.app")
    WEBHOOK_BASE_URL = ""

if WEBHOOK_BASE_URL and not WEBHOOK_BASE_URL.lower().startswith("https://"):
    logger.warning("WEBHOOK_BASE_URL nên là HTTPS public (vd: https://<app>.up.railway.app). Giá trị hiện tại: %s", WEBHOOK_BASE_URL)

if not BOT_TOKEN:
    raise RuntimeError("Missing BOT_TOKEN environment variable")

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

async def fetch_total_async(client: httpx.AsyncClient, url: str, body: dict) -> int:
    try:
        r = await client.post(url, json=body, timeout=httpx.Timeout(8.0))
        r.raise_for_status()
        j = r.json()
        return int(j.get("result", {}).get("totalElements", 0))
    except Exception as e:
        logger.warning("fetch_total error for %s: %s", url, e)
        return 0

def format_lines(totals: dict[str, int]) -> str:
    lines = ['<b>📊 Thống kê hồ sơ từng lĩnh vực:</b>']
    for name, total in totals.items():
        if total > 0:
            lines.append(f"- {HIGHLIGHT_EMOJI} <b>{escape(name)}: {total} hồ sơ</b>")
        else:
            lines.append(f"- {ZERO_EMOJI} {escape(name)}: {total} hồ sơ")
    return "\n".join(lines)

# ---------------- Handlers ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Xin chào! Gõ /thongke để xem thống kê.")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong")

async def thongke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Trả lời sớm để Telegram thấy bot phản hồi ngay
    msg = await update.message.reply_text("⏳ Đang lấy số liệu, vui lòng đợi...")
    async with httpx.AsyncClient(headers=HEADERS) as client:
        tasks = []
        labels = []
        for label, cfg in ENDPOINTS.items():
            labels.append(label)
            tasks.append(fetch_total_async(client, cfg["url"], cfg["body"]))
        results = await asyncio.gather(*tasks)
    totals = {label: total for label, total in zip(labels, results)}
    html = format_lines(totals)
    try:
        await msg.edit_text(html, parse_mode="HTML", disable_web_page_preview=True)
    except Exception:
        await update.message.reply_html(html)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("thongke", thongke))

    webhook_path = BOT_TOKEN  # path khó đoán
    webhook_url = f"{WEBHOOK_BASE_URL}/{webhook_path}" if WEBHOOK_BASE_URL else None

    if webhook_url:
        logger.info("Setting webhook URL to %s", webhook_url)
    else:
        logger.warning("WEBHOOK_BASE_URL chưa có/không hợp lệ. Bot vẫn mở cổng chờ, nhưng Telegram sẽ không gửi update tới. Hãy set HTTPS public rồi redeploy.")

    logger.info("Starting webhook on 0.0.0.0:%s, path=/%s", PORT, webhook_path)
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=webhook_path,
        webhook_url=webhook_url,
        drop_pending_updates=True,
    )

if __name__ == "__main__":
    main()
