# Stage 1: Build React Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/client
COPY client/package*.json ./
RUN npm ci
COPY client/ ./
RUN npm run build

# Stage 2: Build FastAPI Backend and Final Image
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend codebase
COPY server/ ./server/

# Copy compiled frontend build from Stage 1 into the location served by FastAPI
COPY --from=frontend-builder /app/client/dist ./client/dist

# Expose port and run server via programmatic python launcher to handle cloud dynamic ports
EXPOSE 8000
CMD ["python", "run.py"]
