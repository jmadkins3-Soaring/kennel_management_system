#!/bin/bash
set -e
# Start cron daemon in the background, then exec uvicorn as PID 1.
service cron start
exec uvicorn app.main:app --host 0.0.0.0 --port 9101
