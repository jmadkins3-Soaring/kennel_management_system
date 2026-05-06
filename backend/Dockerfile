FROM python:3.12-slim

# System dependencies: WeasyPrint rendering libs + cron for backup job
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libffi-dev libcairo2 cron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY scripts/backup.py ./scripts/backup.py

RUN mkdir -p /data /tmp/receipts /tmp/reports /app/scripts \
    && chmod +x /app/entrypoint.sh

# Backup cron: runs at 1:15 AM inside the container
RUN echo "15 1 * * * python /app/scripts/backup.py >> /proc/1/fd/1 2>&1" | crontab -

ENV DB_PATH=/data/kennel.db
ENV CONFIG_DIR=/config
ENV SECRET_KEY=CHANGE_ME_IN_PRODUCTION

EXPOSE 9101

CMD ["/app/entrypoint.sh"]
