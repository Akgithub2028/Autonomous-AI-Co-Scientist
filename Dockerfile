FROM python:3.11-slim

WORKDIR /app

# System dependencies for scientific packages
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Explicit dependencies identified during development
RUN pip install --no-cache-dir langchain-core langchain-huggingface pydantic SQLAlchemy networkx cdlib matplotlib

COPY . .

ENTRYPOINT ["python", "main.py"]
