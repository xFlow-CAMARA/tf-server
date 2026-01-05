FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (curl for health checks, docker cli + compose for OAI control)
RUN apt-get update && apt-get install -y \
    curl \
    docker.io \
    docker-compose \
    && rm -rf /var/lib/apt/lists/*

# Install only required Python dependencies
RUN pip install --no-cache-dir \
    fastapi==0.115.6 \
    uvicorn[standard]==0.34.0 \
    requests==2.32.3 \
    pyyaml==6.0.2 \
    pydantic==2.10.6 \
    prometheus-client==0.21.1

# Copy application code
COPY . .

# Install the sunrise6g_opensdk package from src/
RUN pip install -e .

EXPOSE 8200

CMD ["python", "api_server.py"]
