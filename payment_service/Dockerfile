# payment_service/Dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY payment_service.py .
EXPOSE 5004
CMD ["python", "payment_service.py"]
