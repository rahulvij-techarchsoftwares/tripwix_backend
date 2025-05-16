FROM python:3.11-slim
ENV PYTHONUNBUFFERED 1

RUN apt-get update --fix-missing
RUN apt-get install -y \
    libpq-dev \
    python3-pip \
    gdal-bin \
    postgis \
    git

ADD requirements/base.pip /
ADD requirements/local.pip /
RUN pip install -r /local.pip

RUN mkdir /code

WORKDIR /code
ADD . /code
