FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Singapore

# Set timezone
RUN ln -sf /usr/share/zoneinfo/${TZ} /etc/localtime

RUN apt-get update && \
    apt-get -y upgrade && \
    apt-get -y install --no-install-recommends \
    cron \
    sqlite3 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy all files to the /app directory
COPY . .

# Install dependencies
RUN pip install -r requirements.txt

# Expose port
# EXPOSE 5000

# Set the working directory for application source code
WORKDIR /app/src

# Ensure the workspace directory exists
RUN mkdir -p /app/src/workspace

# Make scripts executable
RUN chmod +x /app/entrypoint.sh

# Run the server using Uvicorn
ENTRYPOINT ["/app/entrypoint.sh"]
