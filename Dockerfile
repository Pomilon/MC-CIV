# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Install system dependencies and Node.js
# We need Node.js because the Python CLI spawns Mineflayer (Node) processes
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

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

# Copy the rest of the application code
COPY . .

# Create data directory for persistence
RUN mkdir -p data/agents

# Environment variables (Defaults)
ENV PYTHONUNBUFFERED=1
ENV PORT=3000

# Command to run the CLI
# Users can override args via docker-compose command
ENTRYPOINT ["python", "cli/main.py"]
CMD ["--mode", "mock"]
