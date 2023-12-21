import json
import os

from azure.identity import DefaultAzureCredential
from azure.mgmt.privatedns import PrivateDnsManagementClient
from kubernetes import client, config, watch

if 'KUBERNETES_PORT' in os.environ:
    config.load_incluster_config()
else:
    config.load_kube_config()

managedBy = os.getenv("MANAGED_BY", "aks-dns-operator")
subscriptionId = os.getenv("SUBSCRIPTION_ID", "5bb2478d-e497-4ca1-964e-4aaa9f754a5d");
resourceGroupName = os.getenv("RESOURCE_GROUP_NAME", "lscsandboxsde-rg")
privateZoneName = os.getenv("PRIVATE_ZONE_NAME", "privatelink.uksouth.azmk8s.io")

dnsClient = PrivateDnsManagementClient(credential=DefaultAzureCredential(), subscription_id = subscriptionId)
                
v1 = client.CoreV1Api();
watch = watch.Watch();
for event in watch.stream(v1.list_service_for_all_namespaces, timeout_seconds=10):
    service = event['object']
    if service.metadata.annotations != None: 
        if 'service.beta.kubernetes.io/azure-private-dns-prefix' in service.metadata.annotations:
            dnsPrefixes = service.metadata.annotations['service.beta.kubernetes.io/azure-private-dns-prefix']
            for dnsPrefix in dnsPrefixes.split(" "):
                ipAddresses = []
                for ingress in service.status.load_balancer.ingress:
                    ipAddresses.append({ "ipv4Address" : ingress.ip })
                
                if event['type'] == "ADDED" or event['type'] == "MODIFIED":
                    print("Event: %s %s (%s -> %s)" % (event['type'], event['object'].metadata.name, dnsPrefix, ipAddresses))
                    
                    recordsResponse = dnsClient.record_sets.list_by_type(
                        resourceGroupName,
                        privateZoneName,
                        record_type="A"
                        );
                    

                    foundRecord = False
                    recordIsManaged = False
                    requiresUpdate = False

                    for records in recordsResponse:
                        if records.name == dnsPrefix:
                            # The record does exist
                            foundRecord = True
                            
                            # Check to see if the record is managed by this service
                            if records.metadata['managedBy'] == managedBy:
                                recordIsManaged = True
                            
                            for ipAddress in records.a_records:
                                # Check to see if the IP addresses exist
                                ipExists = False
                                for sourceIp in ipAddresses:
                                    if sourceIp['ipv4Address'] == ipAddress.ipv4_address:
                                        ipExists = True

                                if ipExists == False:
                                    requiresUpdate = True

                            if requiresUpdate == False:
                                for sourceIp in ipAddresses:
                                    # Check to see if the IP addresses exist
                                    ipExists = False
                                    for ipAddress in records.a_records:
                                        if sourceIp['ipv4Address'] == ipAddress.ipv4_address:
                                            ipExists = True

                                    if ipExists == False:
                                        requiresUpdate = True   

                    if foundRecord == False or (foundRecord == True and recordIsManaged == True and requiresUpdate == True):
                        print("%s %s %s" % (foundRecord, recordIsManaged, requiresUpdate))
                        dnsClient.record_sets.create_or_update(
                            resourceGroupName, 
                            privateZoneName, 
                            record_type="A", 
                            relative_record_set_name=dnsPrefix, 
                            parameters={
                                "properties" : {
                                    "aRecords": ipAddresses
                                },
                                "metadata" : {
                                    "managedBy" : managedBy
                                },
                                "ttl" : 300
                            })