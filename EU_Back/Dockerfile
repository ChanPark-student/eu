FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
# If requirements.txt is utf-16, this recodes it to utf-8 inside docker just in case
RUN cat requirements.txt | tr -d '\000' > requirements-utf8.txt && \
    pip install --no-cache-dir -r requirements-utf8.txt

# Copy source code
COPY . .

# Environment variables will be injected via docker-compose / .env file
# Run server
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
