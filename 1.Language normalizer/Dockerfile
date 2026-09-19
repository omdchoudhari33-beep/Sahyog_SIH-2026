FROM python:3.11-slim

# ffmpeg is required by app/media/pipeline.py (audio normalization before
# ASR) - looked up via PATH (shutil.which("ffmpeg")), not vendored.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
