FROM python:3.12-slim

WORKDIR /srv/crm
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV CRM_BIND=0.0.0.0 \
    CRM_ALLOW_PUBLIC_BIND=1 \
    CRM_PORT=18734 \
    CRM_SQLITE_PATH=/data/crm.db \
    PYTHONUNBUFFERED=1

VOLUME ["/data"]
EXPOSE 18734
CMD ["python3", "app.py"]
