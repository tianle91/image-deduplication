# https://github.com/ykursadkaya/pyspark-Docker
ARG IMAGE_VARIANT=buster
ARG PYTHON_VERSION=3.9.8
FROM python:${PYTHON_VERSION}-${IMAGE_VARIANT}

RUN apt update -y && apt install -y git ffmpeg libsm6 libxext6

RUN pip install poetry==1.3.2

COPY . /workdir
WORKDIR /workdir
RUN make .venv
ENTRYPOINT [ "make", "run" ]
