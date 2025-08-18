# Use Python 3.7 as specified in runtime.txt
FROM python:3.7-slim

# Set working directory
WORKDIR /app

# Install system dependencies for audio processing
RUN apt-get update && apt-get install -y \
    libgsl27 \
    libgslcblas0 \
    libsndfile1 \
    libsndfile1-dev \
    libmp3lame0 \
    sox \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.txt

# Copy application code
COPY vapor.py .

# Create cache directory
RUN mkdir -p /app/cache

# Create logs directory
RUN mkdir -p /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8443

# Run the application
CMD ["python", "vapor.py"]