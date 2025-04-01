FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY notification_service.py .
EXPOSE 5006
CMD ["python", "notification_service.py"]
