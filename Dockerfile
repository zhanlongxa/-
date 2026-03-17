# Use official Python runtime as a parent image
# Slim version to keep size down, but we need to install system deps
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Install system dependencies required for OpenCV, PaddleOCR, and MoviePy
# libgl1-mesa-glx: for OpenCV
# libglib2.0-0: for OpenCV
# ffmpeg: for MoviePy/EdgeTTS
# gcc/g++: for building some python extensions if needed
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    ffmpeg \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt /app/requirements.txt

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . /app

# Create necessary directories
RUN mkdir -p /app/uploads /app/outputs /app/templates

# Fix for PaddleOCR/EasyOCR model download permissions (optional, better to pre-download if possible)
# But for now we rely on them checking/downloading to /root/.paddlex or similar. 
# Cloud Run runs as root by default unless specified otherwise.

# Expose port (Cloud Run sets PORT env var)
EXPOSE 8080

# Run with Gunicorn for production performance
# Workers: 1 (since we use heavy ML models, multiple workers might OOM on small instances)
# Timeout: 120s (OCR can be slow)
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 300 app:app
