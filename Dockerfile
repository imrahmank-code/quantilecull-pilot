FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python dependencies
RUN pip install --no-cache-dir bottle cryptography psycopg2-binary gunicorn

# Copy necessary source code files
COPY licensing.py /app/
COPY scripts/ /app/scripts/

# Expose default port (Koyeb/Render will route this dynamically)
EXPOSE 5005

# Run using gunicorn bound to the environment-supplied port
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT scripts.licensing_server:app"]
