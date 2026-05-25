# ==========================================
# DockPulse - Production-ready Dockerfile
# ==========================================

# 1. Use the official lightweight Python 3.10 slim image.
# Slim images omit unnecessary development libraries, resulting in a much smaller 
# attack surface and a container footprint (~120MB vs ~900MB full).
FROM python:3.10-slim

# 2. Set the working directory inside the container context.
WORKDIR /app

# 3. Prevent Python from writing byte-compiled (.pyc) files to disk.
ENV PYTHONDONTWRITEBYTECODE=1

# 4. Force stdout and stderr streams to be unbuffered. 
# This ensures application logs are printed immediately to the terminal/docker logs.
ENV PYTHONUNBUFFERED=1

# 5. Install minimal system packages required to compile standard wheels like psutil.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 6. Copy only requirements first to optimize Docker build caching.
# This prevents Docker from re-running 'pip install' on every source code edit.
COPY requirements.txt .

# 7. Install python packages in no-cache mode to keep the image slim.
RUN pip install --no-cache-dir -r requirements.txt

# 8. Copy the local application files into the working directory.
COPY . .

# 9. Inform Docker that the container listens on port 5000 at runtime.
EXPOSE 5000

# 10. Run the main Flask server script directly.
# Binds to 0.0.0.0 internally inside the container's network namespace.
CMD ["python", "app.py"]
