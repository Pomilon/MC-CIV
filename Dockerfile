# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Install system dependencies and Node.js
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /home/appuser -m appuser

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Node.js dependencies
COPY bot-client/package.json bot-client/package.json
WORKDIR /app/bot-client
RUN npm install
WORKDIR /app

# Copy application code (Ordered by frequency of change to optimize layering)
COPY --chown=appuser:appuser agents agents
COPY --chown=appuser:appuser cli cli
COPY --chown=appuser:appuser infrastructure infrastructure
COPY --chown=appuser:appuser narrator narrator
COPY --chown=appuser:appuser bot-client bot-client
COPY --chown=appuser:appuser dashboard dashboard
COPY --chown=appuser:appuser data data
COPY --chown=appuser:appuser docs docs
COPY --chown=appuser:appuser tests tests
COPY --chown=appuser:appuser .env.example LICENSE README.md ./

# Create data directory and set permissions
# We use 777 to ensure the non-root user can write even if a bind mount overlays it with different permissions
RUN mkdir -p data/agents && chmod -R 777 data && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser


# Environment variables (Defaults)
ENV PYTHONUNBUFFERED=1
ENV PORT=3000
ENV PYTHONPATH=/app

# Command to run the CLI

ENTRYPOINT ["python3", "-m", "cli.main"]

# Default: Mock mode. Override with: "--mode real --host host.docker.internal --port 25565 --disable-narrator"

CMD ["--mode", "mock"]
