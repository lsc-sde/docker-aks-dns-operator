import kopf
import logging
import time
import asyncio
import kubernetes
import base64 
import os
from azure.identity import DefaultAzureCredential
from azure.mgmt.privatedns import PrivateDnsManagementClient

private_dns_zone_name = os.environ.get("PRIVATE_DNS_ZONE", "")
dns_prefix = os.environ.get("DNS_PREFIX", "")
subscription_id = os.environ.get("AZ_SUBSCRIPTION_ID", "")
resource_group_name = os.getenv("RESOURCE_GROUP_NAME", "")
dns_client = PrivateDnsManagementClient(credential=DefaultAzureCredential(), subscription_id = subscription_id)

def set_a_record(name: str, ip_addresses : [], managed_by : str):
    logging.info(f"Adding A Record {name}")

    records = dns_client.record_sets.list(
        resource_group_name = resource_group_name,
        private_zone_name = private_dns_zone_name
        );
    
    
    filtered_records = [r for r in records if r.name == name]
    perform_update : bool = True
    if len(filtered_records) > 0:
        record = filtered_records[0]
        currently_managed_by = record.metadata.get("managedBy")
        
        if not currently_managed_by:
            perform_update = False
            logging.error(f"The current record has no managedBy flag")

        elif currently_managed_by != managed_by:
            perform_update = False
            logging.error(f"{name} is currently managed by '{currently_managed_by}' not '{managed_by}'")

        else:
            found_differences : bool = False
            for ip in record.a_records: 
                if ip.ipv4_address not in ip_addresses:
                    logging.info(f"{ip.ipv4_address} has been removed")
                    found_differences = True

            for ip in ip_addresses:
                if ip not in [e.ipv4_address for e in record.a_records]:
                    logging.info(f"{ip} has been added")
                    found_differences = True

            if not found_differences:
                logging.info(f"No differences on {name} to target {ip_addresses}, no update required")
                perform_update = True
            
    if perform_update:
        logging.info(f"Updating A {name} to target {ip_addresses}")
        targets = [{ "ipv4Address" : ip } for ip in ip_addresses]
        logging.info(targets)
        dns_client.record_sets.create_or_update(
            resource_group_name = resource_group_name, 
            private_zone_name = private_dns_zone_name, 
            record_type = "A", 
            relative_record_set_name=name, 
            parameters={
                "properties" : {
                    "aRecords": targets
                },
                "metadata" : {
                    "managedBy" : managed_by
                },
                "ttl" : 300
            })


def set_c_record(name: str, target: str, managed_by : str):
    logging.info(f"Adding C Record {name}")

    records = dns_client.record_sets.list(
        resource_group_name = resource_group_name,
        private_zone_name = private_dns_zone_name,
        );
    
    filtered_records = [r for r in records if r.name == name]
    perform_update : bool = True
    if len(filtered_records) > 0:
        record = filtered_records[0]
        currently_managed_by = record.metadata.get("managedBy")
        
        if not currently_managed_by:
            perform_update = False
            logging.error(f"The current record has no managedBy flag")

        elif currently_managed_by != managed_by:
            perform_update = False
            logging.error(f"{name} is currently managed by '{currently_managed_by}' not '{managed_by}'")

        elif record.cname_record.cname == target:
            logging.info(f"{name} is already set to '{record.cname_record.cname}', no update needed")
            perform_update = False

    if perform_update:
        logging.info(f"Updating CNAME {name} to target {target}")

        dns_client.record_sets.create_or_update(
            resource_group_name = resource_group_name, 
            private_zone_name = private_dns_zone_name, 
            record_type = "CNAME", 
            relative_record_set_name=name, 
            parameters={
                "properties" : {
                    "cnameRecord": { 
                        "cname" : target
                    }   
                },
                "metadata" : {
                    "managedBy" : managed_by
                },
                "ttl" : 300
            })


def process_record(type, annotations, name, namespace, status):
    managed_by = f"{type}/{namespace}/{name}"
    if 'xlscsde.nhs.uk/dns-record' in annotations:
        record = annotations.get("xlscsde.nhs.uk/dns-record")
        record_with_prefix = f"{dns_prefix}{record}"
        record_fqdn = f"{record_with_prefix}.{private_dns_zone_name}"
        loadBalancerStatus = status.get("loadBalancer")
        ingressStatus = loadBalancerStatus.get("ingress")
        target_ips = []
        for item in ingressStatus:
            if 'ip' in item:
                target_ips.append(item.get("ip"))

        target = annotations.get("xlscsde.nhs.uk/dns-record-target")
        record_type = annotations.get("xlscsde.nhs.uk/dns-record-type", "A")
        if target and record_type:
            if record_type == "A":
                set_a_record(record_with_prefix, target.split(","), managed_by = managed_by)
            elif record_type == "CNAME":
                set_c_record(record_with_prefix, target, managed_by = managed_by)
        else:
            ip_count = len(target_ips)
            if ip_count > 0:
                logging.info(f"{type} {name} on {namespace} has been updated, '{record_fqdn}' targets '{target_ips}'")
                set_a_record(record_with_prefix, target_ips, managed_by= managed_by)

            elif type == "ingress":
                target_fqdn = f"{dns_prefix}nginx.{private_dns_zone_name}"
                logging.info(f"{type} {name} on {namespace} has been updated, '{record_fqdn}' has no targets, creating CNAME record to {target_fqdn}")
                set_c_record(record_with_prefix, target_fqdn, managed_by= managed_by)

            else:
                target_ips = [ "127.0.0.1" ]
                logging.info(f"{type} {name} on {namespace} has been updated, '{record_fqdn}' targets '{target_ips}'")
                set_a_record(record_with_prefix, target_ips, managed_by= managed_by)



@kopf.on.create("Ingress")
@kopf.on.update("Ingress")
@kopf.on.resume("Ingress")
def ingressUpdated(annotations, name, namespace, status, **_):
    process_record("ingress", annotations, name, namespace, status)

@kopf.on.create("Service")
@kopf.on.update("Service")
@kopf.on.resume("Service")
def serviceUpdated(annotations, status, name, namespace, **_):
    process_record("service", annotations, name, namespace, status)
    
