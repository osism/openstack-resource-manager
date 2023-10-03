# SPDX-License-Identifier: AGPL-3.0-or-later

FROM python:3.12-alpine

COPY requirements.txt /requirements.txt
COPY src/main.py /usr/local/bin/openstack-resource-manager.py

RUN apk add --no-cache --virtual .build-deps \
      build-base \
      libffi-dev \
      openssl-dev \
      python3-dev \
    && pip install -r requirements.txt \
    && rm /requirements.txt \
    && apk del .build-deps

CMD ["python3", "/usr/local/bin/openstack-resource-manager.py"]
