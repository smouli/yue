# Use PyTorch 2.6.0 base image with CUDA 12.4 support (matches YuE requirements exactly)
FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-devel

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Basic utilities
    curl \
    wget \
    unzip \
    git \
    # Audio processing libraries
    ffmpeg \
    libsndfile1-dev \
    # Build tools for Python packages
    build-essential \
    # Google Cloud SDK for gsutil
    gnupg \
    lsb-release \
    # Clean up
    && rm -rf /var/lib/apt/lists/*

# Install Google Cloud SDK (for gsutil)
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key --keyring /usr/share/keyrings/cloud.google.gpg add - && \
    apt-get update && apt-get install -y google-cloud-cli && \
    rm -rf /var/lib/apt/lists/*

# Copy and install minimal Flask server requirements first
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy YuE directory
COPY YuE-exllamav2/ ./YuE-exllamav2/

# Install YuE dependencies (includes PyTorch 2.6.0, ExllamaV2, Flash Attention)
RUN cd YuE-exllamav2 && pip install --no-cache-dir -r requirements.txt

# Copy the Flask application
COPY server.py ./

# Verify final installation
RUN python3 -c "import torch; print('PyTorch:', torch.__version__)"
RUN python3 -c "import exllamav2; print('ExllamaV2 imported successfully')"
RUN python3 -c "import flash_attn; print('Flash Attention imported successfully')"

# Models directory will now contain Python files (soundstream_hubert_new.py, __init__.py)

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start the Flask server directly (models download on-demand)
CMD ["python3", "server.py"] 