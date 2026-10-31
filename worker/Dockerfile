FROM docker.io/library/python:3.13.18-slim

# A tools/smoke_receipt.py betűkészlete: a Pillow beépítettjében nincs ékezet.
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt
COPY app app
COPY tools tools

USER nobody
CMD ["python", "-m", "app.main"]
