FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Upgrade pip and install curl (for healthchecks)
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --upgrade pip

# Copy requirements first to leverage Docker cache layer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose port the app runs on
EXPOSE 8000

# Command to run FastAPI server
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
