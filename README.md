# Telegram Bot (Webhook) on Railway.app — 0đ

Triển khai bot Telegram Python (python-telegram-bot v20) chạy webhook trên Railway.

## 📦 Cấu trúc
```
.
├─ bot.py
├─ requirements.txt
├─ Dockerfile
└─ .env.example
```

## 🚀 Triển khai trên Railway (miễn phí)
1. **Fork hoặc push** repo này lên GitHub của bạn.
2. Vào **https://railway.app** → **New Project** → **Deploy from GitHub** → chọn repo.
3. Ở tab **Variables**, thêm các biến môi trường:
   - `BOT_TOKEN` — token từ BotFather.
   - `BEARER_TOKEN` — token API nội bộ của bạn (nếu không có có thể để trống, nhưng một số endpoint sẽ 401).
   - *(Tạm thời bỏ trống)* `WEBHOOK_BASE_URL` — sẽ thêm sau khi có domain Railway.
4. Deploy lần 1 xong, lấy **Public Domain** của service (dạng `https://<tên>.up.railway.app`).
5. Vào **Variables** thêm/điền `WEBHOOK_BASE_URL=https://<tên>.up.railway.app`, sau đó **Redeploy**.
6. Mở Telegram chat với bot và gõ `/start`, `/ping` hoặc `/thongke`.

> Bot mở cổng theo biến `PORT` (Railway tự đặt). `run_webhook` sẽ đăng ký webhook tới `https://WEBHOOK_BASE_URL/<BOT_TOKEN>`.

## 🛠️ Chạy local (tuỳ chọn)
```
cp .env.example .env
# sửa BOT_TOKEN, BEARER_TOKEN theo của bạn
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```
Mở một tunnel public (vd ngrok) và đặt `WEBHOOK_BASE_URL` thành `https://<subdomain>.ngrok.io` để Telegram gọi về máy bạn.

## ❗ Lưu ý
- Nếu bạn đổi token bot, hãy **redeploy** để set webhook lại.
- Free tier Railway có credit hàng tháng; bot nhẹ thường đủ 24/7.
- Log xem ở tab **Logs** của service.
- Lỗi 401/403 khi gọi API nội bộ → kiểm tra `BEARER_TOKEN`.

Chúc bạn deploy vui vẻ!
