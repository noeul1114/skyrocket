FROM python:3.8.1

RUN apt-get update
WORKDIR /home/

RUN git clone --depth 1 https://github.com/noeul1114/skyrocket.git
WORKDIR /home/skyrocket/
RUN git fetch --all && git reset --hard master && git pull

WORKDIR /home/skyrocket

RUN pip install -r requirements.txt

EXPOSE 8000
