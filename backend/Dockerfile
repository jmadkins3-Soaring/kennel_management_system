FROM python:3.12-slim

# WeasyPrint system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libffi-dev libcairo2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data /tmp/receipts /tmp/reports

# Backup cron: runs at 1:15 AM inside the container
RUN echo "15 1 * * * python /app/scripts/backup.py >> /proc/1/fd/1 2>&1" | crontab -

ENV DB_PATH=/data/kennel.db
ENV CONFIG_DIR=/config
ENV SECRET_KEY=CHANGE_ME_IN_PRODUCTION

EXPOSE 9101

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9101"]
