FROM docker.io/library/python:3.13.18-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt
COPY .streamlit .streamlit
COPY app app

# A Streamlit a saját beállításait a home mappába írná, a nobody-nak pedig nincs ilyenje.
ENV HOME=/tmp
ENV PYTHONPATH=/srv
USER nobody
CMD ["streamlit", "run", "app/main.py"]
