FROM python:3.12-slim

WORKDIR /app

COPY backend/bq_main.py .
COPY model/ model/

RUN pip install --no-cache-dir \
    fastapi uvicorn[standard] google-cloud-bigquery \
    pandas joblib scikit-learn python-multipart

CMD ["uvicorn", "bq_main:app", "--host", "0.0.0.0", "--port", "8080"]
