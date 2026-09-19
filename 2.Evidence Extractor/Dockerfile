FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8002

# Module is "main:app" (flat layout, not an "app" package - unlike every
# other service here).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
