FROM python:slim-bullseye

COPY requirements.txt /
RUN \
  pip3 install -r /requirements.txt

ENV SERVER_HOSTNAME="0.0.0.0"
ENV SERVER_PORT=8080

ENV PING2_URL="http://localhost"
ENV PING2_USERNAME="user"
ENV PING2_PASSWORD="user"

COPY server.py /
CMD [ "python3", "/server.py"]
