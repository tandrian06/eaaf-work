FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY eaaf_work ./eaaf_work
COPY chat ./chat
COPY config ./config
COPY knowledge ./knowledge
USER 65532:65532
CMD ["python", "-m", "uvicorn", "eaaf_work.app:app", "--host", "0.0.0.0", "--port", "8001"]
