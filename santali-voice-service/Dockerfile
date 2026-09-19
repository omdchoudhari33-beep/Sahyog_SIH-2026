# torch 2.5.1/cuda12.4 genuinely ran on this GPU (an RTX 50-series/
# Blackwell laptop card) but every real op failed at runtime with
# "CUDA error: no kernel image is available for execution on the device" -
# confirmed live, not a config typo - that PyTorch build has no compiled
# kernels for Blackwell's sm_120. 2.14.0/cuda12.8 does (Blackwell support
# landed in PyTorch's cu128 builds); the host driver (CUDA 13.3 UMD) is
# newer than the container's 12.8 toolkit, which is fine - drivers are
# backward compatible with older CUDA toolkits.
FROM pytorch/pytorch:2.9.1-cuda12.8-cudnn9-runtime

WORKDIR /app

# git is needed to pip-install parler-tts straight from its GitHub repo
# (no PyPI release exists yet) - not present in this base image by default.
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8100

# Model weights are downloaded into the HF cache on first request, not at
# build time - the container has no Bhashini-style credentials to fail on,
# but the first /asr, /translate, or /tts call to a fresh volume will be
# slow (multi-GB download) even though the process itself starts instantly.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8100"]
