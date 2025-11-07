# Telegram Bot (Webhook) — Railway (Async)

- Dùng `httpx` async + `asyncio.gather` để gọi các API song song (không block event loop).
- Trả lời sớm "⏳ Đang lấy số liệu..." rồi edit lại tin nhắn khi xong.

## Deploy
1. Push repo lên GitHub.
2. Railway → New Project → Deploy from GitHub.
3. Variables:
   - `BOT_TOKEN`
   - `BEARER_TOKEN` (nếu API yêu cầu)
   - *(sau khi có domain)* `WEBHOOK_BASE_URL=https://<app>.up.railway.app`
4. Redeploy.
5. Test `/ping` và `/thongke`.

Gợi ý kiểm tra webhook: `https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo`
