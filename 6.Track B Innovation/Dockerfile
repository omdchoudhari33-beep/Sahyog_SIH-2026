FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
# sentence-transformers pulls in torch - this image is noticeably larger
# than the other services (expected, not a bug). Installing the CPU-only
# torch build FIRST (from PyTorch's own CPU wheel index) makes pip see
# torch's requirement as already satisfied when it hits
# sentence-transformers below, instead of pulling the default
# CUDA-enabled build - several GB of NVIDIA libraries this container has
# no GPU to use anyway.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8006

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8006"]
