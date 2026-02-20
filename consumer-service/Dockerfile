FROM python:3.10-slim

WORKDIR /app
# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ .

# Use unbuffered output to see logs in Docker immediately
CMD ["python", "-u", "consumer.py"]