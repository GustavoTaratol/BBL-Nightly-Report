FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

WORKDIR /app
COPY . /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    BBL_DATA_DIR=/data \
    BBL_OUTPUT_DIR=/data/reports \
    BBL_ROSTERS_FILE=/data/rosters/current.txt

CMD ["python", "bbl/automation.py"]
