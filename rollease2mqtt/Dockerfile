# This is a Dockerfile for running as an add-on to
# Home Assistant.

ARG BUILD_FROM
FROM $BUILD_FROM

ENV LANG C.UTF-8

COPY . /

RUN apk add --no-cache python3 jq
RUN python3 -m pip install -r /requirements.txt

WORKDIR /

RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
