FROM python:3.8.1-alpine

RUN apk update && apk upgrade
RUN apk add git

RUN cd /home

RUN git clone https://github.com/noeul1114/skyrocket.git

RUN cd /home/skyrocket/

RUN pip install -r requirements.txt

EXPOSE 8000