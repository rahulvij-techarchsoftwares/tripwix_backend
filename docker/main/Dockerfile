FROM python:3.11.10-slim
ENV PYTHONUNBUFFERED 1

RUN apt-get update --fix-missing
RUN apt-get install -y \
    libpq-dev \
    python3-pip \
    gdal-bin \
    postgis

ADD requirements/base.pip /
RUN pip install -r /base.pip
ADD requirements/server.pip /
RUN pip install -r /server.pip

ADD . /code

VOLUME /code

WORKDIR /code
