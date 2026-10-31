FROM docker.io/library/python:3.13.18-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt
COPY app app

USER nobody
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
