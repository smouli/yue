# Use NVIDIA CUDA base image for GPU support
FROM gcr.io/deeplearning-platform-release/pytorch-gpu.2-1


# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    git \
    wget \
    curl \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set Python3 as default python
RUN ln -s /usr/bin/python3 /usr/bin/python

# Copy requirements first for better Docker layer caching
COPY requirements.txt /app/requirements.txt

# Install all dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application code (excluding model weights for Vertex AI)
# For Vertex AI, use Dockerfile.vertex instead
#COPY . /app/

# Set environment variables
ENV PYTHONPATH=/app/YuE-exllamav2/src:/app/Server:$PYTHONPATH
ENV FLASK_APP=/app/Server/server.py
ENV FLASK_ENV=production

# Create necessary directories
RUN mkdir -p /app/YuE-exllamav2/output
RUN mkdir -p /app/Server/logs

# Set proper permissions
RUN chmod +x /app/Server/server.py

# Expose the Flask port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Make startup script executable
RUN chmod +x /app/start_server.py

# Default command to run the server
CMD ["python", "/app/start_server.py"] 