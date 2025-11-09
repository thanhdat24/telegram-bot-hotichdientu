import os
import asyncio
import logging
from html import escape

import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, filters
)

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
def _clean(s: str | None) -> str:
    if not s:
        return ""
    s = "".join(ch for ch in s if 32 <= ord(ch) <= 126)
    return s.strip()

BOT_TOKEN = _clean(os.getenv("BOT_TOKEN"))
PORT = int(os.getenv("PORT", "8080"))

WEBHOOK_BASE_URL = _clean(os.getenv("WEBHOOK_BASE_URL")).rstrip("/")
SECRET_PATH = _clean(os.getenv("WEBHOOK_SECRET_PATH")) or f"hook-{(_clean(os.getenv('BOT_TOKEN'))).replace(':','-') or 'tg'}"

# --- token API & quyền đổi token ---
BEARER_TOKEN = _clean(os.getenv("BEARER_TOKEN"))  # <- ĐỊNH NGHĨA TRƯỚC
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))  # 0 = không giới hạn ai dùng /settoken

# dùng biến toàn cục để cập nhật token "nóng"
CURRENT_BEARER_TOKEN = BEARER_TOKEN

def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {CURRENT_BEARER_TOKEN}" if CURRENT_BEARER_TOKEN else "",
        "Content-Type": "application/json",
    }

if not BOT_TOKEN:
    raise RuntimeError("Missing BOT_TOKEN environment variable")

# Telegram bắt buộc HTTPS public
if WEBHOOK_BASE_URL.lower().startswith(("http://localhost", "http://127.0.0.1")):
    logger.warning("WEBHOOK_BASE_URL đang trỏ localhost, sẽ bỏ qua setWebhook.")
    WEBHOOK_BASE_URL = ""
if WEBHOOK_BASE_URL and not WEBHOOK_BASE_URL.lower().startswith("https://"):
    logger.warning("WEBHOOK_BASE_URL nên là HTTPS public. Hiện tại: %s", WEBHOOK_BASE_URL)

# ====== ENDPOINTS ======
ENDPOINTS = {
    "Đăng ký khai sinh": {
        "url": "https://hotichdientu.moj.gov.vn/v1/birth/search-approve-publish?page=0&size=10&sort=id,DESC",
        "body": {"searchKey":"","registrationDate":[],"signStatus":None,"numberNo":"","bookNoId":None,
                 "rpGender":None,"rpBirthDate":"","spFullName":"","isApprove":True}
    },
    "Đăng ký khai tử": {
        "url": "https://hotichdientu.moj.gov.vn/v1/death/search-approve-publish?page=0&size=10&sort=id,DESC",
        "body": {"searchKey":"","registrationDate":[],"bookNoId":None,"isApprove":True}
    },
    "Đăng ký kết hôn": {
        "url": "https://hotichdientu.moj.gov.vn/v1/marriage/search-approve-publish?page=0&size=10&sort=id,DESC",
        "body": {"searchKey":"","registrationDate":[],"bookNoId":None,"isApprove":True}
    },
    "XNTT Hôn nhân": {
        "url": "https://hotichdientu.moj.gov.vn/v1/marital/search-approve-publish?page=0&size=10&sort=id,DESC",
        "body": {"searchKey":"","registrationDate":[],"signStatus":None,"numberNo":"","bookNoId":None,
                 "rpGender":None,"rpBirthDate":"","spFullName":"","lastUpdated":1762446099275,"isApprove":True}
    },
    "Đăng ký giám hộ": {
        "url": "https://hotichdientu.moj.gov.vn/v1/guardianship/search-approve-publish?page=0&size=10&sort=id,DESC",
        "body": {"searchKey":"","registrationDate":[],"signStatus":None,"guardianBirthDate":None,
                 "dependentBirthDate":None,"spFullName":"","type":None,"isApprove":True}
    },
    "Đăng ký giám sát việc giám hộ": {
        "url": "https://hotichdientu.moj.gov.vn/v1/guardianship-supervision/search-approve-publish?page=0&size=10&sort=id,DESC",
        "body": {"searchKey":"","registrationDate":[],"signStatus":None,"supervisorBirthDate":"",
                 "numberNo":"","type":None,"isApprove":True}
    },
    "Đăng ký nhận cha, mẹ, con": {
        "url": "https://hotichdientu.moj.gov.vn/v1/parent-child/search-approve-publish?page=0&size=10&sort=id,DESC",
        "body": {"searchKey":"","registrationDate":[],"signStatus":None,"bookNoId":None,"childBirthDate":"",
                 "parentBirthDate":"","spFullName":"","lastUpdated":1762446648483,"isApprove":True}
    },
    "Cấp bản sao trích lục": {
        "url": "https://hotichdientu.moj.gov.vn/v1/guardianship/search-approve-publish?page=0&size=10&sort=id,DESC",
        "body": {"searchKey":"","registrationDate":[],"signStatus":None,"guardianBirthDate":None,
                 "dependentBirthDate":None,"spFullName":"","type":None,"isApprove":True}
    }
}

# ===== Helpers =====
async def fetch_total_async(client: httpx.AsyncClient, url: str, body: dict) -> tuple[int, bool]:
    """Trả (total, unauthorized). unauthorized=True nếu nhận 401."""
    try:
        r = await client.post(url, json=body, headers=get_headers(), timeout=httpx.Timeout(8.0))
        if r.status_code == 401:
            logger.warning("401 Unauthorized for %s", url)
            return 0, True
        r.raise_for_status()
        j = r.json()
        return int(j.get("result", {}).get("totalElements", 0)), False
    except Exception as e:
        logger.warning("fetch_total error for %s: %s", url, e)
        return 0, False

def format_lines(totals: dict[str, int]) -> str:
    lines = ['<b>📊 Thống kê hồ sơ từng lĩnh vực:</b>']
    for name, total in totals.items():
        if total > 0:
            lines.append(f"- {HIGHLIGHT_EMOJI} <b>{escape(name)}: {total} hồ sơ</b>")
        else:
            lines.append(f"- {ZERO_EMOJI} {escape(name)}: {total} hồ sơ")
    return "\n".join(lines)

# ===== Handlers =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Xin chào! Gõ /thongke để xem thống kê.")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong")

async def thongke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Đang lấy số liệu, vui lòng đợi...")
    unauthorized_any = False
    async with httpx.AsyncClient() as client:
        labels, tasks = [], []
        for label, cfg in ENDPOINTS.items():
            labels.append(label)
            tasks.append(fetch_total_async(client, cfg["url"], cfg["body"]))
        results = await asyncio.gather(*tasks)

    totals: dict[str, int] = {}
    for (label, (total, unauthorized)) in zip(labels, results):
        totals[label] = total
        if unauthorized:
            unauthorized_any = True

    html = format_lines(totals)
    if unauthorized_any:
        html = (
            "❗️ <b>BEARER_TOKEN có thể đã hết hạn hoặc không hợp lệ (401)</b>\n"
            "→ Cập nhật bằng lệnh <code>/settoken &lt;token_mới&gt;</code>\n\n"
            + html
        )

    try:
        await msg.edit_text(html, parse_mode="HTML", disable_web_page_preview=True)
    except Exception:
        await update.message.reply_html(html)

async def settoken(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CURRENT_BEARER_TOKEN
    user_id = update.effective_user.id if update.effective_user else 0

    if ADMIN_USER_ID and user_id != ADMIN_USER_ID:
        await update.message.reply_text("⛔️ Bạn không có quyền dùng lệnh này.")
        return

    if not context.args:
        await update.message.reply_text("Cách dùng: /settoken")
        return

    new_token = " ".join(context.args).strip()
    new_token = "".join(ch for ch in new_token if 32 <= ord(ch) <= 126)

    if not new_token:
        await update.message.reply_text("Token trống hoặc không hợp lệ.")
        return

    CURRENT_BEARER_TOKEN = new_token
    await update.message.reply_text("✅ Đã cập nhật BEARER_TOKEN. Thử lại /thongke.")
    logger.info("BEARER_TOKEN updated at runtime by user_id=%s", user_id)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    masked = (CURRENT_BEARER_TOKEN[:4] + "..." + CURRENT_BEARER_TOKEN[-4:]) if CURRENT_BEARER_TOKEN and len(CURRENT_BEARER_TOKEN) > 8 else (CURRENT_BEARER_TOKEN or "(empty)")
    await update.message.reply_text(
        "🔎 Status:\n"
        f"- WEBHOOK_BASE_URL: {WEBHOOK_BASE_URL or '(empty)'}\n"
        f"- SECRET_PATH: {SECRET_PATH}\n"
        f"- BEARER_TOKEN: {masked}\n"
        f"- ADMIN_USER_ID: {ADMIN_USER_ID or '(disabled)'}"
    )

async def log_any(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info("Got update: %s", update.to_dict())
    except Exception:
        pass

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Mình chưa hiểu lệnh này. Thử /ping hoặc /thongke nhé.")

# ===== Main =====
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("thongke", thongke))
    app.add_handler(CommandHandler("settoken", settoken))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    app.add_handler(MessageHandler(filters.ALL, log_any))

    webhook_path = SECRET_PATH
    webhook_url = f"{WEBHOOK_BASE_URL}/{webhook_path}" if WEBHOOK_BASE_URL else None

    logger.info("Webhook path: /%s", webhook_path)
    if webhook_url:
        logger.info("Setting webhook URL to %s", webhook_url)
    else:
        logger.warning("WEBHOOK_BASE_URL chưa có/không hợp lệ. Sẽ không setWebhook.")

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=webhook_path,   # dùng SECRET_PATH (không có dấu ':')
        webhook_url=webhook_url,
        drop_pending_updates=True,
    )

if __name__ == "__main__":
    main()
