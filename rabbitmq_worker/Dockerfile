FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY worker.py .

# Unbuffered output for logging
ENV PYTHONUNBUFFERED=1

CMD ["python", "worker.py"]
