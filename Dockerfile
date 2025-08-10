FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DOCKER_CONTAINER=true

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./
COPY README.md ./

# Install Python dependencies
RUN pip install --no-cache-dir build && \
    pip install --no-cache-dir .

# Copy application code
COPY src/ ./

# Create non-root user
RUN useradd -m -u 1000 mcp && \
    chown -R mcp:mcp /app

# Switch to non-root user
USER mcp

# Expose the MCP server port (if using HTTP transport)
EXPOSE 8000

# Set the entrypoint
ENTRYPOINT ["python", "-m", "freshrss_mcp.server", "--http"]
