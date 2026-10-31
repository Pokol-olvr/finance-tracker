FROM docker.io/library/python:3.13.18-slim

RUN pip install --no-cache-dir --root-user-action=ignore dbt-core==1.12.6 dbt-postgres==1.11.0

WORKDIR /dbt
ENTRYPOINT ["dbt"]
