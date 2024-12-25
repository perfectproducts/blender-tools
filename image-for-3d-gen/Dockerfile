# Use NVIDIA PyTorch container as base for CUDA support
FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application files
COPY . .

# Set environment variables
ENV PERSISTENT_DIR=/workdir/data
ENV HF_HOME=/workdir/models
ENV HF_HUB_CACHE=/workdir/models

# Create necessary directories
RUN mkdir -p /workdir/models /workdir/data/gallery

# Expose the FastAPI port
EXPOSE 8000

# Run the FastAPI application
CMD ["python", "app.py"]