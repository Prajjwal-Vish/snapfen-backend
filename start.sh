#!/usr/bin/env bash

# 1. Start the Celery worker in the background (notice the & at the end)
# NOTE: We use --concurrency=1 because Render's free tier only has 512MB of RAM. 
# Loading the ML model multiple times will cause an Out of Memory (OOM) crash.
celery -A tasks.celery_app worker --loglevel=info --pool=solo &

# 2. Start the Flask web server in the foreground
gunicorn app:app --bind 0.0.0.0:$PORT