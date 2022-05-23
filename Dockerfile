FROM python:3.7

WORKDIR /workdir
COPY . ./

RUN pip install -U pip
RUN pip install -r requirements.txt
RUN pip install -r requirements-dev.txt

ENTRYPOINT [ "python", "app.py" ]
