ARG OWNER=vvcb
ARG BASE_CONTAINER=python:3.12.1
FROM $BASE_CONTAINER

WORKDIR /usr/src/app

RUN pip install --upgrade pip
RUN pip install azure-identity
RUN pip install azure-mgmt-privatedns
RUN pip install kubernetes

COPY service-operator.py service-operator.py

ENV MANAGED_BY="aks-dns-operator"
ENV SUBSCRIPTION_ID="5bb2478d-e497-4ca1-964e-4aaa9f754a5d"
ENV RESOURCE_GROUP_NAME="lscsandboxsde-rg"
ENV PRIVATE_ZONE_NAME="privatelink.uksouth.azmk8s.io"

CMD [ "python", "./service-operator.py"]