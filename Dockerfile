# Use slim Python
FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Railway sets PORT; default 8080
ENV PORT=8080

CMD ["python", "bot.py"]
