FROM python:3.12-slim
WORKDIR /app
COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r /app/server/requirements.txt
COPY . /app
ENV PYTHONPATH=/app/server
WORKDIR /app/server
CMD ["python", "-m", "app.main"]
