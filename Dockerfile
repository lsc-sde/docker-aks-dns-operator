FROM python:alpine

RUN apk add gcc
RUN pip install --upgrade pip
RUN pip install azure-identity
RUN pip install azure-mgmt-privatedns
RUN pip install kubernetes
RUN MULTIDICT_NO_EXTENSIONS=1 pip install kopf
ADD . /src

ENV AZ_SUBSCRIPTION_ID=""
ENV RESOURCE_GROUP_NAME=""
ENV PRIVATE_ZONE_NAME=""
ENV DNS_PREFIX=""

CMD kopf run /src/service.py -A --standalone