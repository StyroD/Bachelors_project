FROM python:3.12-slim
 
# System dependencies for psycopg2 and reportlab
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*
 
WORKDIR /app
 
# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
 
# Copy application code from app/ subdirectory
COPY app/app.py .
COPY app/db.py .
COPY app/ui.py .
COPY app/server.py .
COPY app/services/ ./services/
 
EXPOSE 8000
 
CMD ["python", "-m", "shiny", "run", "app.py", "--host", "0.0.0.0", "--port", "8000"]