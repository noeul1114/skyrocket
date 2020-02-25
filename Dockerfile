FROM python:3.8.1

RUN apt-get update && apt-get upgrade -y

RUN cd /home

RUN git clone https://github.com/noeul1114/skyrocket.git

WORKDIR /home/skyrocket/
RUN pip install -r requirements.txt

EXPOSE 8000