FROM python:3.11-alpine

COPY requirements.txt /requirements.txt

COPY src/list-orphaned-resources-api.py /usr/local/bin/list-orphaned-resources-api.py

RUN apk add --no-cache --virtual .build-deps \
      build-base \
      libffi-dev \
      openssl-dev \
      python3-dev \
    && pip install -r requirements.txt \
    && rm /requirements.txt \
    && apk del .build-deps

CMD ["python3", "/usr/local/bin/list-orphaned-resources-api.py"]
