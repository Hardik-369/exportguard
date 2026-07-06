FROM python:3.12-slim

WORKDIR /app

COPY backend/ backend/
COPY model/ model/

RUN pip install --no-cache-dir \
    fastapi uvicorn[standard] google-cloud-bigquery \
    pandas joblib scikit-learn python-multipart

RUN python -c "import zipfile; zipfile.ZipFile('model/exportguard_model.zip').extractall('model/')"

CMD uvicorn backend.bq_main:app --host 0.0.0.0 --port ${PORT:-7860}
