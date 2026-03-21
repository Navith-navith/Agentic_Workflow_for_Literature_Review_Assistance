FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for PDF processing
RUN apt-get update && apt-get install -y \
    curl \
    libpoppler-cpp-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download NLTK data and embedding model at build time
RUN python -c "\
import nltk; \
nltk.download('punkt', quiet=True); \
nltk.download('stopwords', quiet=True); \
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

RUN mkdir -p data/uploads data/vector_store

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
