FROM python:3.7-alpine

COPY requirements.txt /requirements.txt

COPY src/list.py /usr/local/bin/list.py

RUN apk add --no-cache --virtual .build-deps \
      build-base \
      libffi-dev \
      openssl-dev \
      python3-dev \
    && pip install -r requirements.txt \
    && rm /requirements.txt \
    && apk del .build-deps

CMD ["python3", "/usr/local/bin/list.py"]
