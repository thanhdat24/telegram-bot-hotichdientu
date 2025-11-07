# Telegram Bot (Webhook) — Railway (Patched)

## Triển khai
1. Push repo lên GitHub.
2. Railway → New Project → Deploy from GitHub.
3. Variables:
   - `BOT_TOKEN` (bắt buộc)
   - `BEARER_TOKEN` (nếu API cần)
   - *(Đợi có domain rồi thêm)* `WEBHOOK_BASE_URL=https://<app>.up.railway.app`
4. Deploy lần 1 xong → lấy domain public → thêm `WEBHOOK_BASE_URL` → Redeploy.
5. Test `/ping`, `/thongke`.

### Ghi chú
- Code đã **làm sạch** env để tránh lỗi `Invalid non-printable ASCII character in URL`.
- Nếu vô tình đặt `WEBHOOK_BASE_URL=http://localhost:...`, code sẽ **bỏ qua** setWebhook và cảnh báo, tránh crash.
- Telegram yêu cầu URL **HTTPS public**.
