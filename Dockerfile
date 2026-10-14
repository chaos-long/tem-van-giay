FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py matcher.py cloud_database.py ./
COPY web ./web
COPY demo ./demo
RUN python demo/generate.py
ENV TEM_HOST=0.0.0.0 TEM_DATA_DIR=/data TEM_PORT=8765 PYTHONUNBUFFERED=1
RUN mkdir -p /data
EXPOSE 8765
CMD ["python", "server.py"]
