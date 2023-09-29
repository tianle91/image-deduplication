# https://github.com/ykursadkaya/pyspark-Docker
ARG IMAGE_VARIANT=buster
ARG PYTHON_VERSION=3.9.8
FROM python:${PYTHON_VERSION}-${IMAGE_VARIANT}

RUN apt update -y && apt install git

# make sure these match tox.ini
RUN pip install tox==3.26.0 poetry==1.3.2 tox-poetry-installer==0.10.2
