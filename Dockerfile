FROM python:3.11-slim

WORKDIR /app

# Install AWS CLI
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl unzip && \
    curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip && \
    unzip -q awscliv2.zip && \
    ./aws/install && \
    rm -rf awscliv2.zip aws && \
    apt-get purge -y curl unzip && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir ".[mcp]"

ENTRYPOINT ["aaws-mcp"]
