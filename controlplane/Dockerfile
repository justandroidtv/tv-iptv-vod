FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY app /app/app
COPY frontend /app/frontend
EXPOSE 9393
CMD ["sh","-c","uvicorn app.main:app --host 0.0.0.0 --port \${CONTROL_PLANE_PORT:-9393}"]
